import re

FOOTER_PATTERNS = [
    r"CIRCULAR CSSF\s+\d+/\d+.*",
    r"as amended by Circulars.*"
]

SECTION_TITLE_PATTERN = re.compile(
    r"^\d+\.\d+\.\s+[A-Z].*$",
    re.MULTILINE
)

def remove_footers(text: str) -> str:
    """Removes common footer patterns from the text."""
    
    for pattern in FOOTER_PATTERNS:
        text = re.sub(pattern, "", text)
    return text

def remove_section_titles(text: str) -> str:
    """
    Removes lines like:
    3.2. Governance and strategy
    3.4. Information security
    """
    return re.sub(SECTION_TITLE_PATTERN, "", text)

def clean_text(text: str) -> str:
    text = remove_footers(text)
    text = remove_section_titles(text)
    return text.strip()
