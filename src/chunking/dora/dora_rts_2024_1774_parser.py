"""DORA RTS 2024/1774 is structurally the same as the main DORA regulation
(numbered Articles, one per line) except it nests CHAPTER I/II/III under
TITLE I/II/III/IV groupings that dora_parser's chapter detection doesn't
know about — chapter numerals repeat across Titles (e.g. two different
"CHAPTER I"s), so the `chapter` field loses Title-level precision. That's a
metadata quality wrinkle, not a correctness bug: each article still gets
matched to its immediately preceding CHAPTER marker correctly. Reuses
dora_parser's article-finding/chunk-assembly logic directly, same as
gdpr_parser.py.
"""
from typing import Dict, List

from src.chunking.dora.dora_parser import build_article_chunks as _build_article_chunks

DOCUMENT_META = {
    "document_id": "dora_rts_2024_1774",
    "document_title": (
        "Commission Delegated Regulation (EU) 2024/1774 "
        "(DORA RTS — ICT risk management tools, methods, processes and policies)"
    ),
    "authority": "European Union",
    "jurisdiction": "EU",
    "binding_level": "EU Regulatory Technical Standard (Delegated Regulation)",
    "chunk_id_prefix": "dora_rts_2024_1774_article",
}


def build_article_chunks(text: str) -> List[Dict]:
    return _build_article_chunks(text, DOCUMENT_META)
