from pathlib import Path

from src.chunking.cssf.cssf_cleaning import clean_text as cssf_clean
from src.chunking.cssf.chunk_builder import build_section_chunks
from src.chunking.cssf.cssf_validate_chunks import run_validation as cssf_run_validation

from src.chunking.dora.dora_cleaning import remove_official_journal_noise as dora_clean
from src.chunking.dora.dora_parser import build_article_chunks
from src.chunking.dora.dora_validate_chunks import run_validation as dora_run_validation

from src.chunking.eba.eba_cleaning import remove_eba_noise as eba_clean
from src.chunking.eba.eba_parser import build_paragraph_chunks
from src.chunking.eba.eba_validate_chunks import run_validation as eba_run_validation


DOCUMENT_REGISTRY = {
    "cssf": {
        "input_path": Path("data/processed/extracted_text/cssf_circular_20_750.txt"),
        "output_path": Path("data/processed/chunks/cssf_sections.json"),
        "cleaner": cssf_clean,
        "chunk_builder": build_section_chunks,
        "validator": cssf_run_validation,
    },
    "dora": {
        "input_path": Path("data/processed/extracted_text/dora_regulation.txt"),
        "output_path": Path("data/processed/chunks/dora_articles.json"),
        "cleaner": dora_clean,
        "chunk_builder": build_article_chunks,
        "validator": dora_run_validation,
    },
    "eba": {
        "input_path": Path("data/processed/extracted_text/eba_outsourcing_guidelines.txt"),
        "output_path": Path("data/processed/chunks/eba_paragraphs.json"),
        "cleaner": eba_clean,
        "chunk_builder": build_paragraph_chunks,
        "validator": eba_run_validation,
    },
}
