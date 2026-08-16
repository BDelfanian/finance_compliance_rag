import re
from src.chunking.base_parser import BaseParser


class CSSFParser(BaseParser):

    SECTION_PATTERN = re.compile(r"(\d+\.\d+\.\d+)\.\s+(.*)")

    def parse(self, text: str):
        sections = []
        matches = list(self.SECTION_PATTERN.finditer(text))

        for i, match in enumerate(matches):
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

            sections.append({
                "section_id": match.group(1),
                "section_title": match.group(2).strip(),
                "text": text[start:end].strip()
            })

        return sections
