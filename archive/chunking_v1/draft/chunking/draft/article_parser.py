import re
from typing import List, Tuple

ARTICLE_HEADER_PATTERN = re.compile(
    r"^Article\s+(\d+[A-Za-z]*)\s*$",
    re.MULTILINE
)

def find_article_headers(text: str) -> List[Tuple[str, int]]:
    """
    Returns list of (article_number, start_position)
    """
    return [
        (match.group(1), match.start())
        for match in ARTICLE_HEADER_PATTERN.finditer(text)
    ]

def extract_articles(text: str) -> List[Tuple[str, str]]:
    headers = find_article_headers(text)

    articles = []
    for i, (article_number, start_pos) in enumerate(headers):
        end_pos = headers[i + 1][1] if i + 1 < len(headers) else len(text)
        article_text = text[start_pos:end_pos].strip()

        articles.append(
            (f"Article {article_number}", article_text)
        )

    return articles
