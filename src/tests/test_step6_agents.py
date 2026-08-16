"""
STEP 6 — Comprehensive Agent Tests
----------------------------------
Pytest-based validation for all Step 6 agents and orchestrator.

Tests included:
- Retrieval agent
- Citation agent
- Summarization agent
- Risk assessment agent
- Multi-agent orchestrator

Uses fixtures and monkeypatching to avoid dependence on LLMs or vector stores.
"""

import pytest
import asyncio

from src.agents import retrieval_agent as ra
from src.agents import citation_agent as ca
from src.agents import summarization_agent as sa
from src.agents import risk_assessment_agent as risk
from src.orchestrator.multi_agent_orchestrator import MultiAgentOrchestrator
from src.orchestrator.agent_validation import validate_agent_result
from src.orchestrator.langchain_wrappers import make_chain


# -------------------------------
# Fixtures
# -------------------------------

@pytest.fixture
def retrieval_result_fixture():
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


@pytest.fixture
def citation_result_fixture():
    return {
        "answer": (
            "- The management body bears ultimate responsibility for ICT risk "
            "and must establish an internal governance and control framework. "
            "- It must approve and oversee ICT strategies, policies, and risk "
            "management arrangements, including business continuity. "
            "- Adequate resources, skills, and training must be ensured."
        ),
        "citations": [
            {"source_reference": "REG-1", "excerpt": "Sample regulation text"},
            {"source_reference": "REG-2", "excerpt": "Another regulation"},
        ],
        "confidence": 0.72,
        "timestamp": "2026-01-03T00:00:00"
    }


# -------------------------------
# Retrieval Agent Tests
# -------------------------------

@pytest.mark.asyncio
async def test_retrieval_agent_returns_documents(monkeypatch):
    # Patch underlying retrieval function
    monkeypatch.setattr(
        "src.agents.retrieval_agent.retrieve",
        lambda query_text, vector_store_key: {
            "retrieved_chunks": [{"source_reference": f"{vector_store_key}-1", "text": "chunk text"}]
        }
    )

    result = await ra.retrieval_agent("test query")

    assert "agent_result" in result
    assert "retrieved_chunks" in result
    assert len(result["retrieved_chunks"]) == 3
    assert result["agent_result"]["agent_name"] == "retrieval"


@pytest.mark.asyncio
async def test_retrieval_agent_no_results(monkeypatch):
    monkeypatch.setattr(
        "src.agents.retrieval_agent.retrieve",
        lambda query_text, vector_store_key: {"retrieved_chunks": []}
    )

    with pytest.raises(ValueError):
        await ra.retrieval_agent("test query")


# -------------------------------
# Citation Agent Tests
# -------------------------------

@pytest.mark.asyncio
async def test_citation_agent_returns_structured_output(monkeypatch):
    # Patch cached generation. Answer text cites REG-1 inline but not REG-2,
    # so citations must come back as only the cited subset while
    # retrieved_chunks (top-level) keeps the full set.
    monkeypatch.setattr(
        "src.agents.citation_agent.generate_citation_bound_answer_cached",
        lambda query_text, top_k=5: {
            "answer": "Entities must disclose X [REG-1].",
            "retrieved_chunks": [
                {"source_reference": "REG-1", "excerpt": "Test chunk"},
                {"source_reference": "REG-2", "excerpt": "Unused chunk"},
            ],
            "answer_confidence": 0.8,
            "timestamp": "2026-01-03T00:00:00"
        }
    )

    result = await ca.citation_agent("test query", {"retrieved_chunks": []})
    agent_result = result["agent_result"]

    assert agent_result["answer"] == "Entities must disclose X [REG-1]."
    assert [c["source_reference"] for c in agent_result["citations"]] == ["REG-1"]
    assert agent_result["confidence"] == 0.8
    assert "timestamp" in result  # timestamp is still top-level
    assert len(result["retrieved_chunks"]) == 2  # full retrieved set preserved


@pytest.mark.asyncio
async def test_citation_agent_no_citations_when_answer_uses_none(monkeypatch):
    # A correct "no answer found" response cites nothing — that must produce
    # an empty citations list, not the full retrieved set.
    monkeypatch.setattr(
        "src.agents.citation_agent.generate_citation_bound_answer_cached",
        lambda query_text, top_k=5: {
            "answer": "Information not available in retrieved sources.",
            "retrieved_chunks": [{"source_reference": "REG-1", "excerpt": "chunk"}],
            "answer_confidence": 0.3,
            "timestamp": "2026-01-03T00:00:00"
        }
    )

    result = await ca.citation_agent("test query", {"retrieved_chunks": []})
    agent_result = result["agent_result"]

    assert agent_result["citations"] == []
    assert len(result["retrieved_chunks"]) == 1


# -------------------------------
# Summarization Agent Tests
# -------------------------------

@pytest.mark.asyncio
async def test_summarization_executive_mode(citation_result_fixture):
    result = await sa.summarization_agent(
        citation_result=citation_result_fixture,
        mode="executive"
    )
    validate_agent_result(result)
    assert "-" not in result["answer"]
    assert len(result["answer"].split(".")) <= 3
    assert result["confidence"] <= citation_result_fixture["confidence"]


@pytest.mark.asyncio
async def test_summarization_audit_mode(citation_result_fixture):
    result = await sa.summarization_agent(
        citation_result=citation_result_fixture,
        mode="audit"
    )
    validate_agent_result(result)
    assert len(result["answer"].split(".")) <= 5
    assert result["confidence"] <= citation_result_fixture["confidence"]


