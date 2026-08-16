"""
Pydantic request/response models for `app/api.py`, mirroring
`src/orchestrator/agent_schema.py`'s `AgentResult` and the aggregated dict
`MultiAgentOrchestrator.run()` returns.

`AgentResult` is a plain TypedDict typed as `citations: List[str]`, but in
practice the citation/summarization/risk_assessment agents all populate
`citations` with the *chunk objects* a citation was resolved against (see
`citation_agent._extract_cited_chunks`), not bare strings — only
`retrieval_agent`'s own (internal, never returned by the orchestrator)
`AgentResult` uses bare source-reference strings. `Citation` below models the
chunk-object shape actually returned to API clients; fields are optional
because the two upstream producers of this shape
(`citation_bound_answer_generation.py` and `run_embeddings_retrieval.py`)
don't populate identical field sets.
"""

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    model_version: Optional[str] = Field(
        default=None,
        description="Overrides Settings.model_version for this request only.",
    )


class Citation(BaseModel):
    chunk_id: Optional[str] = None
    source_reference: Optional[str] = None
    source_regulation: Optional[str] = None
    similarity_score: Optional[float] = None
    excerpt: Optional[str] = None

    model_config = {"extra": "allow"}


class AgentResultResponse(BaseModel):
    agent_name: str
    answer: str
    citations: List[Citation] = []
    confidence: float
    warnings: List[str] = []


class AuditTrail(BaseModel):
    trace_id: str
    query: str
    model_version: str
    agents: List[str]
    timestamp: str


class QueryResponse(BaseModel):
    answer: AgentResultResponse
    summary: AgentResultResponse
    risk: AgentResultResponse
    confidence: float
    sources: List[Citation] = []
    audit_trail: AuditTrail


class HealthResponse(BaseModel):
    status: str
    model_version: str
    llm_model: str
    mlflow_tracking_uri: Optional[str] = None


class ErrorResponse(BaseModel):
    detail: str
    trace_id: Optional[str] = None
