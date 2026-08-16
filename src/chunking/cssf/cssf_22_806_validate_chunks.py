"""Reuses cssf_validate_chunks's generic checks (chunk length, footer
removal, section ordering) directly — none of them are 20/750-specific.
`validate_no_chapter_4` is skipped: it checks for a structural quirk
specific to 20/750's own text, not applicable here.
"""
from pathlib import Path

from src.chunking.cssf.cssf_validate_chunks import (
    load_chunks,
    validate_chunk_length,
    validate_footer_removal,
    validate_section_order,
)


def run_validation(json_path: Path):
    chunks = load_chunks(json_path)
    print(f"Loaded {len(chunks)} chunks for validation.")

    validate_chunk_length(chunks)
    validate_footer_removal(chunks)
    validate_section_order(chunks)

    print("✅ Validation complete.")
