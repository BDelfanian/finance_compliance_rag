# Improvement Roadmap & Restructuring Plan

**Status:** Phases 0, 1, 2, 3, and 4 are complete (executed, tested, and
verified live — see `docs/09_current_state_and_known_issues.md` for exactly
what changed). Phases 5–6 remain proposals.

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

**Status (2026-08-16, Phase 1 complete): tracking server (Docker), params,
and metrics are done.** `docker/docker-compose.yml` + `docker/Dockerfile.mlflow`
bring up a real `mlflow server` (sqlite-backed, single-node — not the
Postgres/S3 "real store" described below, which is still future work).
`src/config.py`'s `mlflow_tracking_uri` switches between it and the local
default with one env var. `step6_agent_wrappers_mlflow.py` now logs params
(`embedding_model`, `llm_model`, `similarity_threshold`, `k_nearest`,
`citation_top_k`) and metrics (`confidence`, `latency_seconds`,
`warnings_count`) on every run, and nests all four agent runs for one query
under a single parent run (`traced_query_run`, tagged with `trace_id`) — see
docs/09's "Fixed" section for what was verified live, including against the
real Dockerized server. **Update (Phase 2, 2026-08-16)**: eval runs now log
to their own `finance_compliance_rag_eval` experiment, confirmed live to be
distinct from the production `finance_compliance_rag_agents` one (see
`src/evaluation/run_eval.py`) — the "separate experiments per purpose" and
"CI integration" items below are done. Still open: Postgres/S3 backing
store, model/prompt registry.

Today, MLflow is used narrowly: `src/chains/step6_agent_wrappers_mlflow.py`
logs each agent's I/O as a JSON artifact per run, against a local SQLite file
(`mlflow.db`, gitignored as of Phase 0). "Full" MLflow means:

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

**Status (2026-08-16): structured logging + trace ID done; the rest of this
section (OTel spans, durable audit log, LLM observability tool) is still
proposal only.** `src/observability/logging_config.py` now provides JSON log
output and a `contextvars`-based `trace_id` generated once per query (in
`MultiAgentOrchestrator.run()` and in the live UI at form submission),
included in every structured log line, `audit_trail["trace_id"]`, and tagged
on every MLflow run. See `docs/09_current_state_and_known_issues.md`'s
"Fixed (2026-08-16)" section for what was verified. `print()` in
`step6_agent_wrappers_mlflow.py` was replaced; other `print()` call sites (if
any remain elsewhere) were not audited in this pass.

Originally proposed, now partially done:
- **Structured logging**: Python `logging` configured for JSON output
  (`python-json-logger` or stdlib `logging.config` + a JSON formatter), one
  logger per module, replacing all `print()` calls. ✅ done via stdlib
  `logging` (no new dependency), scoped to the app's own logger namespace.
- **Trace/correlation ID**: generate one `trace_id` per user query in the
  orchestrator, thread it through every agent call and every retrieval/LLM
  call, and include it in every log line and MLflow run tag. This is what
  lets you answer "show me everything that happened for this one query"
  across logs, MLflow, and cache files. ✅ done, via a contextvar rather than
  threading it as an explicit parameter through every agent signature —
  works because `asyncio.gather()` and `asyncio.run()` both propagate the
  current `contextvars.Context` into spawned tasks.
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

**Status (2026-08-16, Phase 3 complete): the FastAPI service, typed schemas,
streaming endpoint, and generated TypeScript types are done.** `app/api.py`
is a thin HTTP layer over `MultiAgentOrchestrator` — which was itself
switched onto the MLflow-wrapped chains as part of this phase, resolving the
orchestrator/UI chain divergence `docs/09` used to flag (see that doc's
"Phase 3 (API layer) — complete" section for what changed and what was
verified live, including two real bugs only Docker/live-server testing
caught). Endpoints: `POST /query`, `POST /query/stream` (SSE), `GET
/query/{trace_id}` (backed by a new file-based `src/observability/audit_store.py`
— a lightweight stand-in for §3.3's full durable audit log, not that log
itself), `GET /health`. `app/export_openapi.py` + `client/` generate and
commit `client/api-types.ts` via `openapi-typescript`. `docker/Dockerfile.api`
+ an `api` service in `docker/docker-compose.yml` containerize it alongside
the existing `mlflow` service. Still open, deferred to Phase 4: the actual
React/TS frontend below, and switching the live Streamlit UI to call the API
instead of the chain layer directly (the "migration path" bullet).

- ~~**FastAPI service**~~ ✅ done — see above.
- ~~**Typed contract**~~ ✅ done — see above.
- ~~**Frontend**~~ ✅ done, 2026-08-16: React + TypeScript + Vite app in
  `web/`, importing types directly from `client/api-types.ts`. One query
  screen (not five Streamlit-style panels): a query form, a live SSE stage
  timeline, and agent-by-agent results (Answer/Sources/Executive
  Summary/Risk Assessment) rendering progressively via `POST /query/stream`
  as each stage completes, plus a history/audit view backed by `GET
  /query/{trace_id}`. Regulator filtering was **not** added as a real
  control — `QueryRequest` has no such field and adding one would mean
  orchestration-layer changes out of scope for a frontend phase — so it's
  shown as informational context only. See `docs/09`'s "Phase 4 (TypeScript
  UI) — complete" section for what was verified live, including a real
  headless-browser run through both servers with zero console/network
  errors.
