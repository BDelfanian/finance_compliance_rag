"""
Cost/usage tracking (roadmap §3.6 "Cost/usage tracking").

Mirrors `logging_config.py`'s trace_id contextvar pattern rather than
threading a usage dict through every agent's return shape: the two real
OpenAI call sites (`embed_batch` in run_embeddings_retrieval.py, `llm_call`
in citation_bound_answer_generation.py) record usage as they happen via
`record_usage()`; the orchestrator opens one `usage_scope()` per query and
reads back everything accumulated during it.

Usage:
    with usage_scope():
        ...  # anything that calls record_usage() during this block
    summary = summarize(all_usage())
"""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, List, Optional, TypedDict

from src.config import get_settings

settings = get_settings()


class UsageRecord(TypedDict):
    model: str
    prompt_tokens: int
    completion_tokens: int
    embedding_tokens: int


_usage_ctx: ContextVar[Optional[List[UsageRecord]]] = ContextVar("token_usage", default=None)


@contextmanager
def usage_scope() -> Iterator[None]:
    """
    Bind a fresh usage-record list to the current context for the duration
    of the block. Safe across asyncio.gather() the same way trace_id_scope
    is (each gathered Task captures the context at creation time).
    """
    token = _usage_ctx.set([])
    try:
        yield
    finally:
        _usage_ctx.reset(token)


def record_usage(
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    embedding_tokens: int = 0,
) -> None:
    """
    Record one OpenAI call's token usage. No-ops outside an active
    usage_scope() (e.g. unit tests calling embed_batch/llm_call directly),
    so callers never need to special-case "not tracked here".
    """
    records = _usage_ctx.get()
    if records is None:
        return
    records.append(
        {
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "embedding_tokens": embedding_tokens,
        }
    )


def current_index() -> int:
    """Number of usage records accumulated so far in the active scope (0
    outside a scope) — a marker `usage_since()` can later slice from, used
    to isolate one agent's own usage out of a whole query's total."""
    records = _usage_ctx.get()
    return len(records) if records is not None else 0


def usage_since(start_index: int) -> List[UsageRecord]:
    """Records appended since `start_index` (from an earlier current_index()
    call) — one agent's own usage within a larger query scope."""
    records = _usage_ctx.get()
    if records is None:
        return []
    return records[start_index:]


def all_usage() -> List[UsageRecord]:
    records = _usage_ctx.get()
    return list(records) if records is not None else []


def estimate_cost_usd(records: List[UsageRecord]) -> float:
    """
    Estimated dollar cost of a set of usage records, using
    Settings.token_pricing. Unknown models contribute 0.0 rather than
    raising, since this is a best-effort estimate, not a billing source of
    truth.
    """
    total = 0.0
    for record in records:
        rates = settings.token_pricing.get(record["model"], {})
        total += record["prompt_tokens"] / 1000 * rates.get("prompt", 0.0)
        total += record["completion_tokens"] / 1000 * rates.get("completion", 0.0)
        total += record["embedding_tokens"] / 1000 * rates.get("embedding", 0.0)
    return round(total, 6)


def summarize(records: List[UsageRecord]) -> dict:
    """Aggregate a set of usage records into totals + estimated cost — the
    shape attached to audit_trail.token_usage / logged as MLflow metrics."""
    return {
        "prompt_tokens": sum(r["prompt_tokens"] for r in records),
        "completion_tokens": sum(r["completion_tokens"] for r in records),
        "embedding_tokens": sum(r["embedding_tokens"] for r in records),
        "estimated_cost_usd": estimate_cost_usd(records),
    }
