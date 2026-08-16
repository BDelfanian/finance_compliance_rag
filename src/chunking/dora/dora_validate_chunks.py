import json
import re
from pathlib import Path

OJ_PATTERNS = [
    r"Official Journal of the European Union",
    r"^L\s+\d+/\d+",
    r"\bEN\b",
]

def load_chunks(json_path: Path):
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

def validate_article_boundary(chunks, document_id_prefix="dora"):
    for c in chunks:
        if c.get("document_id", "").startswith(document_id_prefix):
            if not c["text"].lstrip().startswith(c["article_number"]):
                print(f"⚠ Article boundary mismatch in {c['chunk_id']}")


def validate_article_order(chunks, label="DORA"):
    article_numbers = []

    for c in chunks:
        if "article_number" in c:
            try:
                n = int(c["article_number"].split()[-1])
                article_numbers.append(n)
            except ValueError:
                pass

    if article_numbers != sorted(article_numbers):
        print(f"⚠ {label} articles are not in numeric order")

def validate_oj_removal(chunks):
    for c in chunks:
        for pattern in OJ_PATTERNS:
            if re.search(pattern, c["text"], re.MULTILINE):
                print(f"⚠ Official Journal noise found in {c['chunk_id']}")

def run_validation(json_path: Path, document_id_prefix="dora", label="DORA"):
    chunks = load_chunks(json_path)
    print(f"Loaded {len(chunks)} chunks for validation.")

    validate_article_boundary(chunks, document_id_prefix)
    validate_article_order(chunks, label)
    validate_oj_removal(chunks)

    print("✅ Validation complete.")
