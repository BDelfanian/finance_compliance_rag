"""NIS2 (Directive (EU) 2022/2555) uses the same EU Official Journal noise
format as DORA's main regulation, so remove_official_journal_noise is
reused directly. This adds one NIS2-specific step: truncating the text at
"ANNEX I". The Annexes (sector/entity-type lists) aren't Article-structured
regulatory text in the same sense as the 46 numbered Articles above them,
and — more importantly — the trailing Correlation Table (mapping the
NIS2-repealed Directive (EU) 2016/1148's articles to NIS2's own) contains
rows that start with "Article N" at line start, which produced false-
positive matches against dora_parser's article-boundary regex when tested
against the raw text. Truncating before the Annexes avoids both issues.
"""
import re

from src.chunking.dora.dora_cleaning import remove_official_journal_noise

ANNEX_BOUNDARY = re.compile(r"^ANNEX I$", re.MULTILINE)


def clean_text(text: str) -> str:
    cleaned = remove_official_journal_noise(text)
    match = ANNEX_BOUNDARY.search(cleaned)
    if match:
        cleaned = cleaned[: match.start()].rstrip()
    return cleaned
