"""
STEP 6 — Citation Agent (Adapter)
--------------------------------
This agent is a thin adapter over STEP 5's citation-bound
answer generation logic.

Design principles:
- ZERO new logic in STEP 5's generation/retrieval path
- ZERO prompt changes
- Deterministic passthrough
- Explicit contract normalization
"""

import re
from typing import Dict, Any, List

from src.generation.citation_bound_answer_generation import (
    generate_citation_bound_answer_cached
)
from src.orchestrator.agent_schema import AgentResult
from src.orchestrator.agent_validation import validate_agent_result

# Matches the LLM's instructed inline citation format, e.g. "[DORA Article 5.2]".
_CITATION_BRACKET_RE = re.compile(r"\[([^\]]+)\]")


def _extract_cited_chunks(
    answer_text: str, retrieved_chunks: List[dict]
) -> List[dict]:
    """
    Filter retrieved_chunks down to the subset the LLM actually referenced
    in its answer.

    The prompt instructs the LLM to cite sources inline as
    "[REGULATION chunk_id / article / paragraph]", but nothing enforces that
    it cites every chunk it was given as context — some retrieved chunks are
    routinely unused. A chunk counts as cited if its source_reference
    literally appears inside one of the answer's "[...]" brackets (same
    heuristic previously duplicated in the UI as `_is_cited_in_answer`).
    """
    brackets = _CITATION_BRACKET_RE.findall(answer_text or "")
    return [
        chunk
        for chunk in retrieved_chunks
        if chunk.get("source_reference")
        and any(chunk["source_reference"] in bracket for bracket in brackets)
    ]


async def citation_agent(
    query: str,
    retrieval_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    STEP 6 adapter for STEP 5 citation-bound answer generation.

    Responsibilities:
    - Generate citation-bound answer (STEP 5)
    - Return validated AgentResult for orchestration
    - Include raw retrieval payload if needed downstream
    """

    # -------------------------------
    # STEP 5 passthrough
    # -------------------------------
    citation_output = generate_citation_bound_answer_cached(
        query_text=query,
        top_k=5
    )

    retrieved_chunks: List[dict] = citation_output.get("retrieved_chunks", [])
    answer_text: str = citation_output.get("answer", "")
    confidence: float = float(citation_output.get("answer_confidence", 0.0))
    timestamp: str = citation_output.get("timestamp", "")

    # "citations" means what the LLM actually cited, not everything it was
    # handed as context — those are different sets, and conflating them made
    # it structurally impossible for downstream risk assessment to detect
    # retrieved-but-unused sources. See docs/09's "Known issue surfaced but
    # NOT fixed" section.
    cited_chunks: List[dict] = _extract_cited_chunks(answer_text, retrieved_chunks)

    # -------------------------------
    # AgentResult normalization
    # -------------------------------
    agent_result: AgentResult = {
        "agent_name": "citation",
        "answer": answer_text,
        "citations": cited_chunks,
        "confidence": confidence,
        "warnings": [],
    }

    validate_agent_result(agent_result)

    # -------------------------------
    # Return BOTH validated agent result and the full retrieved set
    # (downstream agents/UI need the full set to detect uncited sources)
    # -------------------------------
    return {
        "agent_result": agent_result,
        "retrieved_chunks": retrieved_chunks,
        "timestamp": timestamp,
    }
