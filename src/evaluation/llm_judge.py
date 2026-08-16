"""
LLM-judge scoring for generation quality (roadmap §3.6: "faithfulness /
citation-accuracy scoring via an LLM-judge").

RAGAS was considered (it's the roadmap's suggested starting point) but not
adopted: it pulls in `datasets`/`langchain` integrations this project
doesn't otherwise need, its faithfulness metric is tuned for generic QA
rather than "must cite inline as [REGULATION ref]" answers, and a
single-purpose judge prompt against the same OpenAI client already used
elsewhere in the pipeline (`citation_bound_answer_generation.py`) is easy to
reason about and cheap to run per-query. Worth revisiting if eval needs grow
beyond these two scores.
"""

import json
import re
from typing import Any, Dict, List

import openai

from src.config import get_settings

settings = get_settings()

_JUDGE_SYSTEM_PROMPT = (
    "You are an evaluation judge for a regulatory compliance RAG system. "
    "You score a generated answer against the source chunks it was allowed "
    "to use, strictly and skeptically. Respond with ONLY a JSON object, no "
    "prose outside it."
)

_JUDGE_USER_TEMPLATE = """\
Score the generated answer on two dimensions, each 0.0-1.0:

1. faithfulness: does every factual claim in the answer trace back to the
   provided source chunks, with no invented/hallucinated content? A correct
   "Information not available in retrieved sources" response (when the
   chunks don't actually answer the question) scores 1.0.
2. citation_accuracy: for each inline citation the answer makes (formatted
   like "[REGULATION chunk_id / article / paragraph]"), does the cited
   source actually support the adjacent claim? An answer that makes no
   claims needing citation (e.g. a correct "not available" response) scores
   1.0. Missing, fabricated, or mismatched citations score low.

Question:
{query}

Source chunks provided to the model:
{chunks}

Generated answer:
{answer}

Respond with exactly this JSON shape:
{{"faithfulness": <float 0-1>, "citation_accuracy": <float 0-1>, "reasoning": "<1-2 sentences>"}}
"""

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _format_chunks(retrieved_chunks: List[Dict[str, Any]]) -> str:
    if not retrieved_chunks:
        return "(none retrieved)"
    lines = []
    for c in retrieved_chunks:
        ref = c.get("source_reference") or c.get("chunk_id")
        reg = c.get("source_regulation", "")
        text = c.get("text", "")
        lines.append(f"[{reg} {ref}] {text}".strip())
    return "\n".join(lines)


def _parse_judge_response(raw: str) -> Dict[str, Any]:
    match = _JSON_OBJECT_RE.search(raw)
    payload = json.loads(match.group(0) if match else raw)
    return {
        "faithfulness": max(0.0, min(1.0, float(payload.get("faithfulness", 0.0)))),
        "citation_accuracy": max(0.0, min(1.0, float(payload.get("citation_accuracy", 0.0)))),
        "reasoning": str(payload.get("reasoning", "")),
    }


def judge_answer(
    query: str, answer: str, retrieved_chunks: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Calls `settings.eval_judge_model` to score one generated answer.
    Returns {"faithfulness": float, "citation_accuracy": float, "reasoning": str}.
    On a malformed/unparseable judge response, returns zeros with the raw
    text in "reasoning" rather than raising — one bad judge call shouldn't
    crash an eval run over 50 queries.
    """
    prompt = _JUDGE_USER_TEMPLATE.format(
        query=query,
        chunks=_format_chunks(retrieved_chunks),
        answer=answer,
    )

    response = openai.chat.completions.create(
        model=settings.eval_judge_model,
        messages=[
            {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content.strip()

    try:
        return _parse_judge_response(raw)
    except (json.JSONDecodeError, ValueError, AttributeError):
        return {"faithfulness": 0.0, "citation_accuracy": 0.0, "reasoning": f"unparseable judge response: {raw[:200]}"}
