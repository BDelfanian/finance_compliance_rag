import hashlib
import json
import os
import pickle
from datetime import datetime
from typing import Any, Dict

import faiss
import numpy as np
from openai import OpenAI

from src.config import get_settings
from src.observability.cost_tracking import record_usage

# -------------------------------
# Configuration
# -------------------------------
settings = get_settings()

CHUNK_PATH = str(settings.resolved(settings.chunk_path))
VECTOR_DIM = settings.vector_dim
BATCH_SIZE = settings.embedding_batch_size
K_NEAREST = settings.k_nearest
SIMILARITY_THRESHOLD = settings.similarity_threshold

FAISS_PATH = str(settings.resolved(settings.faiss_path))
CACHE_PATH = str(settings.resolved(settings.retrieval_cache_path))
os.makedirs(FAISS_PATH, exist_ok=True)
os.makedirs(CACHE_PATH, exist_ok=True)

client = OpenAI(api_key=settings.openai_api_key or None)


# -------------------------------
# 1. Load chunks
# -------------------------------
def load_chunks(filename):
    path = os.path.join(CHUNK_PATH, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_chunk_files(filenames):
    """Concatenates chunks from multiple documents into one store's chunk
    list — used for authorities with more than one source document (e.g.
    cssf: Circular 20/750 + 22/806 + 24/847). Each document keeps its own
    chunk_id namespace (enforced by each parser's own chunk_id_prefix), so
    concatenation is safe without an extra dedup/merge step."""
    chunks = []
    for filename in filenames:
        chunks.extend(load_chunks(filename))
    return chunks


chunks_cssf = load_chunk_files(
    [
        "cssf_sections.json",
        "cssf_22_806_sections.json",
        "cssf_24_847_paragraphs.json",
    ]
)
chunks_dora = load_chunk_files(
    [
        "dora_articles.json",
        "dora_rts_2024_1774_articles.json",
    ]
)
chunks_eba = load_chunk_files(
    [
        "eba_paragraphs.json",
        "eba_gl_2019_04_paragraphs.json",
    ]
)
chunks_gdpr = load_chunks("gdpr_articles.json")
chunks_nis2 = load_chunks("nis2_articles.json")

vector_store: Dict[str, Dict[str, Any]] = {
    "cssf": {"vectors": None, "ids": [], "metadata": []},
    "dora": {"vectors": None, "ids": [], "metadata": []},
    "eba": {"vectors": None, "ids": [], "metadata": []},
    "gdpr": {"vectors": None, "ids": [], "metadata": []},
    "nis2": {"vectors": None, "ids": [], "metadata": []},
}


# -------------------------------
# 2. Embeddings
# -------------------------------
def embed_batch(text_list):
    response = client.embeddings.create(model=settings.embedding_model, input=text_list)
    if response.usage:
        record_usage(model=settings.embedding_model, embedding_tokens=response.usage.total_tokens)
    return np.array([r.embedding for r in response.data], dtype=np.float32)


def embed_text(text):
    return embed_batch([text])[0]


def process_chunks_batch(chunks, store_key):
    vectors = []
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        texts = [c["text"] for c in batch]
        batch_vectors = embed_batch(texts)
        vectors.append(batch_vectors)
        for c in batch:
            vector_store[store_key]["ids"].append(c["chunk_id"])
            vector_store[store_key]["metadata"].append(c)

    vector_store[store_key]["vectors"] = np.vstack(vectors)
    faiss.normalize_L2(vector_store[store_key]["vectors"])


def build_or_load_index(store_key, chunks):
    index_file = os.path.join(FAISS_PATH, f"{store_key}.index")
    meta_file = os.path.join(FAISS_PATH, f"{store_key}_metadata.pkl")
    vector_file = os.path.join(FAISS_PATH, f"{store_key}_vectors.npy")

    if os.path.exists(index_file) and os.path.exists(meta_file) and os.path.exists(vector_file):
        index = faiss.read_index(index_file)
        vector_store[store_key]["metadata"] = pickle.load(open(meta_file, "rb"))
        vector_store[store_key]["ids"] = [c["chunk_id"] for c in vector_store[store_key]["metadata"]]
        vector_store[store_key]["vectors"] = np.load(vector_file)
        return index

    process_chunks_batch(chunks, store_key)
    index = faiss.IndexFlatIP(VECTOR_DIM)
    index.add(vector_store[store_key]["vectors"])

    faiss.write_index(index, index_file)
    pickle.dump(vector_store[store_key]["metadata"], open(meta_file, "wb"))
    np.save(vector_file, vector_store[store_key]["vectors"])
    return index


faiss_indexes = {
    "cssf": build_or_load_index("cssf", chunks_cssf),
    "dora": build_or_load_index("dora", chunks_dora),
    "eba": build_or_load_index("eba", chunks_eba),
    "gdpr": build_or_load_index("gdpr", chunks_gdpr),
    "nis2": build_or_load_index("nis2", chunks_nis2),
}


# -------------------------------
# 3. Hard filtering (SAFE)
# -------------------------------
def hard_filter(chunks, authority=None, jurisdiction=None, binding_level=None):
    # CSSF chunks do not carry authority/jurisdiction → do not filter them out
    filtered = []
    for c in chunks:
        if authority and "authority" in c and c.get("authority") != authority:
            continue
        if jurisdiction and "jurisdiction" in c and c.get("jurisdiction") != jurisdiction:
            continue
        if binding_level and c.get("binding_level") != binding_level:
            continue
        filtered.append(c)
    return filtered


# -------------------------------
# 4. Retrieval
# -------------------------------
def query_hash(query_text, authority, jurisdiction, binding_level, store_key, top_k):
    key = f"{query_text}|{authority}|{jurisdiction}|{binding_level}|{store_key}|{top_k}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def retrieve(query_text, vector_store_key, authority=None, jurisdiction=None, binding_level=None, top_k=K_NEAREST):
    cache_file = os.path.join(
        CACHE_PATH, f"{query_hash(query_text, authority, jurisdiction, binding_level, vector_store_key, top_k)}.pkl"
    )
    if os.path.exists(cache_file):
        return pickle.load(open(cache_file, "rb"))

    chunks = hard_filter(vector_store[vector_store_key]["metadata"], authority, jurisdiction, binding_level)

    if not chunks:
        return {
            "query_id": f"Q_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "retrieved_chunks": [],
            "filters_applied": {"authority": authority, "jurisdiction": jurisdiction},
            "retrieval_timestamp": datetime.now().isoformat(),
        }

    vectors = np.vstack(
        [
            vector_store[vector_store_key]["vectors"][vector_store[vector_store_key]["ids"].index(c["chunk_id"])]
            for c in chunks
        ]
    )

    faiss.normalize_L2(vectors)
    index = faiss.IndexFlatIP(VECTOR_DIM)
    index.add(vectors)

    query_vec = embed_text(query_text).reshape(1, -1)
    faiss.normalize_L2(query_vec)

    distances, indices = index.search(query_vec, top_k)

    results = []
    for d, i in zip(distances[0], indices[0]):
        if d < SIMILARITY_THRESHOLD:
            continue
        c = chunks[i]
        results.append(
            {
                "chunk_id": c["chunk_id"],
                "source_reference": c.get("section_id") or c.get("article_number") or c.get("paragraph_number"),
                "similarity_score": float(d),
            }
        )

    output = {
        "query_id": f"Q_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "retrieved_chunks": results,
        "filters_applied": {"authority": authority, "jurisdiction": jurisdiction},
        "retrieval_timestamp": datetime.now().isoformat(),
    }

    pickle.dump(output, open(cache_file, "wb"))
    return output


# -------------------------------
# 5. Example usage
# -------------------------------
if __name__ == "__main__":
    # Pre-flight checks
    def pre_flight_check():
        if not settings.openai_api_key:
            raise EnvironmentError("OPENAI_API_KEY is not set. Please export it first.")

        required_files = [
            os.path.join(CHUNK_PATH, "cssf_sections.json"),
            os.path.join(CHUNK_PATH, "cssf_22_806_sections.json"),
            os.path.join(CHUNK_PATH, "cssf_24_847_paragraphs.json"),
            os.path.join(CHUNK_PATH, "dora_articles.json"),
            os.path.join(CHUNK_PATH, "dora_rts_2024_1774_articles.json"),
            os.path.join(CHUNK_PATH, "eba_paragraphs.json"),
            os.path.join(CHUNK_PATH, "eba_gl_2019_04_paragraphs.json"),
            os.path.join(CHUNK_PATH, "gdpr_articles.json"),
            os.path.join(CHUNK_PATH, "nis2_articles.json"),
        ]
        missing = [f for f in required_files if not os.path.exists(f)]
        if missing:
            raise FileNotFoundError(f"Missing required chunk files: {missing}")

        for folder in [FAISS_PATH, CACHE_PATH]:
            os.makedirs(folder, exist_ok=True)

    # Call at the start
    pre_flight_check()

    # -------------------------
    # CSSF test
    # -------------------------
    cssf_result = retrieve(
        query_text="What are the responsibilities of the management body regarding ICT governance?",
        vector_store_key="cssf",
        authority="CSSF",
        jurisdiction="LU",
        top_k=5,
    )
    print("\n=== CSSF RESULT ===")
    print(json.dumps(cssf_result, indent=2))

    # -------------------------
    # DORA test
    # -------------------------
    dora_result = retrieve(
        query_text="What are the requirements for ICT risk management and incident reporting under DORA?",
        vector_store_key="dora",
        authority="European Union",
        jurisdiction="EU",
        top_k=5,
    )
    print("\n=== DORA RESULT ===")
    print(json.dumps(dora_result, indent=2))

    # -------------------------
    # EBA test
    # -------------------------
    eba_result = retrieve(
        query_text="What are the reporting and compliance obligations for outsourcing arrangements under EBA guidelines?",
        vector_store_key="eba",
        authority="European Banking Authority",
        jurisdiction="EU",
        top_k=5,
    )
    print("\n=== EBA RESULT ===")
    print(json.dumps(eba_result, indent=2))
