"""
STEP 5 — Citation-Bound Answer Generation
Uses STEP 4 retrieval output to generate multi-regulator, citation-bound answers
with GPT-5 mini.
"""

import hashlib
import json
import os
from datetime import datetime
from functools import lru_cache

import openai

from src.config import get_settings
from src.observability.cost_tracking import record_usage
from src.retrieval.run_embeddings_retrieval import retrieve, vector_store
from src.security.prompt_injection_check import scan_chunk_text

settings = get_settings()

# Preview length for the "excerpt" field on each retrieved chunk (API/UI
# display — src/ui/step6_read_only_ui.py and web/src/components/CitationList.tsx
# already render it if present; this is what populates it).
EXCERPT_MAX_CHARS = 400

CACHE_DIR = str(settings.resolved(settings.step5_cache_path))
os.makedirs(CACHE_DIR, exist_ok=True)


@lru_cache
def _load_prompt_template(version: str) -> str:
    """Load a versioned prompt template from prompts/<version>.md (roadmap
    §3.6 "Prompt versioning") — prompt changes become reviewable diffs with
    history instead of silent edits to an inline f-string."""
    path = settings.resolved(settings.prompts_dir) / f"{version}.md"
    return path.read_text(encoding="utf-8")


def get_cache_file(query_text: str) -> str:
    """Return the path for a cached response for a query."""
    query_hash = hashlib.md5(query_text.encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, f"{query_hash}.json")


def generate_citation_bound_answer_cached(query_text: str, top_k: int = settings.citation_top_k):
    """Generate or load a citation-bound answer using cache."""
    cache_file = get_cache_file(query_text)

    # Return cached response if it exists
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    # Otherwise, generate answer
    response = generate_citation_bound_answer(query_text, top_k=top_k)

    # Save to cache
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(response, f, indent=2)

    return response


# -------------------------------
# Configure OpenAI API Key
# -------------------------------
openai.api_key = settings.openai_api_key
if not openai.api_key:
    raise EnvironmentError("OPENAI_API_KEY environment variable not set")


# -------------------------------
# LLM call
# -------------------------------
def llm_call(prompt: str) -> str:
    """
    Call the configured chat model using OpenAI >=1.0.0
    """
    response = openai.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {
                "role": "system",
                "content": "You are a compliance-aware AI. Answer strictly using provided source chunks.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    if response.usage:
        record_usage(
            model=settings.llm_model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
        )
    return (response.choices[0].message.content or "").strip()


# -------------------------------
# Citation-Bound Answer Generation
# -------------------------------
def generate_citation_bound_answer(query_text: str, top_k: int = 5):
    """
    Retrieve relevant chunks from CSSF, DORA, EBA, NIS2 and generate a citation-bound answer
    """
    regulators = {
        "CSSF": {"vector_store_key": "cssf", "authority": "CSSF", "jurisdiction": "LU"},
        "DORA": {"vector_store_key": "dora", "authority": "European Union", "jurisdiction": "EU"},
        "EBA": {"vector_store_key": "eba", "authority": "European Banking Authority", "jurisdiction": "EU"},
        "NIS2": {"vector_store_key": "nis2", "authority": "European Union", "jurisdiction": "EU"},
    }

    retrieved_chunks_all = []
    llm_input = ""
    similarity_scores = []
    chunk_texts_for_scan = []

    # Multi-regulator retrieval
    for reg_name, reg_info in regulators.items():
        retrieval = retrieve(
            query_text=query_text,
            vector_store_key=reg_info["vector_store_key"],
            authority=reg_info["authority"],
            jurisdiction=reg_info["jurisdiction"],
            top_k=top_k,
        )

        for chunk_info in retrieval["retrieved_chunks"]:
            metadata_list = vector_store[reg_info["vector_store_key"]]["metadata"]
            chunk_meta = next((c for c in metadata_list if c["chunk_id"] == chunk_info["chunk_id"]), None)
            if not chunk_meta:
                continue
            # Use regulator name from iteration, not missing field
            regulator_name = reg_name
            source_ref = chunk_meta.get("source_reference", chunk_info["source_reference"])
            chunk_text = chunk_meta["text"]
            llm_input += f"[{regulator_name} {source_ref}] {chunk_text}\n"
            excerpt = chunk_text if len(chunk_text) <= EXCERPT_MAX_CHARS else chunk_text[:EXCERPT_MAX_CHARS] + "…"
            retrieved_chunks_all.append(
                {
                    "chunk_id": chunk_meta["chunk_id"],
                    "source_reference": source_ref,
                    "source_regulation": regulator_name,
                    "similarity_score": chunk_info["similarity_score"],
                    "excerpt": excerpt,
                }
            )
            similarity_scores.append(chunk_info["similarity_score"])
            chunk_texts_for_scan.append({"text": chunk_text})

    # Compute answer confidence
    answer_confidence = round(sum(similarity_scores) / len(similarity_scores), 4) if similarity_scores else 0.0

    # Prompt-injection resistance (roadmap §3.6 "Security hardening"):
    # retrieved chunk text is fixed regulatory PDF text the team sourced and
    # reviewed, but it's still treated as untrusted input to the LLM call —
    # see src/security/prompt_injection_check.py's module docstring. This is
    # a non-blocking signal surfaced as a risk-assessment warning downstream
    # (citation_agent.py), not a request-blocking check.
    injection_detected = scan_chunk_text(chunk_texts_for_scan)

    # Construct strict citation-bound prompt from the versioned template
    template = _load_prompt_template(settings.prompt_version)
    prompt = template.format(query_text=query_text, source_chunks=llm_input)

    # Generate answer using GPT-5 mini
    answer = llm_call(prompt)

    # Structured response
    response = {
        "query": query_text,
        "answer": answer,
        "answer_confidence": answer_confidence,
        "retrieved_chunks": retrieved_chunks_all,
        "retrieval_filters": {
            reg: {"authority": info["authority"], "jurisdiction": info["jurisdiction"]}
            for reg, info in regulators.items()
        },
        "timestamp": datetime.now().isoformat(),
        "prompt_version": settings.prompt_version,
        "injection_detected": injection_detected,
    }

    return response


# -------------------------------
# Example usage
# -------------------------------
if __name__ == "__main__":
    query_text = "Explain reporting obligations for EU financial entities under CSSF, DORA, and EBA."
    response = generate_citation_bound_answer(query_text)
    print(json.dumps(response, indent=2))
