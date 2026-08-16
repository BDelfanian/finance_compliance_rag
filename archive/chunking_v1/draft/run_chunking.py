from pathlib import Path
from chunking.cleaning import clean_text
from chunking.chunk_builder import build_section_chunks
from chunking.persist import save_chunks
from chunking.validate_chunks import run_validation

INPUT_PATH = Path("data/processed/extracted_text/cssf_circular_20_750.txt")
OUTPUT_PATH = Path("data/processed/chunks/cssf_circular_20_750_sections.json")

def main():
    text = INPUT_PATH.read_text(encoding="utf-8")

    cleaned = clean_text(text)
    chunks = build_section_chunks(cleaned)

    assert len(chunks) > 0, "❌ No chunks created!"

    save_chunks(chunks, OUTPUT_PATH)

    print(f"✅ Created {len(chunks)} section chunks")

    run_validation(OUTPUT_PATH)

if __name__ == "__main__":
    main()
