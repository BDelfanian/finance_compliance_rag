"""Reuses dora_validate_chunks's validation logic (article boundary, article
ordering, OJ-noise-removal checks) unchanged — see gdpr_parser.py for why
GDPR and DORA share the same structural pattern.
"""
from pathlib import Path

from src.chunking.dora.dora_validate_chunks import run_validation as _run_validation


def run_validation(json_path: Path):
    _run_validation(json_path, document_id_prefix="gdpr", label="GDPR")