@pytest.mark.asyncio
async def test_summarization_missing_answer():
    result = await sa.summarization_agent(
        citation_result={
            "answer": "",
            "citations": [],
            "confidence": 0.5,
        }
    )
    validate_agent_result(result)
    assert "unavailable" in result["answer"].lower()
    assert result["confidence"] == 0.0
    assert len(result["warnings"]) > 0


@pytest.mark.asyncio
async def test_summarization_invalid_mode(citation_result_fixture):
    with pytest.raises(ValueError):
        await sa.summarization_agent(
            citation_result=citation_result_fixture,
            mode="marketing"
        )


# -------------------------------
# Risk Assessment Agent Tests
# -------------------------------

@pytest.mark.asyncio
async def test_risk_agent_low_confidence(citation_result_fixture, retrieval_result_fixture):
    # Reduce confidence to trigger low-confidence warning
    low_conf_citation = citation_result_fixture.copy()
    low_conf_citation["confidence"] = 0.5

    result = await risk.risk_assessment_agent(
        citation_result=low_conf_citation,
        retrieval_result=retrieval_result_fixture
    )

    assert "low" in " ".join(result["warnings"]).lower()
    assert result["confidence"] < 0.5


@pytest.mark.asyncio
async def test_risk_agent_partial_coverage(citation_result_fixture, retrieval_result_fixture):
    # Remove one citation to trigger coverage warning
    citation_copy = citation_result_fixture.copy()
    citation_copy["citations"] = [citation_copy["citations"][0]]

    result = await risk.risk_assessment_agent(
        citation_result=citation_copy,
        retrieval_result=retrieval_result_fixture
    )

    assert "partial" in " ".join(result["warnings"]).lower()


# -------------------------------
# Orchestrator Tests
# -------------------------------

@pytest.fixture
def orchestrator(monkeypatch):
    # Mock the LangChain-wrapped chains the orchestrator actually calls
    # (retrieval_chain / citation_chain / summarization_chain / risk_assessment_chain),
    # not the raw agent functions — MultiAgentOrchestrator.run() invokes chains,
    # each of which .ainvoke()s a single positional input.
    async def mock_retrieval_chain_fn(query: str):
        return {
            "agent_result": {"agent_name": "retrieval", "answer": "mock", "citations": [], "confidence": 1.0, "warnings": []},
            "retrieved_chunks": [{"source_reference": "REG-1", "text": "chunk"}]
        }

    async def mock_citation_chain_fn(payload: dict):
        return {
            "agent_result": {
                "agent_name": "citation",
                "answer": "Mock citation answer",
                "citations": [{"source_reference": "REG-1", "excerpt": "chunk"}],
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
            "answer": "Mock summary",
            "citations": citation_result["citations"],
            "confidence": 0.75,
            "warnings": []
        }

    async def mock_risk_chain_fn(payload: dict):
        citation_result = payload["citation_result"]
        return {
            "agent_name": "risk_assessment",
            "answer": "Partial regulatory coverage detected.",
            "citations": citation_result["citations"],
            "confidence": 0.6,
            "warnings": ["Partial regulatory coverage"]
        }

    from src.orchestrator import multi_agent_orchestrator as mao
    monkeypatch.setattr(mao, "retrieval_chain", make_chain(mock_retrieval_chain_fn))
    monkeypatch.setattr(mao, "citation_chain", make_chain(mock_citation_chain_fn))
    monkeypatch.setattr(mao, "summarization_chain", make_chain(mock_summarization_chain_fn))
    monkeypatch.setattr(mao, "risk_assessment_chain", make_chain(mock_risk_chain_fn))

    return MultiAgentOrchestrator(model_version="test-model")


@pytest.mark.asyncio
async def test_orchestrator_happy_path(orchestrator):
    result = await orchestrator.run("test query")
    assert "answer" in result
    assert "summary" in result
    assert "risk" in result
    assert "audit_trail" in result
    assert result["confidence"] <= 0.6


@pytest.mark.asyncio
async def test_orchestrator_fail_fast_missing_retrieval(monkeypatch):
    async def empty_retrieval(query: str):
        return None

    from src.orchestrator import multi_agent_orchestrator as mao
    monkeypatch.setattr(mao, "retrieval_chain", make_chain(empty_retrieval))

    orchestrator = MultiAgentOrchestrator(model_version="test-model")

    with pytest.raises(RuntimeError):
        await orchestrator.run("test query")


@pytest.mark.asyncio
async def test_orchestrator_fail_fast_missing_citation_answer(monkeypatch):
    # "citations" now means "what the LLM cited", so an empty citations list
    # alone is a legitimate outcome, not a failure signal — the orchestrator
    # must instead gate on the citation agent failing to produce an answer.
    async def mock_retrieval_chain_fn(query: str):
        return {
            "agent_result": {"agent_name": "retrieval", "answer": "mock", "citations": [], "confidence": 1.0, "warnings": []},
            "retrieved_chunks": [{"source_reference": "REG-1", "text": "chunk"}]
        }

    async def bad_citation_chain_fn(payload: dict):
        return {
            "agent_result": {
                "agent_name": "citation",
                "answer": "",
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

    orchestrator_instance = MultiAgentOrchestrator(model_version="test-model")

    with pytest.raises(RuntimeError):
        await orchestrator_instance.run("test query")
