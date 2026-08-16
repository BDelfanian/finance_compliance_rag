import sys
from pathlib import Path
import json
import pytest

# --- Path bootstrap ---
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT_DIR))

from src.retrieval.run_embeddings_retrieval import retrieve

# --- Load golden queries ---
TEST_DIR = Path(__file__).resolve().parent

with open(TEST_DIR / "golden_queries.json", "r", encoding="utf-8") as f:
    GOLDEN_QUERIES = json.load(f)

SIMILARITY_THRESHOLD = 0.55


@pytest.mark.parametrize("case", GOLDEN_QUERIES)
def test_expected_chunks_retrieved(case):
    result = retrieve(
        query_text=case["query"],
        vector_store_key=case["vector_store_key"],
        authority=case["authority"],
        jurisdiction=case["jurisdiction"],
        top_k=5
    )

    retrieved_ids = {c["chunk_id"] for c in result["retrieved_chunks"]}

    for expected in case["expected_chunk_ids"]:
        assert expected in retrieved_ids


@pytest.mark.parametrize("case", GOLDEN_QUERIES)
def test_similarity_threshold_respected(case):
    result = retrieve(
        query_text=case["query"],
        vector_store_key=case["vector_store_key"],
        authority=case["authority"],
        jurisdiction=case["jurisdiction"],
        top_k=5
    )

    for c in result["retrieved_chunks"]:
        assert c["similarity_score"] >= SIMILARITY_THRESHOLD


@pytest.mark.parametrize("case", GOLDEN_QUERIES)
def test_no_cross_regulatory_contamination(case):
    result = retrieve(
        query_text=case["query"],
        vector_store_key=case["vector_store_key"],
        authority=case["authority"],
        jurisdiction=case["jurisdiction"],
        top_k=5
    )

    for c in result["retrieved_chunks"]:
        assert c["chunk_id"].startswith(case["vector_store_key"])
