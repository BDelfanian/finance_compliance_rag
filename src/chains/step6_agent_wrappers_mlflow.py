import json
import os
import tempfile
import time
from contextlib import contextmanager
from typing import Any, Awaitable, Callable, Dict, Iterator

import mlflow
from langchain_core.runnables import Runnable

from src.agents.citation_agent import citation_agent
from src.agents.retrieval_agent import retrieval_agent
from src.agents.risk_assessment_agent import risk_assessment_agent
from src.agents.summarization_agent import summarization_agent
from src.config import get_settings
from src.observability.cost_tracking import current_index, summarize, usage_since
from src.observability.logging_config import get_logger, get_trace_id

logger = get_logger(__name__)
settings = get_settings()

# -------------------------------
# MLflow setup
# -------------------------------
# mlflow's default tracking store (sqlite:///mlflow.db in this environment)
# creates new experiments with an artifact_location of "mlflow-artifacts:/..."
# by default — a scheme that only resolves through a running `mlflow server`
# proxy. `settings.mlflow_tracking_uri` (None by default here, so mlflow's
# own local-sqlite default is used; set it to e.g. http://localhost:5000 —
# see docker/docker-compose.yml — to point at a real tracking server
# instead, where "mlflow-artifacts:" resolves fine via the server's proxy).
#
# Without a server, every run logged against the default/pre-existing
# experiments failed with "the tracking URI must be a valid http or https
# URI" and was silently swallowed by the try/except below. Fix: when running
# against a local (non-http) store, log to our own experiment with an
# explicit local filesystem artifact root instead, so runs resolve without a
# server. Pre-existing experiments in mlflow.db are left untouched (their
# artifact_location can't be changed after creation anyway).
if settings.mlflow_tracking_uri:
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)

_ARTIFACT_ROOT = settings.resolved(settings.mlflow_artifact_root)


def _is_remote_tracking_uri(uri: str) -> bool:
    return uri.startswith("http://") or uri.startswith("https://")


def _ensure_experiment() -> None:
    experiment = mlflow.get_experiment_by_name(settings.mlflow_experiment_name)
    if experiment is None:
        if _is_remote_tracking_uri(mlflow.get_tracking_uri()):
            # A real `mlflow server` resolves "mlflow-artifacts:" itself via
            # its own configured artifact store — no local override needed.
            mlflow.create_experiment(settings.mlflow_experiment_name)
        else:
            _ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
            mlflow.create_experiment(
                settings.mlflow_experiment_name,
                artifact_location=_ARTIFACT_ROOT.as_uri(),
            )
    mlflow.set_experiment(settings.mlflow_experiment_name)


_ensure_experiment()


# -------------------------------
# Per-query parent run
# -------------------------------
@contextmanager
def traced_query_run(trace_id: str, query: str) -> Iterator[None]:
    """
    Wrap a full query's sequence of agent calls in one parent MLflow run, so
    the four per-agent runs `log_agent_run` starts with `nested=True` are
    genuinely nested underneath it (previously nested=True was a no-op: each
    UI stage ran its own `asyncio.run()` with no enclosing active run to
    nest under). One parent run per trace_id makes "everything that happened
    for this one query" directly browsable in the MLflow UI as a run tree,
    not just correlatable after the fact via the trace_id tag.
    """
    with mlflow.start_run(run_name=f"query_{trace_id[:8]}"):
        mlflow.set_tag("trace_id", trace_id)
        mlflow.set_tag("query", query)
        yield


