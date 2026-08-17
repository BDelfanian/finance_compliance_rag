import re

OJ_FOOTER_PATTERNS = [
    r"Official Journal of the European Union",
    r"^L\s+\d+/\d+.*$",
    r"^\d{1,2}\.\d{1,2}\.\d{4}$",  # publication dates
    r"^—\s*\d+\s*—$",  # page numbers like — 12 —
]


def remove_official_journal_noise(text: str) -> str:
    lines = text.splitlines()
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            cleaned_lines.append("")
            continue

        if any(re.search(pat, stripped) for pat in OJ_FOOTER_PATTERNS):
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()