- ~~**Migration path**~~ ✅ decided, 2026-08-16: **both** existing Streamlit
  UIs stay as admin/debug tools rather than being ported or deleted —
  `step6_read_only_ui.py` (full pipeline demo/debug) and
  `ui_rag_full_advanced.py` (retrieval-only debug tool with adjustable
  top-K/threshold, CSV/PDF export, and term highlighting — functionality
  with no API equivalent). `web/` becomes the primary interface for actually
  answering a query, going through `app/api.py` rather than the chain layer
  directly. See `docs/09`'s "Migration path" subsection for the full
  reasoning.

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

- ~~**Evaluation framework**~~ ✅ done 2026-08-16 (Phase 2):
  `src/tests/golden_queries.json` expanded from 2 to 53 entries (46
  standard + 7 adversarial/no-answer), every one validated against live
  retrieval before being committed. `src/evaluation/metrics.py` adds
  precision@5/MRR; `src/evaluation/llm_judge.py` adds faithfulness/citation-
  accuracy via a direct OpenAI judge call (RAGAS evaluated and rejected —
  see the module's docstring). `src/evaluation/run_eval.py` runs the full
  set, logs to its own `finance_compliance_rag_eval` MLflow experiment
  (confirmed live to be a distinct experiment from the production
  `finance_compliance_rag_agents` one), and gates on regression against a
  committed `data/eval_baseline.json`. See `docs/09`'s "Phase 2 (Evaluation
  framework) — complete" section for what was verified live, including a
  real bug found (a judge-call failure was silently erasing an unrelated,
  already-correct abstention metric — fixed) and a real external blocker hit
  (the OpenAI account ran out of credits mid-run, confirming the gate
  fails safe rather than silently passing). Still open: CI lint/type
  checking (`ruff`/`black`/`mypy`) — the item below.
- **CI/CD (lint & type checking)**: GitHub Actions (`.github/workflows/ci.yml`)
  now runs `pytest` and the eval regression gate on every push/PR (Phase 2,
  done). Still proposal-only: `ruff`/`black` (lint/format) and `mypy`
  (typing — the codebase already uses `TypedDict`, worth going further).
- ~~**Centralized config**~~ ✅ done 2026-08-16: `src/config.py`'s
  `pydantic-settings`-based `Settings` (`get_settings()`, `lru_cache`d)
  replaced the scattered module-level constants (`VECTOR_DIM`,
  `SIMILARITY_THRESHOLD`, `K_NEAREST`, cache paths, model names) across
  `run_embeddings_retrieval.py`, `citation_bound_answer_generation.py`, and
  `step6_agent_wrappers_mlflow.py`. Every field is environment-overridable
  (loads `.env` automatically — no more manually exporting `OPENAI_API_KEY`
  before running tests/scripts) and documented in `.env.example`. Still true:
  this is what the future API layer and eval framework will both need.
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
| **1. Observability foundation** ✅ | See what the system is doing | Structured logging, trace IDs, centralized config, MLflow tracking server (Docker), params/metrics logging | Phase 0 |
| **2. Evaluation framework** ✅ | Make quality measurable | Expanded golden queries (53), retrieval + generation metrics, CI gate, MLflow eval experiment | Phase 1 |
| **3. API layer** ✅ | Decouple UI from pipeline | FastAPI service, typed schemas, streaming endpoint, OpenAPI → TS client generation | Phase 0 |
| **4. TypeScript UI** ✅ | Real frontend | React+TS app (`web/`): query form, SSE-driven agent-by-agent results, audit/history view via `GET /query/{trace_id}` | Phase 3 |
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

Phases 0, 1, 2, 3, and 4 are done, tested, and verified live — see
`docs/09_current_state_and_known_issues.md` for the full list of what
changed and what's still open (notably: dependency versions still unpinned;
a real generation-quality issue the Phase 2 eval framework surfaced, where
the LLM occasionally abstains incorrectly on a well-covered query due to
sampling variance; the CI eval gate's hard dependency on the configured
OpenAI account having credits; the audit store having no retention policy;
and, new from Phase 4, both Streamlit UIs remaining as deliberately-kept
admin/debug tools rather than being migrated onto `app/api.py`). Next up:
**Phase 5 (source enrichment)** — GDPR is already extracted but unchunked,
the lowest-effort addition, and benefits from Phase 2's eval framework
already existing so new sources come with eval coverage immediately. Phase 6
(hardening) is the other option if broader coverage isn't the priority yet.
