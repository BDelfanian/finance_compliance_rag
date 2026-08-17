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

import re
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# Control characters (excluding \t \n \r, which are legitimate in free-text
# queries) — a null byte or other control char in a query string has no
# legitimate use here and is a classic injection/smuggling probe (roadmap
# §3.6 "Security hardening": input validation on the API).
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# model_version flows into MultiAgentOrchestrator, MLflow run tags, and
# structured logs — constrained to the shape a real version string actually
# takes, not left as arbitrary free text.
_MODEL_VERSION_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    model_version: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Overrides Settings.model_version for this request only.",
    )

    @field_validator("query")
    @classmethod
    def _reject_control_characters(cls, value: str) -> str:
        if _CONTROL_CHARS_RE.search(value):
            raise ValueError("query must not contain control characters")
        return value

    @field_validator("model_version")
    @classmethod
    def _validate_model_version_shape(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not _MODEL_VERSION_RE.match(value):
            raise ValueError("model_version may only contain letters, digits, '.', '_', and '-'")
        return value


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


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    embedding_tokens: int = 0


class AuditTrail(BaseModel):
    trace_id: str
    query: str
    model_version: str
    agents: List[str]
    timestamp: str
    token_usage: Optional[TokenUsage] = None
    estimated_cost_usd: Optional[float] = None


class QueryResponse(BaseModel):
    answer: AgentResultResponse
    summary: AgentResultResponse
    risk: AgentResultResponse
    confidence: float
    sources: List[Citation] = []
    audit_trail: AuditTrail


class ReviewRequest(BaseModel):
    """Human-in-the-loop approve/reject/annotate action on a completed run
    (roadmap §3.6) — doubles as the per-answer compliance sign-off record
    docs/06 §4.10 calls for. `reviewer_name` is self-reported free text:
    this app has no auth/user-identity system, a deliberate, documented
    limitation (see docs/09), not an oversight."""

    decision: Literal["approved", "rejected"]
    reviewer_name: str = Field(..., min_length=1, max_length=200)
    reviewer_role: Optional[str] = Field(default=None, max_length=100)
    annotation: Optional[str] = Field(default=None, max_length=4000)


class ReviewRecord(ReviewRequest):
    trace_id: str
    timestamp: str


class HealthResponse(BaseModel):
    status: str
    model_version: str
    llm_model: str
    mlflow_tracking_uri: Optional[str] = None


class ErrorResponse(BaseModel):
    detail: str
    trace_id: Optional[str] = None
