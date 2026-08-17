"""Retrieval-only golden-query validation for the GDPR store, kept separate
from golden_queries.json / test_retrieval_validation.py deliberately: GDPR
is indexed and queryable (see src/retrieval/run_embeddings_retrieval.py) but
is not part of retrieval_agent.VECTOR_STORES or
citation_bound_answer_generation.py's regulators dict yet (see docs/09 Phase
5 section), so it must not be exercised through src/evaluation/run_eval.py
--- that runner pushes every "standard" golden_queries.json case through
generate_citation_bound_answer_cached, which only ever searches CSSF/DORA/
EBA. A GDPR case there would always come back as an incorrect abstention and
corrupt data/eval_baseline.json's generation-quality metrics for a source
that was never wired into generation. This file exercises retrieve()
directly instead, the same live-validated pattern test_retrieval_validation.py
uses for the other three stores.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT_DIR))

from src.retrieval.run_embeddings_retrieval import retrieve

TEST_DIR = Path(__file__).resolve().parent

with open(TEST_DIR / "golden_queries_gdpr.json", "r", encoding="utf-8") as f:
    GDPR_GOLDEN_QUERIES = json.load(f)

SIMILARITY_THRESHOLD = 0.55


@pytest.mark.parametrize("case", GDPR_GOLDEN_QUERIES)
def test_expected_chunks_retrieved(case):
    result = retrieve(
        query_text=case["query"],
        vector_store_key=case["vector_store_key"],
        authority=case["authority"],
        jurisdiction=case["jurisdiction"],
        top_k=5,
    )

    retrieved_ids = {c["chunk_id"] for c in result["retrieved_chunks"]}

    for expected in case["expected_chunk_ids"]:
        assert expected in retrieved_ids


@pytest.mark.parametrize("case", [c for c in GDPR_GOLDEN_QUERIES if c.get("type") == "no_answer"])
def test_no_answer_cases_retrieve_nothing(case):
    result = retrieve(
        query_text=case["query"],
        vector_store_key=case["vector_store_key"],
        authority=case["authority"],
        jurisdiction=case["jurisdiction"],
        top_k=5,
    )

    assert result["retrieved_chunks"] == []


@pytest.mark.parametrize("case", GDPR_GOLDEN_QUERIES)
def test_similarity_threshold_respected(case):
    result = retrieve(
        query_text=case["query"],
        vector_store_key=case["vector_store_key"],
        authority=case["authority"],
        jurisdiction=case["jurisdiction"],
        top_k=5,
    )

    for c in result["retrieved_chunks"]:
        assert c["similarity_score"] >= SIMILARITY_THRESHOLD


@pytest.mark.parametrize("case", GDPR_GOLDEN_QUERIES)
def test_no_cross_regulatory_contamination(case):
    result = retrieve(
        query_text=case["query"],
        vector_store_key=case["vector_store_key"],
        authority=case["authority"],
        jurisdiction=case["jurisdiction"],
        top_k=5,
    )

    for c in result["retrieved_chunks"]:
        assert c["chunk_id"].startswith(case["vector_store_key"])
