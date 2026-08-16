import re


EBA_NOISE_PATTERNS = [
    r"EBA/GL/\d{4}/\d+",
    r"FINAL REPORT",
    r"^Page\s+\d+.*$",
    r"^\d+$",                    # standalone page numbers
    r"European Banking Authority",
    r"^CONSOLIDATED VERSION OF GUIDELINES",  # repeating page-break header in consolidated GL text
]


def remove_eba_noise(text: str) -> str:
    lines = text.splitlines()
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            cleaned_lines.append("")
            continue

        if any(re.search(pat, stripped) for pat in EBA_NOISE_PATTERNS):
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()
