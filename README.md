# AI-Enabled Compliance Risk Assessment (Prototype)

This project explores how retrieval-grounded, multi-agent AI systems can support
compliance risk assessment over unstructured financial regulatory documents, with
explicit focus on explainability, traceability, and human oversight.

It is a **public-data prototype**, built as an analogue of internal compliance
review tools used in regulated financial institutions (banks, PSPs, investment
firms) — not a production system, and not a source of legal advice.

## Status

All six planned pipeline stages are implemented end-to-end:

| Stage | What it does | Doc |
|---|---|---|
| 1. Data ingestion | Manual, traceable collection of source PDFs | [docs/02](docs/02_data_ingestion.md) |
| 2. Text extraction | PDF → clean UTF-8 text via pdfplumber | [docs/03](docs/03_text_extraction.md) |
| 3. Chunking | Regulation-aware chunking (section/article/paragraph) | [docs/05](docs/05_chunking_strategy.md) |
| 4. Embeddings & retrieval | Per-regulator FAISS stores, hard-filter + semantic search | [docs/06](docs/06_retrieval_design.md) |
| 5. Citation-bound generation | GPT-5 mini answers strictly grounded in retrieved chunks | [docs/07](docs/07_answer_generation.md) |
| 6. Multi-agent orchestration | Retrieval → Citation → Summarization/Risk agents, deterministic orchestrator | [docs/08](docs/08_multi_agent_orchestration.md) |

See [docs/09_current_state_and_known_issues.md](docs/09_current_state_and_known_issues.md)
for an accurate, code-verified snapshot of what's implemented, what's dead/unused
code left over from earlier iterations, and known gaps.

Next planned work — full MLflow tracking, structured logging/traceability, a
TypeScript UI on a new API layer, more regulatory sources, and a restructuring
pass — is proposed in
[docs/10_improvement_roadmap.md](docs/10_improvement_roadmap.md) (not yet implemented).

## Regulatory sources covered

- CSSF Circular 20/750 (Luxembourg, ICT & security management)
- DORA — Regulation (EU) 2022/2554 (Digital Operational Resilience Act)
- EBA Guidelines on Outsourcing Arrangements
- GDPR (extracted, not yet chunked/indexed)

Full provenance in [docs/01_data_inventory.md](docs/01_data_inventory.md).

## Architecture (current)

```
User Query
    │
    ▼
MultiAgentOrchestrator (src/orchestrator/multi_agent_orchestrator.py)
    ├── Retrieval Agent        → FAISS (cssf / dora / eba), hard filters + cosine search
    ├── Citation Agent         → GPT-5 mini, citation-bound answer (cached)
    ├── Summarization Agent    → conservative, citation-only compression
    └── Risk Assessment Agent  → coverage/confidence gap detection
    │
    ▼
Aggregated response (answer + summary + risk + fused confidence + audit trail)
    │
    ▼
Streamlit UI (src/ui/step6_read_only_ui.py) / MLflow lineage (src/chains/step6_agent_wrappers_mlflow.py)
```

Agents are plain async Python functions wrapped as LangChain `RunnableLambda`s
purely for a consistent execution interface — **no orchestration logic lives in
LangChain**, and no agent framework (LangGraph etc.) is used. This is a deliberate
governance choice: control flow stays deterministic and auditable. See
[docs/decision_log.md](docs/decision_log.md).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

pip install -e ".[dev]"     # installs the project (see pyproject.toml) + pytest

cp .env.example .env        # then fill in OPENAI_API_KEY
```

`pip install -e .` makes `src` importable as a package root, matching the
`from src.xxx import yyy` convention used throughout the codebase — no manual
`PYTHONPATH` juggling required.

## Running it

```bash
# Rebuild chunks for one or all regulators
python src/run_chunking.py

# Multi-agent orchestrator, CLI smoke test
python src/test_run.py

# Full multi-agent UI (retrieval + citation + summary + risk)
streamlit run src/ui/step6_read_only_ui.py

# Retrieval-only UI with CSV/PDF export
streamlit run src/ui/ui_rag_full_advanced.py

# Tests
pytest src/tests -v
```

First run of retrieval/generation builds FAISS indexes from
`data/processed/chunks/*.json` and calls OpenAI for embeddings — this requires
`OPENAI_API_KEY` and network access. Indexes and query results are then cached
under `data/faiss/`, `data/retrieval_cache/`, and `data/step5_cache/`.

## Guiding principles

- Traceability of every answer to a specific, citable regulatory source
- Explainability over raw performance
- Human-in-the-loop oversight — the system does not make compliance decisions
- Reproducibility and auditability (deterministic orchestration, MLflow lineage)

## Explicit boundaries (out of scope)

- Automated compliance decision-making — outputs require human review
- Legal advice or authoritative legal interpretation
- Proprietary or confidential documents — only public regulatory texts are used
- Model fine-tuning
- Production deployment / uptime guarantees — this is a research prototype
