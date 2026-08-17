from typing import Dict, Any, List

from src.retrieval.run_embeddings_retrieval import retrieve
from src.orchestrator.agent_schema import AgentResult
from src.orchestrator.agent_validation import validate_agent_result


VECTOR_STORES = ["cssf", "dora", "eba", "nis2"]


async def retrieval_agent(query: str) -> Dict[str, Any]:
    """
    STEP 6 adapter for STEP 4 retrieval.

    Responsibilities:
    - Execute retrieval across all configured vector stores
    - Fail fast if nothing is retrieved
    - Return a validated AgentResult + raw retrieval payload
    """

    all_chunks: List[dict] = []
    source_refs: List[str] = []

    for store_key in VECTOR_STORES:
        result = retrieve(
            query_text=query,
            vector_store_key=store_key,
        )

        chunks = result.get("retrieved_chunks", [])
        if chunks:
            all_chunks.extend(chunks)
            source_refs.extend(
                c.get("source_reference") for c in chunks if c.get("source_reference")
            )

    if not all_chunks:
        raise ValueError("Retrieval agent returned no relevant chunks")

    # -------------------------------
    # AgentResult (control layer)
    # -------------------------------
    agent_result: AgentResult = {
        "agent_name": "retrieval",
        "answer": f"Retrieved {len(all_chunks)} relevant regulatory chunks.",
        "citations": sorted(set(source_refs)),
        "confidence": 1.0,  # Retrieval is deterministic
        "warnings": [],
    }

    validate_agent_result(agent_result)

    # -------------------------------
    # Return BOTH:
    # - validated agent result
    # - raw retrieval payload (for downstream agents)
    # -------------------------------
    return {
        "agent_result": agent_result,
        "retrieved_chunks": all_chunks,
    }
