"""
Prompt versioning (roadmap §3.6): the citation-bound prompt lives in
prompts/<prompt_version>.md instead of an inline f-string. These tests cover
the template file itself and that generation logs which version produced an
answer, without making any real OpenAI calls.
"""

from src.config import get_settings
from src.generation import citation_bound_answer_generation as gen

settings = get_settings()


def test_prompt_template_file_has_expected_placeholders():
    template = gen._load_prompt_template(settings.prompt_version)
    assert "{query_text}" in template
    assert "{source_chunks}" in template


def test_prompt_template_formats_without_error():
    template = gen._load_prompt_template(settings.prompt_version)
    formatted = template.format(query_text="What is X?", source_chunks="[DORA 1] text")
    assert "What is X?" in formatted
    assert "[DORA 1] text" in formatted


def test_generate_citation_bound_answer_reports_prompt_version(monkeypatch):
    monkeypatch.setattr(gen, "llm_call", lambda prompt: "Information not available in retrieved sources.")
    monkeypatch.setattr(
        gen,
        "retrieve",
        lambda **kwargs: {"retrieved_chunks": [], "filters_applied": {}, "retrieval_timestamp": ""},
    )

    response = gen.generate_citation_bound_answer("irrelevant test query", top_k=1)

    assert response["prompt_version"] == settings.prompt_version
