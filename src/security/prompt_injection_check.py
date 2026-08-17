"""
Prompt-injection detection over retrieved chunk text (roadmap §3.6 "Security
hardening"). Retrieved chunks are official regulatory PDFs the team sourced
and reviewed (docs/10 §2's ingestion principle), not arbitrary user input —
but the citation-bound prompt still concatenates their text directly into
the LLM call, so they're treated as untrusted input to that call regardless
of provenance, per the same roadmap item.

This is intentionally non-blocking: a match here is far more likely to be a
PDF-extraction artifact (e.g. a heading that happens to read like an
instruction) than a real attack, given the source is fixed regulatory text
the team controls. Flagging it as a warning keeps it auditable in the risk
assessment output without making the pipeline fail closed on a false
positive.
"""

import re
from typing import List

# Deliberately narrow and literal — broad heuristics (e.g. "ignore" alone)
# would false-positive constantly against real regulatory prose.
_INJECTION_PATTERNS = [
    re.compile(r"ignore (all )?(previous|prior|above) instructions", re.IGNORECASE),
    re.compile(r"disregard (all )?(previous|prior|above) instructions", re.IGNORECASE),
    re.compile(r"^\s*system\s*:", re.IGNORECASE | re.MULTILINE),
    re.compile(r"you are now\b", re.IGNORECASE),
    re.compile(r"new instructions?\s*:", re.IGNORECASE),
    re.compile(r"\bact as\b.{0,30}\b(if|instead)\b", re.IGNORECASE),
]


def scan_chunk_text(chunks: List[dict]) -> bool:
    """
    Returns True if any chunk's text matches an injection-shaped pattern.
    Callers should surface this as a warning, not use it to block the
    request — see the module docstring.
    """
    for chunk in chunks:
        text = chunk.get("text") or ""
        if any(pattern.search(text) for pattern in _INJECTION_PATTERNS):
            return True
    return False
