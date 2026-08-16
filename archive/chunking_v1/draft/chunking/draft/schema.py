def create_chunk(
    chunk_id: str,
    document_id: str,
    document_title: str,
    authority: str,
    jurisdiction: str,
    binding_level: str,
    article_number: str,
    article_title: str,
    text: str
) -> dict:
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "document_title": document_title,
        "authority": authority,
        "jurisdiction": jurisdiction,
        "binding_level": binding_level,
        "article_number": article_number,
        "article_title": article_title,
        "text": text.strip()
    }
