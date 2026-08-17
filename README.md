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

Phases 1–4 (observability foundation, evaluation framework, a FastAPI layer
over the orchestrator, and a React/TypeScript frontend) are complete. Next
planned work — more regulatory sources and further hardening (DVC, cost
tracking, human-review workflow) — is proposed in
[docs/10_improvement_roadmap.md](docs/10_improvement_roadmap.md).

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
    ├── Retrieval Agent        → FAISS (cssf / dora / eba / nis2), hard filters + cosine search
    ├── Citation Agent         → GPT-5 mini, citation-bound answer (cached)
    ├── Summarization Agent    → conservative, citation-only compression
    └── Risk Assessment Agent  → coverage/confidence gap detection
    │
    ▼
Aggregated response (answer + summary + risk + fused confidence + audit trail)
    │
    ├──▶ FastAPI service (app/api.py) — POST /query, /query/stream (SSE), GET /query/{trace_id}
    │       │
    │       ▼
    │   React/TS frontend (web/) — primary UI, progressive SSE rendering
    │
    ▼
Streamlit UIs (src/ui/*.py, admin/debug only) / MLflow lineage (src/chains/step6_agent_wrappers_mlflow.py)
```

`MultiAgentOrchestrator` calls `src/chains/step6_agent_wrappers_mlflow.py`'s
MLflow-wrapped agent chains directly, and is `app/api.py`'s only caller — the
one production path. The two Streamlit UIs (`step6_read_only_ui.py`,
`ui_rag_full_advanced.py`) call into that same chain layer independently,
bypassing the API; kept deliberately as admin/debug tools rather than
migrated, since neither has an API equivalent for its debug-only features
(see `docs/09`'s "Phase 4" section for the reasoning). `web/` is the primary
interface for actually asking the pipeline a question.

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

# FastAPI service (POST /query, POST /query/stream, GET /query/{trace_id}, GET /health)
uvicorn app.api:app --reload --port 8000
# Interactive API docs: http://localhost:8000/docs

# React/TS frontend (primary UI) — needs the API running above
cd web && npm install && npm run dev
# http://localhost:5173

# Tests
pytest src/tests -v
```

### Running the API in Docker

```bash
docker compose -f docker/docker-compose.yml up -d --build mlflow api
curl http://localhost:8000/health
```

Brings up the API alongside a real MLflow tracking server on the same
Docker network (`MLFLOW_TRACKING_URI=http://mlflow:5000` is set for the `api`
service in `docker-compose.yml`); `data/faiss`, the retrieval/step5 caches,
and `data/audit_log` persist across restarts via named volumes.

### Regenerating the TypeScript API contract

```bash
python -m app.export_openapi        # writes client/openapi.json
cd client && npm install && npm run generate   # writes client/api-types.ts
```

`web/` (the frontend) imports its request/response types directly from
`client/api-types.ts` — regenerate it after any `app/schemas.py` or
`app/api.py` change, rather than hand-editing types in `web/`. See
[client/README.md](client/README.md) and [web/README.md](web/README.md).

First run of retrieval/generation builds FAISS indexes from
`data/processed/chunks/*.json` and calls OpenAI for embeddings — this requires
`OPENAI_API_KEY` and network access. Indexes and query results are then cached
under `data/faiss/`, `data/retrieval_cache/`, and `data/step5_cache/`.

## Configuration

All settings (model names, retrieval thresholds, cache paths, MLflow config)
are centralized in `src/config.py` (`pydantic-settings`), overridable via `.env`
or real environment variables — see `.env.example` for the full list. Only
`OPENAI_API_KEY` is required; everything else has a working default.

## Observability

Every query gets one `trace_id`, threaded through structured JSON logs
(`src/observability/logging_config.py`) and tagged on every MLflow run, so a
single ID answers "what happened for this query" across both.

By default, MLflow logs locally (`mlflow.db` + `data/mlflow_artifacts/`, no
server needed). To use a real tracking server instead:

```bash
docker compose -f docker/docker-compose.yml up -d
# then in .env:
# MLFLOW_TRACKING_URI=http://localhost:5000
```

Browse runs at http://localhost:5000 (or the local UI: `mlflow ui --backend-store-uri sqlite:///mlflow.db`).

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
