"""
File-based human-in-the-loop review store, keyed by trace_id (roadmap §3.6
"Human-in-the-loop review workflow"). Structurally mirrors `audit_store.py`:
one JSON file per trace_id, same rebuildable/non-source `.gitignore` pattern
— but holds a *list* of review records, since a trace_id can legitimately be
reviewed more than once (e.g. reviewed, then re-reviewed after discussion),
unlike the audit store's one-record-per-trace_id shape.

Doubles as the compliance sign-off record docs/06_retrieval_design.md §4.10
(Model Risk Management Sign-Off) calls for, applied per-answer rather than
per-document-version. There is no auth anywhere in this app today (no
login, no user identity) — `reviewer_name` is self-reported free text, the
same trust model as the rest of this prototype; that limitation is
deliberate, not an oversight, see docs/09.

`trace_id` is attacker-controlled input on the API boundary
(`POST /query/{trace_id}/review`, `GET /query/{trace_id}/reviews`), so
callers MUST validate it against `TRACE_ID_RE` before calling into this
module — same convention as `audit_store.py`.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from src.config import get_settings
from src.observability.audit_store import TRACE_ID_RE

settings = get_settings()

__all__ = ["TRACE_ID_RE", "append_review", "load_reviews"]


def _path_for(trace_id: str) -> Path:
    if not TRACE_ID_RE.match(trace_id):
        raise ValueError(f"Invalid trace_id: {trace_id!r}")
    root = settings.resolved(settings.review_log_path)
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{trace_id}.json"


def load_reviews(trace_id: str) -> List[Dict[str, Any]]:
    path = _path_for(trace_id)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def append_review(trace_id: str, record: Dict[str, Any]) -> None:
    reviews = load_reviews(trace_id)
    reviews.append(record)
    _path_for(trace_id).write_text(json.dumps(reviews, default=str, indent=2), encoding="utf-8")
