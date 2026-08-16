import argparse

from src.chunking.registry import DOCUMENT_REGISTRY
from src.chunking.persist_chunks import save_chunks


def run(document_type: str):
    if document_type not in DOCUMENT_REGISTRY:
        raise ValueError(f"Unknown document type: {document_type}")

    # Load configuration
    config = DOCUMENT_REGISTRY[document_type]

    # Read raw text
    raw_text = config["input_path"].read_text(encoding="utf-8")

    # Clean and chunk
    cleaned = config["cleaner"](raw_text)
    chunks = config["chunk_builder"](cleaned)

    # Basic assertion
    assert len(chunks) > 0, f"❌ No chunks created for {document_type}"

    # Save chunks
    save_chunks(chunks, config["output_path"])
    print(f"✅ Created {len(chunks)} chunks for {document_type}")

    # Run chunking validation
    config["validator"](config["output_path"])


def main():
    parser = argparse.ArgumentParser(
        description="Run chunking pipeline for regulatory documents"
    )

    parser.add_argument(
        "--doc",
        required=True,
        choices=DOCUMENT_REGISTRY.keys(),
        help="Document type to process"
    )

    args = parser.parse_args()
    run(args.doc)


if __name__ == "__main__":
    main()
