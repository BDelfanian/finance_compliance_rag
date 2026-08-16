from pathlib import Path

from chunking.eba_cleaning import remove_eba_noise
from chunking.eba_parser import build_paragraph_chunks
from chunking.persist_chunks import save_chunks
from chunking.eba_validate_chunks import run_validation


INPUT_PATH = Path("data/processed/extracted_text/eba_outsourcing_guidelines.txt")
OUTPUT_PATH = Path("data/processed/chunks/eba_outsourcing_paragraphs.json")


def main():
    raw_text = INPUT_PATH.read_text(encoding="utf-8")

    cleaned = remove_eba_noise(raw_text)
    chunks = build_paragraph_chunks(cleaned)

    assert len(chunks) > 0, "❌ No EBA paragraphs detected!"

    save_chunks(chunks, OUTPUT_PATH)
    print(f"✅ Created {len(chunks)} EBA paragraph chunks")

    run_validation(OUTPUT_PATH)


if __name__ == "__main__":
    main()
