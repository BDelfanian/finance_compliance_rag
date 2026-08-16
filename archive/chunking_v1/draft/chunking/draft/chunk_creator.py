from typing import List
from chunking.schema import create_chunk
from chunking.article_parser import extract_articles

def create_article_chunks(
    text: str,
    document_id: str,
    document_title: str,
    authority: str,
    jurisdiction: str,
    binding_level: str
) -> List[dict]:

    articles = extract_articles(text)
    chunks = []

    for idx, (article_number, article_text) in enumerate(articles, start=1):
        chunk_id = f"{document_id}_{article_number.replace(' ', '_').lower()}"

        chunk = create_chunk(
            chunk_id=chunk_id,
            document_id=document_id,
            document_title=document_title,
            authority=authority,
            jurisdiction=jurisdiction,
            binding_level=binding_level,
            article_number=article_number,
            article_title="",  # optional, fill later if needed
            text=article_text
        )

        chunks.append(chunk)

    return chunks
