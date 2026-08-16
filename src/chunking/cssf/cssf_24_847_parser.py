"""Circular CSSF 24/847 (ICT-related incident reporting) uses flat "N. "
paragraph numbering (1, 2, 3, ...) under "Chapter N: Title" headers — a
different structure from both 20/750 (3-level dotted section numbers) and
22/806 ("Section X.Y.Z" headers), so this is its own small parser rather
than a reuse of either.

The substantive body (Chapters 1-4, paragraphs 1-28) is followed by two
Annexes (a deadlines table and a data-field table for the incident
notification form) whose row/field labels restart numbering from "1." —
colliding with the body's own paragraph numbers and not being citable
regulatory text in the same sense as the numbered paragraphs above them.
Paragraph-finding stops at the "Annexes" marker so those tables are
excluded rather than producing colliding/meaningless chunk_ids.
"""
import re
from typing import Dict, List, Tuple

CHAPTER_PATTERN = re.compile(
    r"^Chapter\s+(\d+):\s*(.*)?$",
    re.MULTILINE
)

PARAGRAPH_PATTERN = re.compile(
    r"^(\d+)\.\s+(.*)$",
    re.MULTILINE
)

ANNEX_BOUNDARY_PATTERN = re.compile(r"^Annexes\s", re.MULTILINE)

DOCUMENT_META = {
    "document_id": "cssf_24_847",
    "document_title": "Circular CSSF 24/847 on ICT-related Incident Reporting Framework",
    "authority": "CSSF",
    "jurisdiction": "LU",
    "binding_level": "Circular",
    "chunk_id_prefix": "cssf_24_847_para",
}


def find_chapters(text: str) -> List[Tuple[str, int, str]]:
    chapters = []
    for match in CHAPTER_PATTERN.finditer(text):
        chapters.append((f"Chapter {match.group(1)}", match.start(), (match.group(2) or "").strip()))
    return chapters


def find_paragraphs(text: str, end_pos: int) -> List[Tuple[str, int]]:
    paragraphs = []
    for match in PARAGRAPH_PATTERN.finditer(text):
        if match.start() >= end_pos:
            break
        paragraphs.append((match.group(1), match.start()))
    return paragraphs


def build_paragraph_chunks(text: str) -> List[Dict]:
    annex_match = ANNEX_BOUNDARY_PATTERN.search(text)
    body_end = annex_match.start() if annex_match else len(text)

    paragraphs = find_paragraphs(text, body_end)
    chapters = find_chapters(text)

    chunks = []
    if not paragraphs:
        return chunks

    def chapter_for_position(pos):
        current = None
        for chap in chapters:
            if chap[1] <= pos:
                current = chap
            else:
                break
        return current

    for i, (para_no, start_pos) in enumerate(paragraphs):
        end_pos = paragraphs[i + 1][1] if i + 1 < len(paragraphs) else body_end
        content = text[start_pos:end_pos].strip()

        chapter = chapter_for_position(start_pos)

        chunks.append({
            "chunk_id": f"{DOCUMENT_META['chunk_id_prefix']}_{para_no}",
            "document_id": DOCUMENT_META["document_id"],
            "document_title": DOCUMENT_META["document_title"],
            "authority": DOCUMENT_META["authority"],
            "jurisdiction": DOCUMENT_META["jurisdiction"],
            "binding_level": DOCUMENT_META["binding_level"],
            "chapter": f"{chapter[0]} – {chapter[2]}" if chapter else "",
            "paragraph_number": para_no,
            "text": content,
        })

    return chunks
