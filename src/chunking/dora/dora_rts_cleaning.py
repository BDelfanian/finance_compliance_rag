"""Commission Delegated Regulation (EU) 2024/1774 (the DORA RTS on ICT risk
management tools/methods/processes) uses the EU's newer Official Journal
"L series" publication format (2024+), which formats its noise lines
differently from the older format dora_cleaning.py was written against
(the DORA main regulation is from 2022) — e.g. "Official Journal EN" /
"of the European Union L series" split across two lines instead of one,
"OJ L, 25.6.2024" instead of a bare date, and an "ELI: http://..." link
line instead of a page-number marker. Same noise-removal approach as
dora_cleaning.py (strip matching lines), different patterns because the
underlying format genuinely differs.
"""
import re

OJ_L_SERIES_NOISE_PATTERNS = [
    r"^Official Journal EN$",
    r"^of the European Union L series$",
    r"^OJ L,\s*\d{1,2}\.\d{1,2}\.\d{4}$",
    r"^ELI:\s*http",
]


def remove_oj_l_series_noise(text: str) -> str:
    lines = text.splitlines()
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            cleaned_lines.append("")
            continue

        if any(re.search(pat, stripped) for pat in OJ_L_SERIES_NOISE_PATTERNS):
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()
