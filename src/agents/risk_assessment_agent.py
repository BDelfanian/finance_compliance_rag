"""
STEP 6 — Risk Assessment Agent
-----------------------------
Evaluates regulatory risk, ambiguity, and coverage gaps
based strictly on retrieved sources and citation-bound answers.

Design constraints:
- NO new regulatory facts
- NO hallucinated obligations
- Explicit uncertainty handling
- Confidence is a first-class output
"""

from typing import Any, Dict, List

from src.orchestrator.agent_schema import AgentResult
from src.orchestrator.agent_validation import validate_agent_result

# -------------------------------
# Heuristic risk signals
# -------------------------------
LOW_CONFIDENCE_THRESHOLD = 0.6
MIN_CITATIONS_REQUIRED = 1


# -------------------------------
# Risk Assessment Agent
# -------------------------------
async def risk_assessment_agent(
    citation_result: Dict[str, Any],
    retrieval_result: Dict[str, Any],
) -> AgentResult:
    """
    Analyze regulatory risk and uncertainty.

    Inputs:
    - citation_result: output from STEP 5 citation agent
    - retrieval_result: retrieved regulation chunks (STEP 4)

    Output:
    - Validated AgentResult with warnings and confidence
    """

    warnings: List[str] = []
    risk_statements: List[str] = []

    # -------------------------------
    # 1. Citation coverage checks
    # -------------------------------
    citations = citation_result.get("citations", [])

    if len(citations) < MIN_CITATIONS_REQUIRED:
        warnings.append("Insufficient regulatory citations")
        risk_statements.append("Answer may not be fully supported by authoritative regulatory sources.")

    # -------------------------------
    # 2. Retrieval vs answer alignment
    # -------------------------------
    retrieved_sources = {
        chunk.get("source_reference")
        for chunk in retrieval_result.get("retrieved_chunks", [])
        if chunk.get("source_reference")
    }

    cited_sources = {citation.get("source_reference") for citation in citations if citation.get("source_reference")}

    uncovered_sources = retrieved_sources - cited_sources

    if uncovered_sources:
        warnings.append("Partial regulatory coverage")
        risk_statements.append("Some retrieved regulatory sources were not addressed in the final answer.")

    # -------------------------------
    # 3. Confidence-based risk signals
    # -------------------------------
    base_confidence = float(citation_result.get("confidence", 0.0))

    if base_confidence < LOW_CONFIDENCE_THRESHOLD:
        warnings.append("Low model confidence")
        risk_statements.append("The generated answer exhibits low confidence and may require manual review.")

    # -------------------------------
    # 4. Risk-adjusted confidence
    # -------------------------------
    risk_confidence = base_confidence
    if warnings:
        # Penalize confidence conservatively
        risk_confidence *= max(0.5, 1 - 0.1 * len(warnings))

    risk_confidence = round(min(max(risk_confidence, 0.0), 1.0), 3)

    # -------------------------------
    # 5. Structured AgentResult output
    # -------------------------------
    agent_result: AgentResult = {
        "agent_name": "risk_assessment",
        "answer": " ".join(risk_statements)
        if risk_statements
        else "No material regulatory risks detected based on available sources.",
        "citations": citations,  # pass-through for traceability
        "confidence": risk_confidence,
        "warnings": warnings,
    }

    validate_agent_result(agent_result)

    return agent_result
