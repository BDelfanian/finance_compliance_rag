import pytest

from src.observability import review_store


def _trace_id(n: int) -> str:
    return f"{n:032d}"


def test_load_reviews_empty_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(review_store.settings, "review_log_path", tmp_path)
    assert review_store.load_reviews(_trace_id(1)) == []


def test_append_and_load_reviews_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(review_store.settings, "review_log_path", tmp_path)
    trace_id = _trace_id(2)

    review_store.append_review(trace_id, {"decision": "approved", "reviewer_name": "Alice"})
    review_store.append_review(trace_id, {"decision": "rejected", "reviewer_name": "Bob"})

    reviews = review_store.load_reviews(trace_id)
    assert len(reviews) == 2
    assert reviews[0]["reviewer_name"] == "Alice"
    assert reviews[1]["decision"] == "rejected"


def test_invalid_trace_id_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(review_store.settings, "review_log_path", tmp_path)
    with pytest.raises(ValueError):
        review_store.append_review("../../etc/passwd", {"decision": "approved"})
