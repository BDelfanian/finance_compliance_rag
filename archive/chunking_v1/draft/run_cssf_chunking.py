from pathlib import Path

from chunking.cssf_cleaning import clean_text
from chunking.chunk_builder import build_section_chunks
from chunking.persist_chunks import save_chunks
from chunking.validate_chunks import run_validation


DOCUMENTS = {
    "cssf": {
        "input_path": Path("data/processed/extracted_text/cssf_circular_20_750.txt"),
        "output_path": Path("data/processed/chunks/cssf_circular_20_750_sections.json"),
        "chunking_strategy": "section"
    }
    # dora and eba will be added later
}


def run_cssf_pipeline(config):
    text = config["input_path"].read_text(encoding="utf-8")

    cleaned = clean_text(text)
    chunks = build_section_chunks(cleaned)

    assert len(chunks) > 0, "❌ No chunks created!"

    save_chunks(chunks, config["output_path"])
    print(f"✅ Created {len(chunks)} CSSF section chunks")

    run_validation(config["output_path"])


def main(document_type: str):
    if document_type not in DOCUMENTS:
        raise ValueError(f"Unknown document type: {document_type}")

    config = DOCUMENTS[document_type]

    if document_type == "cssf":
        run_cssf_pipeline(config)
    else:
        raise NotImplementedError(
            f"Chunking not yet implemented for {document_type}"
        )


if __name__ == "__main__":
    main("cssf")
