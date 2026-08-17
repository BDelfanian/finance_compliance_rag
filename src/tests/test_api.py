"""
FastAPI service tests (app/api.py). Mocks the same module-level agent chains
(src.orchestrator.multi_agent_orchestrator.{retrieval,citation,summarization,
risk_assessment}_chain) that test_orchestrator.py mocks, so these exercise
real HTTP request/response handling and Pydantic validation without
depending on the OpenAI API or FAISS indexes.
"""

import pytest
from fastapi.testclient import TestClient

from app.api import app
from src.orchestrator import multi_agent_orchestrator as mao
from src.orchestrator.langchain_wrappers import make_chain


async def mock_retrieval_chain_fn(inputs: dict):
    return {
        "agent_result": {
            "agent_name": "retrieval",
            "answer": "Retrieved 2 relevant regulatory chunks.",
            "citations": ["REG-1", "REG-2"],
            "confidence": 1.0,
            "warnings": [],
        },
        "retrieved_chunks": [
            {"chunk_id": "c1", "source_reference": "REG-1", "similarity_score": 0.9},
            {"chunk_id": "c2", "source_reference": "REG-2", "similarity_score": 0.8},
        ],
    }


async def mock_citation_chain_fn(payload: dict):
    return {
        "agent_result": {
            "agent_name": "citation",
            "answer": "Regulated entities must disclose X. [REG-1]",
            "citations": [{"chunk_id": "c1", "source_reference": "REG-1", "similarity_score": 0.9}],
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
        "answer": "No material regulatory risks detected.",
        "citations": citation_result["citations"],
        "confidence": 0.7,
        "warnings": [],
    }


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(mao, "retrieval_chain", make_chain(mock_retrieval_chain_fn))
    monkeypatch.setattr(mao, "citation_chain", make_chain(mock_citation_chain_fn))
    monkeypatch.setattr(mao, "summarization_chain", make_chain(mock_summarization_chain_fn))
    monkeypatch.setattr(mao, "risk_assessment_chain", make_chain(mock_risk_chain_fn))
    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "llm_model" in body


def test_query_happy_path_and_audit_lookup(client):
    resp = client.post("/query", json={"query": "What are the ICT governance obligations?"})
    assert resp.status_code == 200
    body = resp.json()

    assert body["answer"]["agent_name"] == "citation"
    assert body["summary"]["agent_name"] == "summarization"
    assert body["risk"]["agent_name"] == "risk_assessment"
    assert body["confidence"] == pytest.approx(0.7)
    assert len(body["sources"]) == 2
    trace_id = body["audit_trail"]["trace_id"]
    assert trace_id

    lookup = client.get(f"/query/{trace_id}")
    assert lookup.status_code == 200
    assert lookup.json()["audit_trail"]["trace_id"] == trace_id


def test_query_unknown_trace_id_404(client):
    resp = client.get("/query/" + "0" * 32)
    assert resp.status_code == 404


def test_query_malformed_trace_id_400(client):
    resp = client.get("/query/../../etc/passwd")
    assert resp.status_code in (400, 404)


def test_query_rejects_empty_query(client):
    resp = client.post("/query", json={"query": ""})
    assert resp.status_code == 422


def test_query_rejects_control_characters(client):
    resp = client.post("/query", json={"query": "What is DORA?\x00malicious"})
    assert resp.status_code == 422


def test_query_rejects_malformed_model_version(client):
    resp = client.post("/query", json={"query": "What is DORA?", "model_version": "gpt-4.1; rm -rf /"})
    assert resp.status_code == 422


def test_query_fail_fast_returns_502(monkeypatch, client):
    async def empty_retrieval(inputs: dict):
        return None

    monkeypatch.setattr(mao, "retrieval_chain", make_chain(empty_retrieval))
    resp = client.post("/query", json={"query": "irrelevant"})
    assert resp.status_code == 502


def test_query_out_of_domain_returns_502_not_500(monkeypatch, client):
    """
    retrieval_agent raises ValueError directly when nothing clears the
    similarity threshold (see src/agents/retrieval_agent.py), rather than
    returning a falsy result for the orchestrator's own `if not
    retrieval_result` fail-fast check to catch — so that check alone never
    actually fires for the real out-of-domain-query case. The API must
    still map this to 502 (pipeline couldn't service a well-formed
    request), not fall through to a generic 500.
    """

    async def no_relevant_chunks(inputs: dict):
        raise ValueError("Retrieval agent returned no relevant chunks")

    monkeypatch.setattr(mao, "retrieval_chain", make_chain(no_relevant_chunks))
    resp = client.post("/query", json={"query": "How do I make sourdough bread?"})
    assert resp.status_code == 502


def test_review_round_trip(client, tmp_path, monkeypatch):
    from src.observability import review_store

    monkeypatch.setattr(review_store.settings, "review_log_path", tmp_path)

    query_resp = client.post("/query", json={"query": "What are the ICT governance obligations?"})
    trace_id = query_resp.json()["audit_trail"]["trace_id"]

    submit = client.post(
        f"/query/{trace_id}/review",
        json={"decision": "approved", "reviewer_name": "Alice", "annotation": "Looks correct."},
    )
    assert submit.status_code == 201
    assert submit.json()["trace_id"] == trace_id

    reviews = client.get(f"/query/{trace_id}/reviews")
    assert reviews.status_code == 200
    body = reviews.json()
    assert len(body) == 1
    assert body[0]["decision"] == "approved"
    assert body[0]["reviewer_name"] == "Alice"


def test_review_unknown_trace_id_404(client):
    resp = client.post(
        "/query/" + "0" * 32 + "/review",
        json={"decision": "approved", "reviewer_name": "Alice"},
    )
    assert resp.status_code == 404


def test_review_malformed_trace_id_400(client):
    resp = client.post(
        "/query/not-a-valid-trace-id/review",
        json={"decision": "approved", "reviewer_name": "Alice"},
    )
    assert resp.status_code == 400


def test_reviews_empty_list_when_none_submitted(client, tmp_path, monkeypatch):
    from src.observability import review_store

    monkeypatch.setattr(review_store.settings, "review_log_path", tmp_path)

    query_resp = client.post("/query", json={"query": "What are the ICT governance obligations?"})
    trace_id = query_resp.json()["audit_trail"]["trace_id"]

    resp = client.get(f"/query/{trace_id}/reviews")
    assert resp.status_code == 200
    assert resp.json() == []


def test_query_stream_emits_stage_events(client):
    with client.stream("POST", "/query/stream", json={"query": "What are the ICT governance obligations?"}) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())

    for stage in ("retrieval", "citation", "summarization", "risk_assessment", "final"):
        assert f"event: {stage}" in body
