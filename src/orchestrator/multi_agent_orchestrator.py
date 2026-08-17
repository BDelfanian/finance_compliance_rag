"""
STEP 6 — Multi-Agent Orchestrator
--------------------------------
Deterministic orchestration layer coordinating
compliance-grade agents built in STEP 4 & STEP 5.

LangChain is used ONLY as an execution wrapper.
NO logic is delegated to LangChain.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict

# MLflow-wrapped agent chains (STEP 6.3 / Phase 1's observability wrappers).
# Previously this imported the plain (unlogged) chains from
# src.orchestrator.langchain_wrappers, while the live Streamlit UI called
# these MLflow-wrapped ones directly — two chain paths for the same agents
# (see docs/09's "Known issue" section). Standardizing the orchestrator on
# these wrappers, and having the future API layer (app/api.py) be the only
# caller of MultiAgentOrchestrator, makes this the one canonical path: every
# orchestrated run (UI or API) now gets MLflow logging, params/metrics, and
# trace_id tagging for free, instead of a second hand-maintained chain set.
from src.chains.step6_agent_wrappers_mlflow import (
    citation_chain,
    retrieval_chain,
    risk_assessment_chain,
    summarization_chain,
    traced_query_run,
)
from src.config import get_settings
from src.observability.cost_tracking import all_usage, summarize, usage_scope
from src.observability.logging_config import get_logger, new_trace_id, trace_id_scope

logger = get_logger(__name__)
settings = get_settings()

# -------------------------------
# Orchestrator
# -------------------------------


class MultiAgentOrchestrator:
    """
    Deterministic orchestration layer.

    Responsibilities:
    - Execute agents in the correct order
    - Enforce fail-fast behavior
    - Aggregate outputs
    - Attach audit metadata
    """

    def __init__(self, model_version: str):
        self.model_version = model_version

    async def run(self, query: str, trace_id: str | None = None) -> Dict[str, Any]:
        """Run the full agent sequence and return only the final result —
        the shape every existing caller (tests, and formerly the UI) expects.

        `trace_id` lets a caller (app/api.py) pre-generate the ID so it's
        known even if this raises before completion — otherwise it's
        generated fresh, as before."""
        trace_id = trace_id or new_trace_id()
        with trace_id_scope(trace_id), traced_query_run(trace_id, query), usage_scope():
            final_result: Dict[str, Any] = {}
            async for event in self._run_stages(query, trace_id):
                if event["stage"] == "final":
                    final_result = event["data"]
            return final_result

    async def run_events(self, query: str, trace_id: str | None = None) -> AsyncIterator[Dict[str, Any]]:
        """
        Same orchestration as `run()`, but yields one event per stage
        (retrieval, citation, summarization, risk_assessment, final) as it
        completes rather than only the aggregated end result — what
        `app/api.py`'s SSE endpoint streams to the client so a UI can show
        retrieval -> citation -> summary/risk progressively instead of one
        long spinner. Raises the same RuntimeError as `run()` on fail-fast;
        the caller is responsible for turning that into an "error" SSE event.
        """
        trace_id = trace_id or new_trace_id()
        with trace_id_scope(trace_id), traced_query_run(trace_id, query), usage_scope():
            async for event in self._run_stages(query, trace_id):
                yield event

    async def _run_stages(self, query: str, trace_id: str) -> AsyncIterator[Dict[str, Any]]:
        start_time = datetime.now(timezone.utc).isoformat()
        logger.info("orchestration started", extra={"query": query})

        # -------------------------------
        # 1. Retrieval (fail-fast)
        # -------------------------------
        retrieval_result = await retrieval_chain.ainvoke({"query": query})

        if not retrieval_result:
            logger.error("retrieval agent returned no results")
            raise RuntimeError("Retrieval agent returned no results")

        yield {"stage": "retrieval", "data": retrieval_result}

        # -------------------------------
        # 2. Citation-bound answer (fail-fast)
        # -------------------------------
        citation_payload = {
            "query": query,
            "retrieval_result": retrieval_result,
        }

        citation_result = await citation_chain.ainvoke(citation_payload)

        # NOTE: "citations" now means "chunks the LLM actually cited" (see
        # citation_agent._extract_cited_chunks), not "everything retrieved" —
        # so an empty citations list is a legitimate outcome (e.g. the model
        # correctly answered "Information not available in retrieved
        # sources") rather than proof the agent failed. Gate on the agent
        # having produced a real result instead; risk_assessment_agent
        # already surfaces "Insufficient regulatory citations" as a warning
        # when citations are empty or sparse.
        agent_citation = citation_result.get("agent_result")
        if not agent_citation or not agent_citation.get("answer"):
            logger.error("citation agent failed or returned no answer")
            raise RuntimeError("Citation agent failed or returned no answer")

        yield {"stage": "citation", "data": citation_result}

        # -------------------------------
        # 3. Parallel downstream agents
        # -------------------------------
        summary_payload = {
            "citation_result": agent_citation,
            "mode": "executive",
        }

        risk_payload = {
            "citation_result": agent_citation,
            "retrieval_result": retrieval_result,
        }

        summary_result, risk_result = await asyncio.gather(
            summarization_chain.ainvoke(summary_payload),
            risk_assessment_chain.ainvoke(risk_payload),
        )

        yield {"stage": "summarization", "data": summary_result}
        yield {"stage": "risk_assessment", "data": risk_result}

        # -------------------------------
        # 4. Confidence fusion (conservative)
        # -------------------------------
        final_confidence = min(
            agent_citation.get("confidence", 0.0),
            risk_result.get("confidence", 0.0),
        )

        if risk_result.get("warnings"):
            final_confidence *= 0.8

        # -------------------------------
        # 5. Audit metadata
        # -------------------------------
        usage_summary = summarize(all_usage())
        audit_trail = {
            "trace_id": trace_id,
            "query": query,
            "model_version": self.model_version,
            "agents": [
                "retrieval",
                "citation",
                "summarization",
                "risk_assessment",
            ],
            "timestamp": start_time,
            # Cost/usage tracking (roadmap §3.6): tokens + estimated $ cost
            # for every OpenAI call made during this query (embeddings +
            # chat completion), aggregated via src.observability.cost_tracking.
            "token_usage": {
                "prompt_tokens": usage_summary["prompt_tokens"],
                "completion_tokens": usage_summary["completion_tokens"],
                "embedding_tokens": usage_summary["embedding_tokens"],
            },
            "estimated_cost_usd": usage_summary["estimated_cost_usd"],
        }

        logger.info(
            "orchestration completed",
            extra={"confidence": round(final_confidence, 3), "warnings": risk_result.get("warnings")},
        )

        # -------------------------------
        # 6. Aggregated response
        # -------------------------------
        yield {
            "stage": "final",
            "data": {
                "answer": agent_citation,
                "summary": summary_result,
                "risk": risk_result,
                "confidence": round(final_confidence, 3),
                # Full retrieved set (cited + uncited), so a consumer can
                # render "retrieved, not directly cited" the way the
                # Streamlit UI's render_citations() already does — the
                # top-level "answer"/"summary"/"risk" agent results only
                # carry the narrower cited subset.
                "sources": citation_result.get("retrieved_chunks", []),
                "audit_trail": audit_trail,
            },
        }


# -------------------------------
# Sync convenience wrapper
# -------------------------------


def run_orchestrator(query: str, model_version: str = settings.model_version) -> Dict[str, Any]:
    orchestrator = MultiAgentOrchestrator(model_version=model_version)
    return asyncio.run(orchestrator.run(query))
