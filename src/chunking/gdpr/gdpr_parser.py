"""GDPR (Regulation (EU) 2016/679) is structured identically to DORA —
numbered CHAPTERs containing numbered Articles, same EU Official Journal
formatting — so this reuses dora_parser's chapter/article regex and chunk
assembly directly rather than duplicating it. Only the per-document
metadata differs.
"""

from typing import Dict, List

from src.chunking.dora.dora_parser import build_article_chunks as _build_article_chunks

DOCUMENT_META = {
    "document_id": "gdpr_2016_679",
    "document_title": "Regulation (EU) 2016/679 (GDPR)",
    "authority": "European Union",
    "jurisdiction": "EU",
    "binding_level": "EU Regulation",
    "chunk_id_prefix": "gdpr_article",
}


def build_article_chunks(text: str) -> List[Dict]:
    return _build_article_chunks(text, DOCUMENT_META)
