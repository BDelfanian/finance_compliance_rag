"""
Cost/usage tracking (roadmap §3.6). Pure unit tests against the contextvar
accumulator — no OpenAI calls.
"""

from src.observability.cost_tracking import (
    all_usage,
    current_index,
    estimate_cost_usd,
    record_usage,
    summarize,
    usage_scope,
    usage_since,
)


def test_record_usage_noop_outside_scope():
    record_usage(model="gpt-5-mini", prompt_tokens=10, completion_tokens=5)
    assert all_usage() == []


def test_usage_scope_accumulates_records():
    with usage_scope():
        record_usage(model="gpt-5-mini", prompt_tokens=100, completion_tokens=50)
        record_usage(model="text-embedding-3-small", embedding_tokens=20)
        records = all_usage()

    assert len(records) == 2
    assert records[0]["prompt_tokens"] == 100
    assert records[1]["embedding_tokens"] == 20
    # Outside the scope again, the accumulator is gone.
    assert all_usage() == []


def test_usage_since_isolates_one_agent_within_a_query():
    with usage_scope():
        record_usage(model="text-embedding-3-small", embedding_tokens=20)
        start = current_index()
        record_usage(model="gpt-5-mini", prompt_tokens=200, completion_tokens=100)
        this_agent_only = usage_since(start)

    assert len(this_agent_only) == 1
    assert this_agent_only[0]["prompt_tokens"] == 200


def test_estimate_cost_uses_configured_pricing():
    records = [
        {"model": "gpt-5-mini", "prompt_tokens": 1000, "completion_tokens": 1000, "embedding_tokens": 0},
    ]
    # 1000 prompt @ $0.00025/1K + 1000 completion @ $0.002/1K = 0.00025 + 0.002
    assert estimate_cost_usd(records) == round(0.00025 + 0.002, 6)


def test_estimate_cost_unknown_model_is_zero():
    records = [{"model": "some-unpriced-model", "prompt_tokens": 1000, "completion_tokens": 0, "embedding_tokens": 0}]
    assert estimate_cost_usd(records) == 0.0


def test_summarize_aggregates_totals_and_cost():
    records = [
        {"model": "text-embedding-3-small", "prompt_tokens": 0, "completion_tokens": 0, "embedding_tokens": 500},
        {"model": "gpt-5-mini", "prompt_tokens": 300, "completion_tokens": 100, "embedding_tokens": 0},
    ]
    summary = summarize(records)
    assert summary["prompt_tokens"] == 300
    assert summary["completion_tokens"] == 100
    assert summary["embedding_tokens"] == 500
    assert summary["estimated_cost_usd"] > 0
