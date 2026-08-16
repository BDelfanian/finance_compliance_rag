from typing import List, Dict
from .section_parser import find_sections

def build_section_chunks(text: str) -> List[Dict]:
    sections = find_sections(text)
    chunks = []

    if not sections:
        return chunks

    for i, (section_id, start_pos, title) in enumerate(sections):
        end_pos = sections[i + 1][1] if i + 1 < len(sections) else len(text)
        content = text[start_pos:end_pos].strip()

        chunks.append({
            "chunk_id": f"cssf_20_750_{section_id.replace('.', '_')}",
            "section_id": section_id,
            "title": title,
            "text": content
        })

    return chunks
