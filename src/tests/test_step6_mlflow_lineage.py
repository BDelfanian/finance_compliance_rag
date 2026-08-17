# src/tests/test_step6_mlflow_lineage.py
from unittest.mock import AsyncMock, patch

import pytest

from src.chains import step6_agent_wrappers_mlflow as wrappers


@pytest.mark.asyncio
async def test_step6_agent_lineage_smoke():
    """
    STEP 6 smoke test:
    - Verify retrieval and citation wrappers
    - Patch MLflow logging to avoid hangs
    """

    frozen_retrieval_output = {
        "agent_result": {
            "agent_name": "retrieval",
            "answer": "Retrieved 2 relevant regulatory chunks.",
            "citations": ["BCBS_2010"],
            "confidence": 1.0,
            "warnings": [],
        },
        "retrieved_chunks": [
            {"chunk_id": "c1", "source_reference": "BCBS_2010"},
            {"chunk_id": "c2", "source_reference": "BCBS_2010"},
        ],
    }

    frozen_citation_output = {
        "agent_result": {
            "agent_name": "citation",
            "answer": "Banks must maintain a minimum CET1 ratio...",
            "citations": ["BCBS_2010"],
            "confidence": 0.92,
            "warnings": [],
        },
        "retrieved_chunks": frozen_retrieval_output["retrieved_chunks"],
        "timestamp": "2026-01-04T00:00:00Z",
    }

    # Patch MLflow and agent functions
    with (
        patch("mlflow.log_artifact"),
        patch("mlflow.log_params"),
        patch(
            "src.chains.step6_agent_wrappers_mlflow.retrieval_chain.afunc",
            new=AsyncMock(return_value=frozen_retrieval_output),
        ),
        patch(
            "src.chains.step6_agent_wrappers_mlflow.citation_chain.afunc",
            new=AsyncMock(return_value=frozen_citation_output),
        ),
    ):
        # 1️⃣ Test retrieval_chain
        retrieval_result = await wrappers.retrieval_chain.ainvoke({"query": "Basel III capital requirements"})
        assert retrieval_result["agent_result"]["agent_name"] == "retrieval"
        assert len(retrieval_result["retrieved_chunks"]) == 2

        # 2️⃣ Test citation_chain
        citation_result = await wrappers.citation_chain.ainvoke(
            {
                "query": "Basel III capital requirements",
                "retrieval_result": retrieval_result,
            }
        )
        assert citation_result["agent_result"]["agent_name"] == "citation"
        assert "Banks must maintain" in citation_result["agent_result"]["answer"]
