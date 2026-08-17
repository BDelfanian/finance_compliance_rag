"""NIS2 is structurally identical to DORA and GDPR (numbered CHAPTERs
containing numbered Articles), so this reuses dora_parser's article/chapter
parsing logic directly — only the per-document metadata differs. Note
binding_level is "EU Directive", not "EU Regulation": NIS2 requires
national transposition and isn't directly applicable the way DORA/GDPR
are, a real legal distinction worth keeping accurate in chunk metadata.
"""

from typing import Dict, List

from src.chunking.dora.dora_parser import build_article_chunks as _build_article_chunks

DOCUMENT_META = {
    "document_id": "nis2_2022_2555",
    "document_title": "Directive (EU) 2022/2555 (NIS2 Directive)",
    "authority": "European Union",
    "jurisdiction": "EU",
    "binding_level": "EU Directive",
    "chunk_id_prefix": "nis2_article",
}


def build_article_chunks(text: str) -> List[Dict]:
    return _build_article_chunks(text, DOCUMENT_META)
