"""
Retrieval quality metrics against `src/tests/golden_queries.json` (roadmap
§3.6 evaluation framework).

Both metrics return `None` for "no_answer" golden cases (empty
`expected_chunk_ids`) — precision/MRR aren't meaningful when the correct
retrieval outcome is "nothing." Those cases are scored separately by
`abstention_correct` in `run_eval.py`.
"""

from typing import List, Optional, Sequence


def precision_at_k(retrieved_ids: Sequence[str], expected_ids: Sequence[str]) -> Optional[float]:
    """Fraction of retrieved chunks (already capped at top_k by `retrieve()`)
    that are relevant, i.e. appear in `expected_ids`."""
    if not expected_ids:
        return None
    if not retrieved_ids:
        return 0.0
    relevant = sum(1 for rid in retrieved_ids if rid in expected_ids)
    return relevant / len(retrieved_ids)


def reciprocal_rank(retrieved_ids: Sequence[str], expected_ids: Sequence[str]) -> Optional[float]:
    """1 / rank of the first relevant chunk in `retrieved_ids` (1-indexed),
    or 0.0 if none of the expected chunks were retrieved."""
    if not expected_ids:
        return None
    for rank, rid in enumerate(retrieved_ids, start=1):
        if rid in expected_ids:
            return 1.0 / rank
    return 0.0


def mean(values: List[Optional[float]]) -> Optional[float]:
    present = [v for v in values if v is not None]
    if not present:
        return None
    return sum(present) / len(present)
