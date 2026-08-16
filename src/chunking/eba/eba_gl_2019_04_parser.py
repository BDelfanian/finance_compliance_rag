"""EBA/GL/2019/04 (consolidated version, as amended by EBA/GL/2025/02) —
Guidelines on ICT and security risk management. DORA superseded most of
this guideline's substantive content for DORA-scope entities; the
consolidated text marks those repealed sections as "[deleted]" (sections
3.1-3.7), leaving only section 3.8 (payment-service-user relationship
management, paragraphs 92-98) genuinely in force — still applicable
because it derives from PSD2, not the CRD mandate DORA displaced.

Reuses eba_parser's paragraph-finding logic directly (same numbered-
paragraph convention as the outsourcing guidelines already indexed).
PARAGRAPH_PATTERN only matches lines with an actual "N. " numbered
paragraph, so the "[deleted]" sections — which have no paragraph numbers,
just a dotted sub-heading like "3.1. Proportionality" followed by the
literal word "[deleted]" — are naturally excluded already; no explicit
filtering needed.
"""
from typing import Dict, List

from src.chunking.eba.eba_parser import build_paragraph_chunks as _build_paragraph_chunks

DOCUMENT_META = {
    "document_id": "eba_gl_2019_04",
    "document_title": (
        "EBA/GL/2019/04 (consolidated, as amended by EBA/GL/2025/02) — "
        "Guidelines on ICT and Security Risk Management"
    ),
    "authority": "European Banking Authority",
    "jurisdiction": "EU",
    "binding_level": "Guideline (Comply or Explain)",
    "chunk_id_prefix": "eba_ict_security_paragraph",
}


def build_paragraph_chunks(text: str) -> List[Dict]:
    return _build_paragraph_chunks(text, DOCUMENT_META)
