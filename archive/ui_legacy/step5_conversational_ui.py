"""
STEP 5 Streamlit UI — Multi-Turn Conversational Context (Fixed)
Supports follow-ups and remembers previous queries in the session.
"""

import streamlit as st
from src.generation.citation_bound_answer_generation import generate_citation_bound_answer_cached

# -------------------------------
# Page Configuration
# -------------------------------
st.set_page_config(
    page_title="Finance Compliance RAG — Multi-Turn",
    page_icon="💬",
    layout="wide"
)

st.title("💬 Multi-Turn Citation-Bound QA")
st.markdown(
    """
    Ask regulatory questions about CSSF, DORA, and EBA. Previous queries and answers
    are remembered for follow-up questions within this session.
    """
)

# -------------------------------
# Session State Initialization
# -------------------------------
if "conversation" not in st.session_state:
    st.session_state.conversation = []

if "current_query" not in st.session_state:
    st.session_state.current_query = ""

# -------------------------------
# Input Section
# -------------------------------
st.session_state.current_query = st.text_area(
    label="Enter your regulatory query or follow-up",
    value=st.session_state.current_query,
    height=120,
    placeholder="e.g., Explain reporting obligations for EU financial entities under CSSF, DORA, and EBA."
)

top_k = st.slider(
    label="Number of top chunks to retrieve per regulator",
    min_value=1,
    max_value=10,
    value=5
)

submit_button = st.button("Submit Query / Follow-Up")

# -------------------------------
# Handle Query Submission
# -------------------------------
if submit_button and st.session_state.current_query.strip():
    query_text = st.session_state.current_query.strip()
    with st.spinner("Generating citation-bound answer..."):
        try:
            # Get cached answer for speed
            response = generate_citation_bound_answer_cached(query_text)

            # Append to session conversation
            st.session_state.conversation.append({
                "query": query_text,
                "answer": response["answer"],
                "answer_confidence": response["answer_confidence"],
                "retrieved_chunks": response["retrieved_chunks"],
                "timestamp": response["timestamp"]
            })

            # Clear the text area for next query
            st.session_state.current_query = ""

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

# -------------------------------
# Display Conversation History
# -------------------------------
if st.session_state.conversation:
    st.subheader("🕒 Conversation History")
    for i, entry in enumerate(reversed(st.session_state.conversation)):
        st.markdown(f"**Q{i+1}:** {entry['query']}")
        st.markdown(f"**A{i+1}:** {entry['answer']}")
        st.caption(f"Confidence: {entry['answer_confidence']:.2f} | Timestamp: {entry['timestamp']}")
        st.markdown("---")
