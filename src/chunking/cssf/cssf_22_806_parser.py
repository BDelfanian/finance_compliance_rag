r"""Circular CSSF 22/806 (outsourcing arrangements) uses dotted section
numbers at the same depth as Circular 20/750 (e.g. "4.2.7"), but the real
headers are formatted "Section 4.2.7 Documentation requirements" — prefixed
with the literal word "Section", not a bare number at line start like
20/750's "4.2.7. Documentation requirements". cssf_parser's existing
SECTION_PATTERN (`^(\d+\.\d+\.\d+)\.\s*...`) finds zero matches on this
document, so this is a small dedicated parser rather than a reuse of
section_parser.py — plus a "Part I/II/III" grouping 20/750 doesn't have,
tracked the same way dora_parser tracks chapter context per article.

The document opens with a full table of contents listing every "Section
X.Y.Z Title" and "Part N" heading a second time before the real body —
both match the same regexes as the real headers, which produced duplicate/
garbage chunk_ids (short, meaningless "chunks" spanning one TOC line to the
next) before this was caught by cssf_22_806_validate_chunks flagging 16
suspiciously short chunks. Fixed by anchoring on the second occurrence of
"Part I" (the TOC mentions it once, the real body heading appears once) and
discarding every match before that position. PART_PATTERN also requires a
dash before the title text (matching the real headings' "Part I –
Outsourcing arrangements" style) rather than accepting any "Part I ..."
line — without it, the body sentence "Part I of this circular applies to
the following In-Scope Entities when..." (line 318, prose referencing Part
I, not a heading) was misread as a heading and corrupted every subsequent
chunk's `part` field with that sentence fragment instead of the real title.
"""
import re
from typing import Dict, List, Tuple

SECTION_PATTERN = re.compile(
    r"^Section\s+(\d+\.\d+\.\d+)\s+(.+)?$",
    re.MULTILINE
)

PART_PATTERN = re.compile(
    r"^Part\s+([IVX]+)\s*[–—-]\s*(.+)?$",
    re.MULTILINE
)

DOCUMENT_META = {
    "document_id": "cssf_22_806",
    "document_title": "Circular CSSF 22/806 (as amended by 25/883) on Outsourcing Arrangements",
    "authority": "CSSF",
    "jurisdiction": "LU",
    "binding_level": "Circular",
    "chunk_id_prefix": "cssf_22_806",
}


def find_body_start(text: str) -> int:
    """The real Part I heading is the second "Part I" occurrence in the
    text (the first is the table of contents); everything before it is
    front matter/TOC, not citable body content."""
    matches = list(re.finditer(r"^Part\s+I\b", text, re.MULTILINE))
    return matches[1].start() if len(matches) >= 2 else 0


def find_parts(text: str, body_start: int) -> List[Tuple[str, int, str]]:
    parts = []
    for match in PART_PATTERN.finditer(text):
        if match.start() < body_start:
            continue
        title = (match.group(2) or "").strip().lstrip("–—- ").strip()
        parts.append((f"Part {match.group(1)}", match.start(), title))
    return parts


def find_sections(text: str, body_start: int) -> List[Tuple[str, int, str]]:
    sections = []
    for match in SECTION_PATTERN.finditer(text):
        if match.start() < body_start:
            continue
        sections.append((match.group(1), match.start(), (match.group(2) or "").strip()))
    return sections


def build_section_chunks(text: str) -> List[Dict]:
    body_start = find_body_start(text)
    sections = find_sections(text, body_start)
    parts = find_parts(text, body_start)

    chunks = []
    if not sections:
        return chunks

    def part_for_position(pos):
        current = None
        for part in parts:
            if part[1] <= pos:
                current = part
            else:
                break
        return current

    for i, (section_id, start_pos, title) in enumerate(sections):
        end_pos = sections[i + 1][1] if i + 1 < len(sections) else len(text)
        content = text[start_pos:end_pos].strip()

        part = part_for_position(start_pos)

        chunks.append({
            "chunk_id": f"{DOCUMENT_META['chunk_id_prefix']}_{section_id.replace('.', '_')}",
            "document_id": DOCUMENT_META["document_id"],
            "document_title": DOCUMENT_META["document_title"],
            "authority": DOCUMENT_META["authority"],
            "jurisdiction": DOCUMENT_META["jurisdiction"],
            "binding_level": DOCUMENT_META["binding_level"],
            "part": f"{part[0]} – {part[2]}" if part else "",
            "section_id": section_id,
            "title": title,
            "text": content,
        })

    return chunks
