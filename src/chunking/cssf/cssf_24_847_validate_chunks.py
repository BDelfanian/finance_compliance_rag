import json
import re
from pathlib import Path

NOISE_PATTERNS = [
    r"^CIRCULAR CSSF\s+\d+/\d+",
    r"^\d+/\d+$",
]

MIN_CHUNK_LENGTH = 20  # short but real paragraphs exist (e.g. single-sentence obligations)


def load_chunks(json_path: Path):
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_chunk_length(chunks):
    for c in chunks:
        if len(c["text"].strip()) < MIN_CHUNK_LENGTH:
            print(f"⚠ Chunk {c['chunk_id']} is too short ({len(c['text'])} chars)")


def validate_noise_removal(chunks):
    for c in chunks:
        for pattern in NOISE_PATTERNS:
            if re.search(pattern, c["text"], re.MULTILINE):
                print(f"⚠ Page noise found in chunk {c['chunk_id']}")


def validate_no_duplicate_paragraph_numbers(chunks):
    seen = set()
    for c in chunks:
        para_no = c.get("paragraph_number")
        if para_no in seen:
            print(f"⚠ Duplicate paragraph number {para_no} in {c['chunk_id']}")
        seen.add(para_no)


def validate_paragraph_order(chunks):
    numbers = [int(c["paragraph_number"]) for c in chunks]
    if numbers != sorted(numbers):
        print("⚠ CSSF 24/847 paragraphs are not in numeric order")


def run_validation(json_path: Path):
    chunks = load_chunks(json_path)
    print(f"Loaded {len(chunks)} chunks for validation.")

    validate_chunk_length(chunks)
    validate_noise_removal(chunks)
    validate_no_duplicate_paragraph_numbers(chunks)
    validate_paragraph_order(chunks)

    print("✅ Validation complete.")
