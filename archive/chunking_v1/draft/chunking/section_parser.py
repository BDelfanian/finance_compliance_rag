import re
from typing import List, Tuple

SECTION_PATTERN = re.compile(
    r"^(\d+\.\d+\.\d+)\.\s*(.+)?$",
    re.MULTILINE
)

def find_sections(text: str) -> List[Tuple[str, int, str]]:
    """
    Returns (section_id, position, optional_title)
    """
    sections = []
    for match in SECTION_PATTERN.finditer(text):
        section_id = match.group(1)
        title = match.group(2) or ""
        sections.append((section_id, match.start(), title.strip()))
    return sections

def extract_section_chunks(text: str):
    sections = find_sections(text)
    chunks = []

    for i, (section_id, start_pos, title) in enumerate(sections):
        end_pos = sections[i + 1][1] if i + 1 < len(sections) else len(text)
        content = text[start_pos:end_pos].strip()

        chunks.append({
            "section_id": section_id,
            "title": title,
            "text": content
        })

    return chunks
