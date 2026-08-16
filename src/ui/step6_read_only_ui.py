# src/ui/step6_read_only_ui.py
"""
Finance Compliance RAG — primary UI.

Drives the full multi-agent pipeline (retrieval -> citation-bound answer ->
summarization -> risk assessment) via the MLflow-logged chains in
src.chains.step6_agent_wrappers_mlflow, and renders the result as a readable
answer with citations, summary, and risk warnings — not raw JSON dumps.
Raw agent output remains available per-run for audit purposes.
"""
import asyncio
import re
from datetime import datetime

import streamlit as st

from src.chains import step6_agent_wrappers_mlflow as wrappers
from src.observability.logging_config import get_logger, new_trace_id, trace_id_scope

logger = get_logger(__name__)

st.set_page_config(page_title="Finance Compliance RAG", page_icon="📋", layout="wide")

if "history" not in st.session_state:
    st.session_state.history = []
if "selected" not in st.session_state:
    st.session_state.selected = None


st.title("📋 Finance Compliance RAG")
st.caption(
    "Retrieval-grounded answers over CSSF, DORA, and EBA regulatory text. "
    "**Advisory only — not legal advice.** Every statement is traceable to a "
    "cited source below; review before acting on it."
)


def confidence_badge(score: float) -> str:
    score = float(score or 0.0)
    if score >= 0.75:
        color = "green"
    elif score >= 0.5:
        color = "orange"
    else:
        color = "red"
    return f":{color}[**{score:.0%} confidence**]"


def _is_cited_in_answer(source_reference: str, answer_text: str) -> bool:
    """
    Heuristic only: the citation agent's "citations" list is every chunk
    retrieved and handed to the LLM as context, not just the ones the LLM
    actually referenced in its answer — those are different sets. This checks
    whether a chunk's reference literally appears inside a "[...]" citation
    bracket in the generated text, so the UI can show which sources the
    answer actually leans on vs. which were provided but went unused.
    """
    if not source_reference:
        return False
    for bracket in re.findall(r"\[([^\]]+)\]", answer_text or ""):
        if source_reference in bracket:
            return True
    return False


def render_citations(citations: list, answer_text: str = "") -> None:
    if not citations:
        st.caption("No citations returned.")
        return
    for c in citations:
        regulation = c.get("source_regulation", "")
        reference = c.get("source_reference") or c.get("chunk_id", "?")
        score = c.get("similarity_score")
        label = f"**{regulation} {reference}**".strip() if regulation else f"**{reference}**"
        score_txt = f" · similarity {score:.2f}" if isinstance(score, (int, float)) else ""
        excerpt = c.get("excerpt")
        if _is_cited_in_answer(reference, answer_text):
            status = ":green[✓ cited in answer]"
        else:
            status = ":gray[retrieved, not directly cited]"
        st.markdown(f"- {label}{score_txt} — {status}")
        if excerpt:
            st.caption(excerpt)


def render_entry(entry: dict) -> None:
    retrieval_result = entry["retrieval_result"]
    citation_result = entry["citation_result"]
    summary_result = entry["summary_result"]
    risk_result = entry["risk_result"]
    agent_citation = citation_result["agent_result"]

    trace_note = f" · trace `{entry['trace_id']}`" if entry.get("trace_id") else ""
    st.caption(f"Asked {entry['timestamp']}{trace_note}")
    st.markdown(f"> {entry['query']}")

    st.subheader("Answer")
    st.markdown(agent_citation.get("answer") or "_No answer returned._")
    st.markdown(confidence_badge(agent_citation.get("confidence", 0.0)))

    st.subheader("Sources")
    # citation_result["retrieved_chunks"] is the full retrieved set;
    # agent_citation["citations"] is now the narrower subset the LLM actually
    # cited (see citation_agent._extract_cited_chunks) — render_citations
    # wants the full set so it can label each source cited vs. uncited.
    render_citations(citation_result.get("retrieved_chunks", []), agent_citation.get("answer", ""))

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Executive Summary")
        st.info(summary_result.get("answer") or "_No summary available._")
    with col2:
        st.subheader("Risk Assessment")
        warnings = risk_result.get("warnings") or []
        if warnings:
            for w in warnings:
                st.warning(w)
        else:
            st.success("No material regulatory risks detected.")
        st.markdown(confidence_badge(risk_result.get("confidence", 0.0)))

    with st.expander("Raw agent output (debug / audit)"):
        st.markdown("**Retrieval**")
        st.json(retrieval_result)
        st.markdown("**Citation-bound answer**")
        st.json(citation_result)
        st.markdown("**Summarization**")
        st.json(summary_result)
        st.markdown("**Risk assessment**")
        st.json(risk_result)


with st.form("query_form"):
    query = st.text_area(
        "Regulatory query",
        height=100,
        placeholder=(
            "e.g. What are the management body's responsibilities for ICT risk "
            "governance under CSSF, DORA, and EBA?"
        ),
    )
    st.caption("Searches CSSF, DORA, and EBA together.")
    submitted = st.form_submit_button("Submit", type="primary")

if submitted and query.strip():
    trace_id = new_trace_id()
    with st.status("Processing query…", expanded=True) as status:
        try:
            with trace_id_scope(trace_id), wrappers.traced_query_run(trace_id, query):
                logger.info("query submitted", extra={"query": query})

                status.write("🔎 Retrieving relevant regulatory chunks…")
                retrieval_result = asyncio.run(wrappers.retrieval_chain.ainvoke({"query": query}))

                status.write("✍️ Generating citation-bound answer…")
                citation_result = asyncio.run(wrappers.citation_chain.ainvoke({
                    "query": query,
                    "retrieval_result": retrieval_result,
                }))
                agent_citation = citation_result["agent_result"]

                status.write("📝 Summarizing…")
                summary_result = asyncio.run(wrappers.summarization_chain.ainvoke({
                    "citation_result": agent_citation,
                }))

                status.write("⚠️ Assessing risk…")
                risk_result = asyncio.run(wrappers.risk_assessment_chain.ainvoke({
                    "citation_result": agent_citation,
                    "retrieval_result": retrieval_result,
                }))

                logger.info("query completed", extra={"query": query})

            status.update(label="Done", state="complete", expanded=False)
        except Exception as e:
            logger.error("query failed", extra={"query": query}, exc_info=True)
            status.update(label="Failed", state="error", expanded=True)
            st.error(f"Something went wrong processing this query: {e}")
            st.stop()

    entry = {
        "query": query,
        "trace_id": trace_id,
        "retrieval_result": retrieval_result,
        "citation_result": citation_result,
        "summary_result": summary_result,
        "risk_result": risk_result,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    st.session_state.history.append(entry)
    st.session_state.selected = len(st.session_state.history) - 1

# Rendered after any submission above is processed, so a just-completed
# query shows up immediately rather than on the next rerun.
with st.sidebar:
    st.header("Query History")
    if not st.session_state.history:
        st.caption("No queries yet this session.")
    else:
        for i, past in enumerate(reversed(st.session_state.history)):
            idx = len(st.session_state.history) - 1 - i
            label = past["query"][:60] + ("…" if len(past["query"]) > 60 else "")
            if st.button(label, key=f"hist_{idx}", use_container_width=True):
                st.session_state.selected = idx
        st.divider()
        if st.button("Clear history", use_container_width=True):
            st.session_state.history = []
            st.session_state.selected = None
            st.rerun()

if st.session_state.selected is not None and st.session_state.history:
    st.divider()
    render_entry(st.session_state.history[st.session_state.selected])
elif not st.session_state.history:
    st.info("Enter a query above to get started.")
