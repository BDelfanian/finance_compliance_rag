from pathlib import Path

from src.chunking.dora.dora_validate_chunks import run_validation as _run_validation


def run_validation(json_path: Path):
    _run_validation(json_path, document_id_prefix="nis2", label="NIS2")
