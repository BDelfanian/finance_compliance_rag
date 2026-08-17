import re
from typing import Dict, List, Optional, Tuple

PARAGRAPH_PATTERN = re.compile(r"^(\d+)\.\s+(.*)", re.MULTILINE)

SECTION_TITLE_PATTERN = re.compile(r"^[A-Z][A-Za-z\s\-]{5,}$", re.MULTILINE)

DOCUMENT_META = {
    "document_id": "eba_gl_outsourcing",
    "document_title": "EBA Guidelines on Outsourcing Arrangements",
    "authority": "European Banking Authority",
    "jurisdiction": "EU",
    "binding_level": "Guideline (Comply or Explain)",
    "chunk_id_prefix": "eba_outsourcing_paragraph",
}


def find_sections(text: str) -> List[Tuple[str, int]]:
    """
    Returns list of (section_title, position)
    """
    sections = []
    for match in SECTION_TITLE_PATTERN.finditer(text):
        sections.append((match.group(0).strip(), match.start()))
    return sections


def find_paragraphs(text: str) -> List[Tuple[str, int]]:
    """
    Returns list of (paragraph_number, position)
    """
    paragraphs = []
    for match in PARAGRAPH_PATTERN.finditer(text):
        paragraphs.append((match.group(1), match.start()))
    return paragraphs


def build_paragraph_chunks(text: str, document_meta: Optional[Dict] = None) -> List[Dict]:
    meta = document_meta or DOCUMENT_META

    paragraphs = find_paragraphs(text)
    sections = find_sections(text)

    chunks: list[dict] = []

    if not paragraphs:
        return chunks

    def section_for_position(pos):
        current = None
        for section in sections:
            if section[1] <= pos:
                current = section
            else:
                break
        return current

    for i, (para_no, start_pos) in enumerate(paragraphs):
        end_pos = paragraphs[i + 1][1] if i + 1 < len(paragraphs) else len(text)
        content = text[start_pos:end_pos].strip()

        section = section_for_position(start_pos)

        chunks.append(
            {
                "chunk_id": f"{meta['chunk_id_prefix']}_{para_no}",
                "document_id": meta["document_id"],
                "document_title": meta["document_title"],
                "authority": meta["authority"],
                "jurisdiction": meta["jurisdiction"],
                "binding_level": meta["binding_level"],
                "paragraph_number": para_no,
                "section_title": section[0] if section else "",
                "text": content,
            }
        )

    return chunks
