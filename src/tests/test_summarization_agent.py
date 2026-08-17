import pytest

from src.agents.summarization_agent import summarization_agent
from src.orchestrator.agent_validation import validate_agent_result

# -------------------------------
# Fixtures
# -------------------------------


@pytest.fixture
def citation_result_fixture():
    """
    Representative STEP 5 output (frozen, deterministic)
    """
    return {
        "answer": (
            "- The management body bears ultimate responsibility for ICT risk "
            "and must establish an internal governance and control framework. "
            "- It must approve and oversee ICT strategies, policies, and risk "
            "management arrangements, including business continuity. "
            "- Adequate resources, skills, and training must be ensured."
        ),
        "citations": [
            "DORA Article 5 / 2",
            "CSSF 3.2.1 / 2-4",
        ],
        "confidence": 0.72,
    }


# -------------------------------
# Tests
# -------------------------------


@pytest.mark.asyncio
async def test_summarization_executive_mode(citation_result_fixture):
    """
    Executive summary:
    - Short
    - Compressed
    - No bullets
    """

    result = await summarization_agent(
        citation_result=citation_result_fixture,
        mode="executive",
    )

    # Schema validation
    validate_agent_result(result)

    assert result["agent_name"] == "summarization"
    assert isinstance(result["answer"], str)
    assert len(result["answer"]) > 0

    # Must not contain bullets
    assert "-" not in result["answer"]

    # Executive summary should be concise
    assert len(result["answer"].split(".")) <= 3

    # Confidence rules
    assert result["confidence"] <= citation_result_fixture["confidence"]
    assert result["confidence"] <= 0.95

    assert result["warnings"] == []


@pytest.mark.asyncio
async def test_summarization_audit_mode(citation_result_fixture):
    """
    Audit summary:
    - Slightly longer
    - Still compressed
    """

    result = await summarization_agent(
        citation_result=citation_result_fixture,
        mode="audit",
    )

    validate_agent_result(result)

    # Audit mode may include more detail
    assert len(result["answer"].split(".")) <= 5
    assert result["confidence"] <= citation_result_fixture["confidence"]


@pytest.mark.asyncio
async def test_missing_answer_handling():
    """
    Missing STEP 5 answer must fail gracefully.
    """

    result = await summarization_agent(
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
async def test_invalid_mode_rejected(citation_result_fixture):
    """
    Unsupported summarization modes must fail fast.
    """

    with pytest.raises(ValueError):
        await summarization_agent(
            citation_result=citation_result_fixture,
            mode="marketing",  # invalid
        )
