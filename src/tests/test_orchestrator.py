"""
STEP 6 — Orchestrator Tests
--------------------------
Pytest-based validation of deterministic orchestration logic.

These tests deliberately mock the LangChain-wrapped agent chains
(retrieval_chain, citation_chain, summarization_chain, risk_assessment_chain)
that MultiAgentOrchestrator actually calls, to:
- Validate fail-fast behavior
- Validate confidence fusion
- Validate risk downgrade logic
- Avoid dependence on LLMs or vector stores
"""

import pytest
from src.orchestrator.multi_agent_orchestrator import MultiAgentOrchestrator
from src.orchestrator.langchain_wrappers import make_chain


# -------------------------------
# Mock chain implementations (match the real agent I/O contracts)
# -------------------------------

async def mock_retrieval_chain_fn(query: str):
    return {
        "agent_result": {
            "agent_name": "retrieval",
            "answer": "Retrieved 2 relevant regulatory chunks.",
            "citations": ["REG-1", "REG-2"],
            "confidence": 1.0,
            "warnings": [],
        },
        "retrieved_chunks": [
            {"source_reference": "REG-1", "text": "Sample regulation text"},
            {"source_reference": "REG-2", "text": "Another regulation"},
        ],
    }


async def mock_citation_chain_fn(payload: dict):
    return {
        "agent_result": {
            "agent_name": "citation",
            "answer": "Regulated entities must disclose X.",
            "citations": [
                {"source_reference": "REG-1", "excerpt": "must disclose X"}
            ],
            "confidence": 0.8,
            "warnings": [],
        },
        "retrieved_chunks": payload["retrieval_result"]["retrieved_chunks"],
        "timestamp": "2026-01-03T00:00:00",
    }


async def mock_summarization_chain_fn(payload: dict):
    citation_result = payload["citation_result"]
    return {
        "agent_name": "summarization",
        "answer": "Entities must disclose X.",
        "citations": citation_result["citations"],
        "confidence": 0.75,
        "warnings": [],
    }


async def mock_risk_chain_fn(payload: dict):
    citation_result = payload["citation_result"]
    return {
        "agent_name": "risk_assessment",
        "answer": "Partial regulatory coverage detected.",
        "citations": citation_result["citations"],
        "confidence": 0.6,
        "warnings": ["Partial regulatory coverage"],
    }


# -------------------------------
# Test helpers
# -------------------------------

@pytest.fixture
def orchestrator(monkeypatch):
    """
    Orchestrator with mocked agent chains injected.
    """
    from src.orchestrator import multi_agent_orchestrator as mao

    monkeypatch.setattr(mao, "retrieval_chain", make_chain(mock_retrieval_chain_fn))
    monkeypatch.setattr(mao, "citation_chain", make_chain(mock_citation_chain_fn))
    monkeypatch.setattr(mao, "summarization_chain", make_chain(mock_summarization_chain_fn))
    monkeypatch.setattr(mao, "risk_assessment_chain", make_chain(mock_risk_chain_fn))

    return MultiAgentOrchestrator(model_version="test-model")


# -------------------------------
# Tests
# -------------------------------

@pytest.mark.asyncio
async def test_orchestrator_happy_path(orchestrator):
    result = await orchestrator.run("test query")

    assert "answer" in result
    assert "summary" in result
    assert "risk" in result
    assert "audit_trail" in result

    # Confidence should be min(citation=0.8, risk=0.6) with downgrade
    assert result["confidence"] < 0.6


@pytest.mark.asyncio
async def test_fail_fast_on_missing_retrieval(monkeypatch):
    async def empty_retrieval(query: str):
        return None

    from src.orchestrator import multi_agent_orchestrator as mao
    monkeypatch.setattr(mao, "retrieval_chain", make_chain(empty_retrieval))

    orchestrator = MultiAgentOrchestrator(model_version="test-model")

    with pytest.raises(RuntimeError):
        await orchestrator.run("test query")


@pytest.mark.asyncio
async def test_fail_fast_on_missing_citations(monkeypatch):
    async def bad_citation_chain_fn(payload: dict):
        return {
            "agent_result": {
                "agent_name": "citation",
                "answer": "text",
                "citations": [],
                "confidence": 0.9,
                "warnings": [],
            },
            "retrieved_chunks": [],
            "timestamp": "2026-01-03T00:00:00",
        }

    from src.orchestrator import multi_agent_orchestrator as mao
    monkeypatch.setattr(mao, "retrieval_chain", make_chain(mock_retrieval_chain_fn))
    monkeypatch.setattr(mao, "citation_chain", make_chain(bad_citation_chain_fn))

    orchestrator = MultiAgentOrchestrator(model_version="test-model")

    with pytest.raises(RuntimeError):
        await orchestrator.run("test query")
