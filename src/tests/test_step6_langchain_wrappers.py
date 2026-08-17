import pytest

import src.orchestrator.multi_agent_orchestrator as mao
from src.orchestrator import langchain_wrappers as lw


# -------------------------------
# Test 1 — retrieval_chain executes
# -------------------------------
@pytest.mark.asyncio
async def test_retrieval_chain_executes(monkeypatch):
    async def mock_retrieval(query: str):
        return {"mock": True}

    monkeypatch.setattr(lw, "retrieval_chain", lw.make_chain(mock_retrieval))

    result = await lw.retrieval_chain.ainvoke("test query")
    assert result == {"mock": True}


# -------------------------------
# Test 2 — citation_chain payload
# -------------------------------
@pytest.mark.asyncio
async def test_citation_chain_payload(monkeypatch):
    async def mock_citation(query: str, retrieval_result: dict):
        return {
            "agent_result": {
                "agent_name": "citation",
                "answer": "ok",
                "citations": ["REG-1"],
                "confidence": 0.9,
                "warnings": [],
            }
        }

    # Wrap the mock in a RunnableLambda using helper
    monkeypatch.setattr(lw, "citation_chain", lw.make_chain(lambda p: mock_citation(p["query"], p["retrieval_result"])))

    payload = {"query": "test", "retrieval_result": {"documents": []}}
    result = await lw.citation_chain.ainvoke(payload)

    assert result["agent_result"]["agent_name"] == "citation"


# -------------------------------
# Test 3 — MultiAgentOrchestrator with LangChain mocks
# -------------------------------
@pytest.mark.asyncio
async def test_orchestrator_with_langchain(monkeypatch):
    async def mock_retrieval(query):
        return {"documents": ["doc"]}

    async def mock_citation(query, retrieval_result):
        return {
            "agent_result": {
                "agent_name": "citation",
                "answer": "answer",
                "citations": ["REG-1"],
                "confidence": 0.8,
                "warnings": [],
            }
        }

    async def mock_summary(payload):
        return {
            "agent_name": "summarization",
            "answer": "summary",
            "citations": ["REG-1"],
            "confidence": 0.7,
            "warnings": [],
        }

    async def mock_risk(payload):
        return {
            "agent_name": "risk_assessment",
            "answer": "ok",
            "citations": ["REG-1"],
            "confidence": 0.6,
            "warnings": [],
        }

    # Patch chains where MultiAgentOrchestrator actually imports them
    monkeypatch.setattr(mao, "retrieval_chain", lw.make_chain(mock_retrieval))
    monkeypatch.setattr(
        mao, "citation_chain", lw.make_chain(lambda p: mock_citation(p["query"], p["retrieval_result"]))
    )
    monkeypatch.setattr(mao, "summarization_chain", lw.make_chain(mock_summary))
    monkeypatch.setattr(mao, "risk_assessment_chain", lw.make_chain(mock_risk))

    orchestrator = mao.MultiAgentOrchestrator(model_version="test")
    result = await orchestrator.run("test query")

    assert "answer" in result
    assert "summary" in result
    assert "risk" in result
    assert result["confidence"] == 0.6
