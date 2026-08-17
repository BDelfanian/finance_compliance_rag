"""
STEP 6.1 — Agent Output Schema
------------------------------
Defines a strict, auditable contract for all STEP 6 agents.
"""

from typing import Any, List, TypedDict


class AgentResult(TypedDict):
    agent_name: str
    answer: str
    # In practice, citation/summarization/risk_assessment agents populate
    # this with chunk *objects* (dicts), not bare strings — only
    # retrieval_agent's own AgentResult uses bare source-reference strings.
    # List[Any] reflects that real, heterogeneous contract rather than
    # asserting a stricter shape nothing actually satisfies — see
    # app/schemas.py's module docstring for the fuller explanation.
    citations: List[Any]
    confidence: float
    warnings: List[str]
