import json
import re
from pathlib import Path

FOOTER_PATTERNS = [
    r"CIRCULAR CSSF\s+\d+/\d+",
    r"as amended by Circulars"
]

MIN_CHUNK_LENGTH = 100  # minimum number of characters per chunk

def load_chunks(json_path: Path):
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

def validate_chunk_length(chunks):
    for c in chunks:
        if len(c["text"].strip()) < MIN_CHUNK_LENGTH:
            print(f"⚠ Chunk {c['chunk_id']} is too short ({len(c['text'])} chars)")

def validate_footer_removal(chunks):
    for c in chunks:
        for pattern in FOOTER_PATTERNS:
            if re.search(pattern, c["text"]):
                print(f"⚠ Footer found in chunk {c['chunk_id']}")

def validate_section_order(chunks):
    section_ids = [c["section_id"] for c in chunks]
    sorted_sections = sorted(section_ids, key=lambda s: [int(x) for x in s.split(".")])
    if section_ids != sorted_sections:
        print("⚠ Sections are not in proper order")

def validate_no_chapter_4(chunks):
    chapter_4_pattern = re.compile(r"Chapter\s+4\.\s+Date of application", re.IGNORECASE)
    for c in chunks:
        if chapter_4_pattern.search(c["text"]):
            print(f"⚠ Chapter 4 content found in chunk {c['chunk_id']}")

def run_validation(json_path: Path):
    chunks = load_chunks(json_path)
    print(f"Loaded {len(chunks)} chunks for validation.")

    validate_chunk_length(chunks)
    validate_footer_removal(chunks)
    validate_section_order(chunks)
    validate_no_chapter_4(chunks)

    print("✅ Validation complete.")
