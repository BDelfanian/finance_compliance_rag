import re
import sys
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# --- Path bootstrap ---
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT_DIR))

from src.retrieval.run_embeddings_retrieval import retrieve, vector_store

st.set_page_config(page_title="Advanced Regulatory RAG", layout="wide")
st.title("📜 Regulatory Retrieval Assistant (Advanced)")

# -------------------------
# Query input
# -------------------------
query_text = st.text_area("Enter your regulatory query:", height=120)

regulator_options = ["CSSF", "DORA", "EBA", "NIS2"]
selected_regulators = st.multiselect("Select regulator(s):", regulator_options, default=regulator_options)

top_k = st.slider("Number of chunks to retrieve (top K):", min_value=1, max_value=20, value=5)
sim_threshold = st.slider("Similarity threshold:", min_value=0.0, max_value=1.0, value=0.55)

# -------------------------
# Session caching
# -------------------------
if "query_cache" not in st.session_state:
    st.session_state.query_cache = {}


def get_cached_result(cache_key):
    return st.session_state.query_cache.get(cache_key)


def set_cached_result(cache_key, result):
    st.session_state.query_cache[cache_key] = result


# -------------------------
# Regulator metadata mapping
# -------------------------
regulator_map = {
    "CSSF": ("cssf", "CSSF", "LU"),
    "DORA": ("dora", "European Union", "EU"),
    "EBA": ("eba", "European Banking Authority", "EU"),
    "NIS2": ("nis2", "European Union", "EU"),
}

# -------------------------
# Stopword list for highlighting
# -------------------------
STOPWORDS = {
    "the",
    "of",
    "and",
    "in",
    "on",
    "for",
    "with",
    "a",
    "an",
    "to",
    "is",
    "are",
    "as",
    "by",
    "at",
    "be",
    "this",
    "that",
}


def highlight_terms(text, query):
    terms = [w for w in re.findall(r"\w+", query) if w.lower() not in STOPWORDS and len(w) > 2]
    for term in terms:
        regex = re.compile(re.escape(term), re.IGNORECASE)
        text = regex.sub(lambda m: f"<mark>{m.group(0)}</mark>", text)
    return text


# -------------------------
# PDF generation
# -------------------------
def generate_pdf(results, query):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, f"Query: {query}")
    y -= 30

    for item in results:
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, f"{item['regulator']} - {item['chunk_id']} - {item['source_reference']}")
        y -= 15
        c.setFont("Helvetica", 10)
        for line in item["text"].split("\n"):
            if y < 50:
                c.showPage()
                y = height - 50
            c.drawString(50, y, line[:90])
            y -= 12
        c.drawString(50, y, f"Similarity: {item['similarity_score']:.2f}")
        y -= 25
    c.save()
    buffer.seek(0)
    return buffer


# -------------------------
# Retrieval & Display
# -------------------------
if st.button("Retrieve") and query_text and selected_regulators:
    aggregated_results = []

    for reg in selected_regulators:
        store_key, authority, jurisdiction = regulator_map[reg]
        cache_key = f"{query_text}|{reg}|{top_k}|{sim_threshold}"
        result = get_cached_result(cache_key)
        if not result:
            result = retrieve(
                query_text=query_text,
                vector_store_key=store_key,
                authority=authority,
                jurisdiction=jurisdiction,
                top_k=top_k,
            )
            # filter by similarity threshold
            result["retrieved_chunks"] = [
                c for c in result["retrieved_chunks"] if c["similarity_score"] >= sim_threshold
            ]
            set_cached_result(cache_key, result)

        # Add text to each chunk for display & export
        for c in result["retrieved_chunks"]:
            meta_chunks = [m for m in vector_store[store_key]["metadata"] if m["chunk_id"] == c["chunk_id"]]
            if meta_chunks:
                c["text"] = highlight_terms(meta_chunks[0]["text"], query_text)
                c["regulator"] = reg
                aggregated_results.append(c)

    # -------------------------
    # Display results
    # -------------------------
    st.subheader("🔹 Aggregated Results")
    if aggregated_results:
        for c in aggregated_results:
            st.markdown(f"**{c['regulator']} - {c['chunk_id']} - {c['source_reference']}**")
            st.markdown(c["text"], unsafe_allow_html=True)
            st.markdown(f"*Similarity: {c['similarity_score']:.2f}*")
            st.markdown("---")
    else:
        st.write("No relevant chunks found.")

    # -------------------------
    # Download options
    # -------------------------
    if aggregated_results:
        # CSV
        export_df = pd.DataFrame(aggregated_results)
        csv_bytes = export_df.to_csv(index=False).encode("utf-8")
        st.download_button(label="📥 Download CSV", data=csv_bytes, file_name="rag_results.csv", mime="text/csv")

        # PDF
        pdf_buffer = generate_pdf(aggregated_results, query_text)
        st.download_button(
            label="📥 Download PDF", data=pdf_buffer, file_name="rag_results.pdf", mime="application/pdf"
        )
