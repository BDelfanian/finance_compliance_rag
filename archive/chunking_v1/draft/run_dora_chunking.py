from pathlib import Path

from chunking.dora_cleaning import remove_official_journal_noise
from chunking.dora_parser import build_article_chunks
from chunking.persist_chunks import save_chunks
from chunking.dora_validate_chunks import run_validation


INPUT_PATH = Path("data/processed/extracted_text/dora_regulation.txt")
OUTPUT_PATH = Path("data/processed/chunks/dora_articles.json")


def main():
    raw_text = INPUT_PATH.read_text(encoding="utf-8")

    cleaned = remove_official_journal_noise(raw_text)
    chunks = build_article_chunks(cleaned)

    assert len(chunks) > 0, "❌ No DORA articles detected!"

    save_chunks(chunks, OUTPUT_PATH)
    print(f"✅ Created {len(chunks)} DORA article chunks")

    run_validation(OUTPUT_PATH)


if __name__ == "__main__":
    main()
