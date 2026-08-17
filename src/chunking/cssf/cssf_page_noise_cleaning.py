"""Page-header/footer noise for CSSF Circulars 22/806 and 24/847 — same
"CIRCULAR CSSF NN/NNN" / "as amended by Circular ..." footer text
cssf_cleaning.py's FOOTER_PATTERNS already targets, plus a bare "N/NN"
page-counter line (e.g. "1/59", "12/24") neither 20/750's extraction nor
cssf_cleaning.py's regex.sub-over-the-whole-string approach needs to
handle (20/750's PDF layout doesn't produce this artifact). Implemented as
line-based filtering (like dora_cleaning.py/eba_cleaning.py) rather than
reusing cssf_cleaning.remove_footers's whole-string re.sub, since the new
bare-page-number pattern needs `^...$` anchored to each line, and
remove_footers doesn't set re.MULTILINE.
"""

import re

PAGE_NOISE_PATTERNS = [
    r"^CIRCULAR CSSF\s+\d+/\d+",
    r"^as amended by Circular",
    r"^\d+/\d+$",  # bare page counters ("1/59") and cover-page circular-number lines ("22/806")
]


def remove_page_noise(text: str) -> str:
    lines = text.splitlines()
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            cleaned_lines.append("")
            continue

        if any(re.search(pat, stripped) for pat in PAGE_NOISE_PATTERNS):
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()