# -------------------------------
# MLflow Logging Helper
# -------------------------------
async def log_agent_run(
    agent_name: str,
    payload: Dict[str, Any],
    latency_seconds: float,
    usage_summary: Dict[str, Any] | None = None,
):
    """
    Logs the agent payload to MLflow in JSON format, plus params/metrics
    (roadmap §3.2: "parameters, not just artifacts" / "metrics"). Nests
    under an active run if one exists (see traced_query_run); starts a new
    top-level run otherwise.
    """
    # retrieval/citation payloads wrap the AgentResult under "agent_result";
    # summarization/risk_assessment payloads *are* the AgentResult directly.
    # Falling back to `payload` itself (instead of {}) when "agent_result" is
    # absent is what makes confidence/warnings metrics correct for all four
    # agents instead of silently reading as 0.0 for the latter two.
    agent_result = payload.get("agent_result", payload)

    with mlflow.start_run(run_name=agent_name, nested=mlflow.active_run() is not None):
        mlflow.set_tag("trace_id", get_trace_id())

        # Params: static config that shaped this run, so runs are
        # comparable in the MLflow UI without opening the JSON artifact.
        mlflow.log_params(
            {
                "embedding_model": settings.embedding_model,
                "llm_model": settings.llm_model,
                "similarity_threshold": settings.similarity_threshold,
                "k_nearest": settings.k_nearest,
                "citation_top_k": settings.citation_top_k,
                "prompt_version": settings.prompt_version,
            }
        )

        # Metrics: measured outcomes of this specific run. Cost/usage metrics
        # (roadmap §3.6) are 0 for agents that make no OpenAI call of their
        # own (summarization, risk_assessment) — that's correct, not a gap.
        usage_summary = usage_summary or {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "embedding_tokens": 0,
            "estimated_cost_usd": 0.0,
        }
        mlflow.log_metrics(
            {
                "latency_seconds": round(latency_seconds, 4),
                "confidence": float(agent_result.get("confidence", 0.0)),
                "warnings_count": len(agent_result.get("warnings") or []),
                "prompt_tokens": usage_summary["prompt_tokens"],
                "completion_tokens": usage_summary["completion_tokens"],
                "embedding_tokens": usage_summary["embedding_tokens"],
                "estimated_cost_usd": usage_summary["estimated_cost_usd"],
            }
        )

        tmp_file = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json")
        try:
            json.dump(payload, tmp_file, indent=2)
            tmp_file.close()
            mlflow.log_artifact(tmp_file.name, artifact_path=agent_name)
        finally:
            os.unlink(tmp_file.name)


# -------------------------------
# Runnable wrapper with MLflow
# -------------------------------
def wrap_agent_with_mlflow(agent_fn: Callable[..., Awaitable[Any]]) -> Runnable:
    """
    Wraps an async agent with:
    - MLflow logging
    - LangChain Runnable interface

    `agent_fn`'s return type is `Awaitable[Any]`, not a specific dict shape,
    because the four agents genuinely return two different shapes:
    retrieval/citation wrap their AgentResult under "agent_result", while
    summarization/risk_assessment return the flat AgentResult TypedDict
    directly (see the "agent_name" lookup below, which already handles
    both).
    """

    async def wrapped_fn(inputs: Dict[str, Any]) -> Dict[str, Any]:
        agent_label = getattr(agent_fn, "__name__", "unknown")
        logger.info("agent run started", extra={"agent": agent_label})

        # Run the original agent, tracking any OpenAI usage recorded during
        # just this agent's call (not the whole query's — see cost_tracking.py).
        start = time.perf_counter()
        usage_start = current_index()
        outputs = await agent_fn(**inputs)
        latency_seconds = time.perf_counter() - start
        agent_usage_summary = summarize(usage_since(usage_start))

        # retrieval/citation payloads wrap the AgentResult under
        # "agent_result"; summarization/risk_assessment payloads *are* the
        # AgentResult directly — fall back to `outputs` itself so the real
        # short agent_name ("summarization", not the function name
        # "summarization_agent") is used for both shapes.
        agent_name = outputs.get("agent_result", outputs).get("agent_name", agent_label)

        # Log to MLflow
        try:
            await log_agent_run(
                agent_name=agent_name,
                payload=outputs,
                latency_seconds=latency_seconds,
                usage_summary=agent_usage_summary,
            )
        except Exception:
            logger.warning("MLflow logging skipped", extra={"agent": agent_name}, exc_info=True)

        logger.info(
            "agent run completed",
            extra={"agent": agent_name, "latency_seconds": round(latency_seconds, 4)},
        )

        return outputs

    # RunnableLambda equivalent: sync dummy + async afunc
    from langchain_core.runnables import RunnableLambda

    return RunnableLambda(lambda x: x, afunc=wrapped_fn)


# -------------------------------
# Example agent chain wrappers
# -------------------------------
# Wrap agents with MLflow logging
retrieval_chain = wrap_agent_with_mlflow(retrieval_agent)
citation_chain = wrap_agent_with_mlflow(citation_agent)
summarization_chain = wrap_agent_with_mlflow(summarization_agent)
risk_assessment_chain = wrap_agent_with_mlflow(risk_assessment_agent)
