"""
STEP 6.1 — Agent Output Validation
---------------------------------
Fail-fast validation to enforce agent contracts.
"""

from src.orchestrator.agent_schema import AgentResult


def validate_agent_result(result: AgentResult) -> None:
    assert isinstance(result, dict), "Agent result must be a dict"

    required_keys = {
        "agent_name",
        "answer",
        "citations",
        "confidence",
        "warnings",
    }

    missing = required_keys - result.keys()
    if missing:
        raise ValueError(f"Agent result missing keys: {missing}")

    assert isinstance(result["agent_name"], str)
    assert isinstance(result["answer"], str)
    assert isinstance(result["citations"], list)
    assert isinstance(result["confidence"], (float, int))
    assert isinstance(result["warnings"], list)

    assert 0.0 <= float(result["confidence"]) <= 1.0, "Confidence must be between 0 and 1"
