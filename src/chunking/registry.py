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

# GDPR reuses DORA's Official Journal noise cleaner as-is: that function is
# already EU-regulation-generic, not DORA-specific, so there's nothing to
# duplicate here. Only the article/chapter parsing needs GDPR's own document
# metadata — see gdpr_parser.py.
from src.chunking.dora.dora_cleaning import remove_official_journal_noise as gdpr_clean
from src.chunking.gdpr.gdpr_parser import build_article_chunks as gdpr_build_chunks
from src.chunking.gdpr.gdpr_validate_chunks import run_validation as gdpr_run_validation

# --- Additional documents for existing authorities (Phase 5 extension) ---

from src.chunking.cssf.cssf_page_noise_cleaning import remove_page_noise as cssf_22_806_clean
from src.chunking.cssf.cssf_22_806_parser import build_section_chunks as cssf_22_806_build_chunks
from src.chunking.cssf.cssf_22_806_validate_chunks import run_validation as cssf_22_806_run_validation

from src.chunking.cssf.cssf_page_noise_cleaning import remove_page_noise as cssf_24_847_clean
from src.chunking.cssf.cssf_24_847_parser import build_paragraph_chunks as cssf_24_847_build_chunks
from src.chunking.cssf.cssf_24_847_validate_chunks import run_validation as cssf_24_847_run_validation

# DORA RTS 2024/1774 needs its own OJ-noise cleaner (the EU's newer "L
# series" OJ publication format, different from the 2022-era format
# dora_cleaning.py targets) but reuses dora_parser's article/chapter logic.
from src.chunking.dora.dora_rts_cleaning import remove_oj_l_series_noise as dora_rts_clean
from src.chunking.dora.dora_rts_2024_1774_parser import build_article_chunks as dora_rts_build_chunks
from src.chunking.dora.dora_rts_2024_1774_validate_chunks import run_validation as dora_rts_run_validation

# eba_cleaning/eba_validate_chunks are already document-agnostic (no
# eba_outsourcing-specific hardcoding), so both are reused directly here —
# only the parser needs eba_gl_2019_04's own document metadata.
from src.chunking.eba.eba_cleaning import remove_eba_noise as eba_gl_2019_04_clean
from src.chunking.eba.eba_gl_2019_04_parser import build_paragraph_chunks as eba_gl_2019_04_build_chunks
from src.chunking.eba.eba_validate_chunks import run_validation as eba_gl_2019_04_run_validation


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
    "gdpr": {
        "input_path": Path("data/processed/extracted_text/gdpr_regulation.txt"),
        "output_path": Path("data/processed/chunks/gdpr_articles.json"),
        "cleaner": gdpr_clean,
        "chunk_builder": gdpr_build_chunks,
        "validator": gdpr_run_validation,
    },
    "cssf_22_806": {
        "input_path": Path("data/processed/extracted_text/cssf_circular_22_806.txt"),
        "output_path": Path("data/processed/chunks/cssf_22_806_sections.json"),
        "cleaner": cssf_22_806_clean,
        "chunk_builder": cssf_22_806_build_chunks,
        "validator": cssf_22_806_run_validation,
    },
    "cssf_24_847": {
        "input_path": Path("data/processed/extracted_text/cssf_circular_24_847.txt"),
        "output_path": Path("data/processed/chunks/cssf_24_847_paragraphs.json"),
        "cleaner": cssf_24_847_clean,
        "chunk_builder": cssf_24_847_build_chunks,
        "validator": cssf_24_847_run_validation,
    },
    "dora_rts_2024_1774": {
        "input_path": Path("data/processed/extracted_text/dora_rts_2024_1774.txt"),
        "output_path": Path("data/processed/chunks/dora_rts_2024_1774_articles.json"),
        "cleaner": dora_rts_clean,
        "chunk_builder": dora_rts_build_chunks,
        "validator": dora_rts_run_validation,
    },
    "eba_gl_2019_04": {
        "input_path": Path("data/processed/extracted_text/eba_gl_2019_04_ict_security.txt"),
        "output_path": Path("data/processed/chunks/eba_gl_2019_04_paragraphs.json"),
        "cleaner": eba_gl_2019_04_clean,
        "chunk_builder": eba_gl_2019_04_build_chunks,
        "validator": eba_gl_2019_04_run_validation,
    },
}
