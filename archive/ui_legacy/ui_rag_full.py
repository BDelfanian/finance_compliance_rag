import streamlit as st
import pandas as pd
import numpy as np
import sys
from pathlib import Path
import json
from io import BytesIO
import base64

# --- Path bootstrap ---
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT_DIR))

from src.run_embeddings_retrieval import retrieve

st.set_page_config(page_title="Regulatory Retrieval RAG", layout="wide")

st.title("📜 Regulatory Retrieval Assistant")

# -------------------------
# Query input
# -------------------------
query_text = st.text_area("Enter your regulatory query:", height=120)

regulator_options = ["CSSF", "DORA", "EBA"]
selected_regulators = st.multiselect(
    "Select regulator(s):", regulator_options, default=["CSSF"]
)

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
    "EBA": ("eba", "European Banking Authority", "EU")
}

# -------------------------
# Retrieval & Display
# -------------------------
if st.button("Retrieve") and query_text and selected_regulators:
    all_results = []
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
                top_k=top_k
            )
            # filter by similarity threshold
            result["retrieved_chunks"] = [
                c for c in result["retrieved_chunks"]
                if c["similarity_score"] >= sim_threshold
            ]
            set_cached_result(cache_key, result)
        all_results.append((reg, result))

    # Display results per regulator
    for reg, res in all_results:
        st.subheader(f"🔹 {reg} Results")
        if res["retrieved_chunks"]:
            df = pd.DataFrame(res["retrieved_chunks"])
            
            # similarity heatmap
            def color_score(val):
                # Green high, red low
                green = int(255 * val)
                red = 255 - green
                return f'background-color: rgb({red},{green},0)'
            
            st.dataframe(df.style.applymap(lambda v: color_score(v) if isinstance(v, float) else '', subset=["similarity_score"]))
        else:
            st.write("No relevant chunks found.")

    # -------------------------
    # Export options
    # -------------------------
    export_all = []
    for reg, res in all_results:
        for c in res["retrieved_chunks"]:
            export_all.append({
                "regulator": reg,
                **c
            })
    if export_all:
        export_df = pd.DataFrame(export_all)
        csv_bytes = export_df.to_csv(index=False).encode("utf-8")
        b64_csv = base64.b64encode(csv_bytes).decode()
        st.markdown(f"[📥 Download CSV](data:file/csv;base64,{b64_csv})", unsafe_allow_html=True)
