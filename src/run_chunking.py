import argparse
import sys

from src.chunking.persist_chunks import save_chunks
from src.chunking.registry import DOCUMENT_REGISTRY

# This script (and the chunk-builder/validator modules it calls into) print
# unicode symbols (✅, ⚠, ❌). A non-interactive Windows console defaults its
# stdout/stderr encoding to the system codepage (cp1252), not UTF-8, which
# raises UnicodeEncodeError on those symbols — surfaced by running this via
# `dvc repro` (dvc.yaml's `chunk` stage), which spawns it without an
# inherited interactive-terminal UTF-8 codepage. Reconfiguring here once, at
# the actual process entrypoint, fixes every print site without touching
# each one individually.
if hasattr(sys.stdout, "reconfigure"):
    # typeshed's abstract `TextIO` doesn't declare reconfigure (only the
    # concrete io.TextIOWrapper does) — the hasattr guard above is the real
    # runtime safety check; these are narrower than what the stub can prove.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]


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
    parser = argparse.ArgumentParser(description="Run chunking pipeline for regulatory documents")

    parser.add_argument("--doc", required=True, choices=DOCUMENT_REGISTRY.keys(), help="Document type to process")

    args = parser.parse_args()
    run(args.doc)


if __name__ == "__main__":
    main()
