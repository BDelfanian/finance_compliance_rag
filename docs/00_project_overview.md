# Project Overview

## Purpose

This project explores the use of Retrieval-Augmented Generation (RAG)
and multi-agent AI workflows to support compliance risk assessment
over unstructured financial regulatory documents.

The prototype is designed as a public-data analogue of internal
compliance review tools used in regulated financial institutions.

## Current Implementation Status

As of this update, all six planned pipeline stages (docs 02–08) are
implemented and exercised by tests and Streamlit UIs:

1. Manual, traceable data ingestion (CSSF, DORA, EBA, GDPR PDFs)
2. Text extraction to clean UTF-8 (pdfplumber)
3. Regulation-aware chunking (section / article / paragraph, per authority)
4. Segmented FAISS retrieval with symbolic hard filters + semantic search
5. Citation-bound answer generation (GPT-5 mini), cached
6. Deterministic multi-agent orchestration (retrieval, citation, summarization,
   risk assessment agents) with MLflow lineage logging

GDPR text has been extracted but is not yet chunked or indexed — it is
data on hand, not yet part of the retrieval scope.

See [docs/09_current_state_and_known_issues.md](09_current_state_and_known_issues.md)
for a code-verified inventory of what's active vs. leftover/unused, and known
gaps that have not yet been addressed.

## Scope (MVP)

Included:
- Regulatory documents from CSSF and EU authorities (CSSF, DORA, EBA; GDPR extracted only)
- Text extraction and regulation-aware chunking
- Segmented, filtered, explainable retrieval
- Citation-bound answer generation with inline source references
- Multi-agent summarization and risk/coverage-gap flagging, with confidence scoring
- Deterministic orchestration and audit-trail logging (MLflow)

Excluded (by design, not just "not yet built"):
- Automated compliance decision-making — every agent output is advisory and
  requires human review; the orchestrator does not gate real-world actions
- Proprietary or confidential data — only public regulatory texts are used
- Model fine-tuning — retrieval and generation rely on off-the-shelf OpenAI models
- Agentic frameworks (LangGraph, autonomous planning) — orchestration is
  hand-written, deterministic Python for auditability (see decision log)

## Guiding Principles

- Traceability of sources
- Explainability over performance
- Human-in-the-loop oversight
- Reproducibility
