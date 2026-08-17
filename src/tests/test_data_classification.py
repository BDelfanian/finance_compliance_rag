"""
Explicit "no confidential data enters the pipeline" check (roadmap §3.6
"Security hardening") — previously only a docs claim
(docs/00_project_overview.md). Scans every indexed chunk's text for
PII-shaped patterns (email, US SSN, credit-card number formats) as an
automated, repeatable proxy for "confidential/personal data", instead of a
one-off manual review that nobody re-runs.

These are real EU regulatory texts, so a genuinely benign match is
plausible (e.g. a regulator's own published institutional contact address)
— any such match must be individually confirmed and allowlisted below with
a stated reason, not silently ignored. A previously-unseen match should be
treated as a real finding: read the surrounding chunk text before deciding
whether to allowlist it.
"""

import glob
import json
import re

import pytest

from src.config import get_settings

settings = get_settings()

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CREDIT_CARD_RE = re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b")

# Confirmed benign: CSSF's own published institutional contact address in
# Circular 22/806 (data/processed/chunks/cssf_22_806_sections.json,
# chunk cssf_22_806_2_1_3) — the regulator's official contact, not a
# private individual's data.
_ALLOWED_EMAIL_MATCHES = {"direction@cssf.lu"}


def _iter_chunks():
    chunk_dir = settings.resolved(settings.chunk_path)
    for path in sorted(glob.glob(str(chunk_dir / "*.json"))):
        chunks = json.loads(open(path, "r", encoding="utf-8").read())
        for chunk in chunks:
            yield path, chunk


def test_no_ssn_or_credit_card_shaped_text_in_indexed_chunks():
    findings = []
    for path, chunk in _iter_chunks():
        text = chunk.get("text", "")
        for pattern, label in ((_SSN_RE, "ssn"), (_CREDIT_CARD_RE, "credit_card")):
            for match in pattern.finditer(text):
                findings.append((label, path, chunk.get("chunk_id"), match.group()))

    assert findings == [], f"Found PII-shaped matches outside the allowlist: {findings}"


def test_email_matches_in_indexed_chunks_are_all_allowlisted():
    unallowed = []
    for path, chunk in _iter_chunks():
        text = chunk.get("text", "")
        for match in _EMAIL_RE.finditer(text):
            if match.group() not in _ALLOWED_EMAIL_MATCHES:
                unallowed.append((path, chunk.get("chunk_id"), match.group()))

    assert unallowed == [], (
        f"Found email-shaped matches not in _ALLOWED_EMAIL_MATCHES: {unallowed}. "
        "Read the surrounding chunk text and either add a justified allowlist "
        "entry or treat this as a real data-classification finding."
    )


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Contact the DPO at jane.doe@example.com for details.", True),
        ("Article 5.2 governs ICT risk management.", False),
    ],
)
def test_email_regex_sanity(text, expected):
    assert bool(_EMAIL_RE.search(text)) is expected
