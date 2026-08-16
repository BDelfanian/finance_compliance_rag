"""
STEP 5 Streamlit UI — Citation-Bound Answer Generation
Uses STEP 4 retrieval + STEP 5 engine to provide a clean, audit-friendly interface.
"""

import streamlit as st
from datetime import datetime
from src.generation.citation_bound_answer_generation import generate_citation_bound_answer, generate_citation_bound_answer_cached
import json

# -------------------------------
# Page Configuration
# -------------------------------
st.set_page_config(
    page_title="Finance Compliance RAG",
    page_icon="💼",
    layout="wide"
)

st.title("📊 Citation-Bound Answer Generation")
st.markdown(
    """
    Enter a regulatory query below. The system will generate an answer strictly using retrieved
    sources from CSSF, DORA, and EBA. Confidence scores and source citations are shown for auditability.
    """
)

# -------------------------------
# Input Section
# -------------------------------
query_text = st.text_area(
    label="Enter your regulatory query",
    height=120,
    placeholder="e.g., Explain reporting obligations for EU financial entities under CSSF, DORA, and EBA."
)

top_k = st.slider(
    label="Number of top chunks to retrieve per regulator",
    min_value=1,
    max_value=10,
    value=5
)

generate_button = st.button("Generate Answer")

# -------------------------------
# Generate & Display Answer
# -------------------------------
if generate_button:
    if not query_text.strip():
        st.error("Query cannot be empty!")
    else:
        with st.spinner("Generating citation-bound answer..."):
            try:
                #response = generate_citation_bound_answer(query_text, top_k=top_k)
                response = generate_citation_bound_answer_cached(query_text)

                # Answer Section
                st.subheader("✅ Answer")
                st.markdown(response["answer"])

                # Confidence Section
                st.subheader("📏 Answer Confidence")
                st.metric(
                    label="Confidence (0.0 = low, 1.0 = high)",
                    value=f"{response['answer_confidence']:.2f}"
                )

                # Retrieved Chunks Table
                st.subheader("📚 Retrieved Chunks")
                if response.get("retrieved_chunks"):
                    st.dataframe(response["retrieved_chunks"])
                else:
                    st.info("No chunks retrieved. Check your query or filters.")

                # Audit / JSON Panel
                st.subheader("🔍 Full STEP 5 Output (JSON)")
                with st.expander("Show JSON"):
                    st.json(response)

                # Timestamp
                st.caption(f"Generated at: {response['timestamp']}")

            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
