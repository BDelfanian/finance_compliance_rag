# Improvement Roadmap & Restructuring Plan

**Status:** Phase 0 applied (staged in the working tree, not committed, not
yet executed/tested — see `docs/09_current_state_and_known_issues.md` for
exactly what changed and what's still open). Phases 1–6 remain proposals.

## 1. Purpose

The prototype (docs 00–09) proves the pipeline end-to-end: ingestion →
chunking → retrieval → citation-bound generation → multi-agent orchestration.
It was built fast, over what the repo's git history shows as roughly two
active weeks of commits, and it has the rough edges of that pace: dead code,
inconsistent imports, no API/UI separation, minimal observability, and a
`requirements.txt` that was missing half its real dependencies until the
previous update. This document proposes how to take it from "working
prototype" to "defensible, extensible, observable system" — the four things
you asked for (full MLflow, full logging/traceability, a TypeScript UI, more
sources) plus a restructuring pass and a few additions I think the project
needs to support them.

## 2. Principles carried forward (non-negotiable)

Every workstream below must preserve what's already load-bearing in this
project (see `docs/00_project_overview.md` and `docs/decision_log.md`):

- No automated compliance decisions — every surface remains advisory.
- Every answer stays traceable to a specific, citable regulatory chunk.
- Retrieval hard filters (authority/jurisdiction/binding level) are never
  overridable by semantic similarity.
- Orchestration stays deterministic Python — no LangGraph or autonomous
  agent planning, even as the system grows.
- New ingestion stays human-controlled — automation may *propose* new
  sources or new versions of existing ones, but nothing is embedded or
  indexed without a review step.

## 3. Workstreams

### 3.1 Repository restructuring & hygiene

This should happen **first** — it's the foundation everything else builds on,
and doing it after adding an API/UI/eval layer means restructuring twice.

Concrete actions:
- Delete the empty stub files (`agents/*.py`, `app/api.py`, `app/cli.py`,
  `src/ui/streamlit_app.py`, `src/ui/test_orchestrator.py`,
  `src/ui/model_config.yaml`) or replace them with real content per §3.4.
- Fix the four broken/inconsistent imports documented in
  `docs/09_current_state_and_known_issues.md` (`cssf_parser.py`'s missing
  `base_parser`, the three stale `src.run_embeddings_retrieval` imports,
  `test_run.py`'s unprefixed import).
- Archive `src/draft/` (rename to `archive/chunking_v1/` or delete outright
  — it's disconnected from `chunking/registry.py` already) and consolidate
  the five Streamlit UIs down to one canonical file.
- Replace `setup.py` + bare `requirements.txt` with a single `pyproject.toml`
  (PEP 621), with optional dependency groups (`[project.optional-dependencies]`
  for `ui`, `dev`, `eval`) so `pip install -e ".[dev]"` is the one command
  anyone needs.
- Expand `.gitignore` to exclude `data/faiss/`, `data/retrieval_cache/`,
  `data/step5_cache/`, and `mlflow.db` — these are build/run artifacts, not
  source. See §3.6 for what replaces them (DVC or documented rebuild step).
- Add `.env.example` documenting `OPENAI_API_KEY` and any new config from
  §3.6's settings module, so setup doesn't rely on tribal knowledge
  (`notes.md`'s hardcoded `PYTHONPATH=E:\...` is a symptom of this gap).

### 3.2 Full MLflow application

Today, MLflow is used narrowly: `src/chains/step6_agent_wrappers_mlflow.py`
logs each agent's I/O as a JSON artifact per run, against a local SQLite file
(`mlflow.db`) that's committed to git. "Full" MLflow means:

- **Tracking server**: run `mlflow server` (Docker, see §3.6) backed by a
  real store (Postgres for metadata, S3/local filesystem or Azure/GCS for
  artifacts) instead of a file-based SQLite DB in the repo. Multi-user,
  queryable, and not a git-tracked binary blob that grows forever.
- **Parameters, not just artifacts**: log `chunking_version`, `embedding_model`,
  `similarity_threshold`, `top_k`, `prompt_version`, `llm_model` as MLflow
  *params* on each run, not buried inside JSON artifacts — this is what makes
  runs comparable in the MLflow UI.
- **Metrics**: log retrieval precision@k / MRR against `golden_queries.json`
  (§3.6 evaluation framework), answer latency, token counts, and estimated
  cost per query as MLflow *metrics*.
- **Experiments, not one flat run stream**: separate MLflow experiments for
  `retrieval-eval`, `generation-eval`, and `production-queries`, so ad hoc
  eval runs don't pollute the operational query log.
- **Model/prompt registry**: register the embedding model and the citation
  prompt template as versioned MLflow entities, so "what prompt produced this
  answer" is answerable by run ID, not by reading git blame on a Python
  f-string.
- **CI integration**: eval runs (§3.6) log to MLflow automatically on each PR,
  giving a permanent, comparable history of retrieval/generation quality over
  time — not just pass/fail.

### 3.3 Full logging & traceability

Current state: `print()` for MLflow logging failures, no structured logs, no
request correlation across agents, and the only persistent trace of a query
is whatever ends up in `data/retrieval_logs/`, `query_history.json`, and the
per-stage caches — three overlapping, inconsistent places.

Proposed:
- **Structured logging**: Python `logging` configured for JSON output
  (`python-json-logger` or stdlib `logging.config` + a JSON formatter), one
  logger per module, replacing all `print()` calls.
- **Trace/correlation ID**: generate one `trace_id` per user query in the
  orchestrator, thread it through every agent call and every retrieval/LLM
  call, and include it in every log line and MLflow run tag. This is what
  lets you answer "show me everything that happened for this one query"
  across logs, MLflow, and cache files.
- **OpenTelemetry spans**: wrap each agent (`retrieval`, `citation`,
  `summarization`, `risk_assessment`) and each external call (OpenAI
  embedding, OpenAI chat completion, FAISS search) in an OTel span, exported
  to a local collector (or Jaeger/Grafana Tempo in Docker) for latency
  waterfalls — this is the fastest way to see *why* a query was slow.
- **One durable audit log**: consolidate `query_history.json` (there are
  currently two copies — repo root and `data/`), `data/retrieval_logs/`, and
  ad hoc caches into a single append-only structured log (JSONL or a
  SQLite/Postgres table: `query_id, trace_id, timestamp, agent, input_ref,
  output_ref, confidence, warnings, mlflow_run_id`). Caches stay as caches;
  the audit log stays as the audit log — right now they're conflated.
- **LLM-specific observability (optional but recommended)**: a tool like
  Langfuse or Arize Phoenix gives prompt/response inspection, cost dashboards,
  and eval-in-the-loop out of the box, complementing MLflow's run-level
  tracking rather than replacing it. Worth a spike before committing.

### 3.4 TypeScript UI + API layer

You can't put a TypeScript frontend directly on top of the current code —
the orchestrator is a Python async function, and the Streamlit UIs call into
`src/` directly. The prerequisite is a real API layer.

- **FastAPI service** (fills the empty `app/api.py`): thin HTTP layer over
  `MultiAgentOrchestrator`, with Pydantic request/response models mirroring
  `AgentResult`. Endpoints: `POST /query` (full orchestrated run),
  `GET /query/{trace_id}` (audit lookup), `GET /health`. Streaming
  (Server-Sent Events) is worth it so the UI can show retrieval → citation →
  summary/risk progressively instead of one long spinner.
- **Typed contract**: generate a TypeScript client from FastAPI's OpenAPI
  schema (`openapi-typescript`), so the frontend's types can never drift from
  the backend's Pydantic models silently.
- **Frontend**: React + TypeScript + Vite. Recommended over Next.js here —
  this is an internal tool hitting one backend, not a site needing SSR/routing
  complexity. Core screens: query input with regulator filters (mirrors
  `ui_rag_full_advanced.py`), agent-by-agent results (mirrors
  `step6_read_only_ui.py`) with citations rendered as clickable source
  references, and a history/audit view backed by the durable audit log from
  §3.3.
- **Migration path**: keep one Streamlit UI alive as an internal/admin tool
  (fast to extend for one-off debugging) while the FastAPI + TS stack becomes
  the primary interface. Don't try to port every existing Streamlit feature
  1:1 — audit which of the five current UIs' features are actually used.

### 3.5 Enriching the source database

Two separate things here: finishing what's started, and adding breadth.

**Finish what's started:**
- GDPR is already extracted (`data/processed/extracted_text/gdpr_regulation.txt`)
  but never chunked or indexed. Lowest-effort addition — the article-based
  chunking strategy already built for DORA is directly reusable (GDPR is
  also EU-Regulation-structured, article-based).

**Candidate new sources**, roughly in order of relevance/overlap with what's
already covered:
- **NIS2 Directive** — cybersecurity, heavy overlap with DORA; good test of
  cross-regulation risk detection (the risk agent could flag where DORA and
  NIS2 obligations overlap or conflict).
- **MiCA** (Markets in Crypto-Assets) — EU regulation, same
  Article-based chunking pattern as DORA, extends coverage to digital assets.
- **ECB/EIOPA/ESMA guidelines** — broadens beyond banking-only (EIOPA =
  insurance, ESMA = securities), same "guidelines → paragraph-level"
  chunking pattern already built for EBA.
- **Other national regulators' circulars** (BaFin, ACPR, DNB, FCA) if
  multi-jurisdiction comparison is a goal — this is the biggest lift, since
  each will likely need its own structural parser like `cssf_parser.py`.

**Structural change needed to scale this**: right now every new authority
means a new hand-written `<authority>_cleaning.py` / `<authority>_parser.py`
/ `<authority>_validate_chunks.py` triplet. Before adding many more sources,
worth extracting the common pattern (noise removal, structural unit
detection via numbering regex, chunk assembly, validation) into a shared base
implementation that per-authority modules configure rather than reimplement.
This is exactly what the now-orphaned `src/chunking/cssf/cssf_parser.py` +
missing `base_parser.py` were apparently attempting — worth reviving that
idea deliberately instead of leaving it as dead code.

Also worth a **semi-automated ingestion queue**: a scheduled job that checks
official sources (CSSF website, EUR-Lex) for new/updated documents and drops
them into a `pending_review/` queue with a diff against the last indexed
version, rather than fully automated scraping-and-embedding. This preserves
the "no ingestion without human approval" principle while removing the
manual polling burden.

### 3.6 Other recommended components

- **Evaluation framework**: `golden_queries.json` currently has 2 entries and
  only covers retrieval. Expand to a proper eval set (aim for 30–50 queries
  spanning all regulators, including adversarial/no-answer cases) and add
  generation-quality metrics — faithfulness/citation-accuracy scoring via an
  LLM-judge (RAGAS is a reasonable starting library) alongside retrieval
  precision@k/MRR. This is what makes the MLflow metrics in §3.2 meaningful
  and gives CI something to gate on.
- **CI/CD**: GitHub Actions workflow running `ruff`/`black` (lint/format),
  `mypy` (typing — the codebase already uses `TypedDict`, worth going
  further), `pytest`, and the eval suite on every PR. Fail the build on a
  retrieval/generation regression against golden queries, not just on test
  failure.
- **Centralized config**: a `pydantic-settings`-based `Settings` object
  replacing the scattered module-level constants (`VECTOR_DIM`,
  `SIMILARITY_THRESHOLD`, `K_NEAREST`, `CACHE_DIR`, cache paths duplicated
  across `run_embeddings_retrieval.py` and `citation_bound_answer_generation.py`).
  One source of truth, environment-overridable, and it's what the API layer
  and eval framework will both need anyway.
- **Prompt versioning**: move the citation-bound prompt out of the inline
  f-string in `generate_citation_bound_answer` into a versioned template file
  (e.g. `prompts/citation_bound_v1.md`), referenced by version string that
  gets logged to MLflow (§3.2). Prompt changes become reviewable diffs with
  history, not silent edits.
- **Human-in-the-loop review workflow**: a lightweight
  approve/reject/annotate action on generated answers (in the TS UI),
  persisted with the audit log. Doubles as the compliance sign-off record
  the design docs already call for (`docs/06`'s MRM sign-off section) and as
  a growing eval/feedback dataset.
- **Data lifecycle management**: move `data/raw/`, `data/faiss/`,
  `data/retrieval_cache/`, `data/step5_cache/` out of plain git and into DVC
  (or documented external storage), addressing the "unbounded binary growth
  in git" issue from `docs/09`. Git keeps code, chunk JSON, and config;
  DVC (or equivalent) tracks large/binary/rebuildable artifacts with
  versioning but without bloating the git history.
- **Cost/usage tracking**: log OpenAI token usage and estimated $ cost per
  query as MLflow metrics and in the audit log — necessary before this scales
  past a personal prototype, and cheap to add now while wiring up MLflow
  metrics anyway.
- **Security hardening**: given regulatory/financial subject matter, add
  basic prompt-injection resistance (retrieved chunk text is regulatory
  language you control, but treat it as untrusted input to the LLM call
  regardless), input validation on the future API, and a documented data
  classification note confirming no confidential data enters the pipeline
  (already a stated principle — worth an explicit check/test, not just a
  docs claim).
- **Containerization**: `Dockerfile` for the FastAPI service +
  `docker-compose.yml` bringing up API, MLflow server, and (if adopted) a
  vector DB together — makes the "how do I run this" answer one command
  instead of the current multi-step manual setup.
- **Vector store scalability (later, optional)**: FAISS + pickle files is
  fine at current scale (a few thousand chunks) but has no concurrent-write
  story and no metadata-filtering-at-the-DB-layer. If source count grows
  significantly (§3.5), evaluate migrating to Qdrant or pgvector — not
  urgent, flagged here so it's a deliberate later decision rather than a
  surprise rewrite.

## 4. Proposed target repository structure

```
finance_compliance_rag/
├── pyproject.toml                 # replaces setup.py + requirements.txt
├── .env.example
├── .gitignore                     # excludes data artifacts, mlflow.db
├── README.md
├── docs/                          # unchanged convention, 00-10+
├── prompts/                       # NEW: versioned prompt templates
├── src/finance_compliance_rag/
│   ├── config.py                  # NEW: centralized settings
│   ├── ingestion/
│   ├── chunking/
│   │   ├── base/                  # NEW: shared parser/cleaner/validator base
│   │   ├── cssf/  dora/  eba/  gdpr/
│   ├── retrieval/
│   ├── generation/
│   ├── agents/
│   ├── orchestrator/
│   ├── observability/             # NEW: logging, tracing, mlflow helpers
│   └── evaluation/                # NEW: golden query runner, metrics
├── apps/
│   ├── api/                       # NEW: FastAPI service
│   └── web/                       # NEW: React + TypeScript UI
├── ui_streamlit/                  # ONE retained admin/debug UI
├── tests/                         # moved to top level (pytest convention)
├── docker/
│   ├── Dockerfile.api
│   └── docker-compose.yml
├── data/                          # small fixtures only; rest via DVC
└── .github/workflows/ci.yml
```

## 5. Phased roadmap

| Phase | Goal | Key deliverables | Depends on |
|---|---|---|---|
| **0. Cleanup & hygiene** ✅ | Stable foundation | Fixed broken/inconsistent imports, deleted stub files, consolidated 5 UIs → 2, `pyproject.toml`, `.gitignore` for data artifacts, `.env.example` | — |
| **1. Observability foundation** | See what the system is doing | Structured logging, trace IDs, centralized config, MLflow tracking server (Docker), params/metrics logging | Phase 0 |
| **2. Evaluation framework** | Make quality measurable | Expanded golden queries, retrieval + generation metrics, CI gate, MLflow eval experiment | Phase 1 |
| **3. API layer** | Decouple UI from pipeline | FastAPI service, typed schemas, streaming endpoint, OpenAPI → TS client generation | Phase 0 |
| **4. TypeScript UI** | Real frontend | React+TS app: query, agent-by-agent results, audit/history view | Phase 3 |
| **5. Source enrichment** | Broader coverage | GDPR chunking/indexing, shared base parser, 1–2 new regulators (NIS2/MiCA suggested first) | Phase 0, benefits from Phase 2 |
| **6. Hardening** | Ready for heavier use | DVC for data artifacts, containerization, cost tracking, human-review workflow, security checks | Phases 1–5 |

Phases 0 and 3 can start in parallel; everything else is easier once 0 is
done. Phase 5's new-source work benefits from Phase 2 existing (so new
sources come with eval coverage immediately) but doesn't strictly require it.

## 6. Risks & trade-offs to weigh

- **DVC vs. staying on plain git for data**: DVC adds tooling overhead; if
  the dataset stays small (a handful of PDFs, current FAISS index sizes),
  it may be simpler to just `.gitignore` the rebuildable artifacts and accept
  a "run the pipeline once after clone" setup step instead of adopting DVC.
- **FastAPI+React vs. extending Streamlit further**: Streamlit is faster to
  iterate on but caps out on UX control and doesn't give you a typed contract
  with a future non-Python consumer. Worth confirming this is actually going
  toward a real multi-user tool before paying the React/TS setup cost.
- **MLflow server vs. staying local-file**: a real tracking server is more
  useful but is one more service to run/operate. Docker Compose makes this
  low-friction; still worth deciding if that operational overhead is wanted
  yet.
- **How many new sources at once**: each new authority is real per-source
  engineering (structural parser + validation rules + golden queries), even
  with a shared base. Recommend 1–2 sources per iteration, not a batch.

## 7. Suggested immediate next step

Phase 0 is applied — see `docs/09_current_state_and_known_issues.md` for the
full list of what changed. It has **not been run** (no Python environment was
available during the cleanup), so the actual next step is: install
(`pip install -e ".[dev]"`), run `pytest`, launch both Streamlit UIs, and fix
whatever surfaces. Only after that's green is it worth reviewing and
committing, then moving to Phase 1 (observability) and/or Phase 3 (API layer,
which can start in parallel).
