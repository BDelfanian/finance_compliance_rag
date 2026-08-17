# Current State and Known Issues

This document is a code-verified snapshot of what is implemented, what is
leftover from earlier iterations, and what has (and hasn't) been fixed. It
complements docs 00–08, which describe intended design, and
`docs/10_improvement_roadmap.md`, which proposes further work.

**Update (Phase 0 cleanup applied, then actually run end-to-end):** the
issues originally logged here (see §"Resolved in Phase 0" below) were fixed
in the working tree. A venv was then created (`.venv`, Python 3.12), the
project installed (`pip install -e ".[dev]"`), the full test suite run
against live OpenAI API calls, and the Streamlit UI (`step6_read_only_ui.py`)
launched and exercised with a real query end-to-end. All 29 tests pass; a
live query flows correctly through retrieval → citation-bound generation →
summarization → risk assessment. Two **additional real bugs** were found
this way — by execution, not static reading — and fixed; see
§"Resolved by running the app" below.

**Update (Phase 1 complete, 2026-08-16):** the citation-semantics gap, MLflow
logging, structured logging/trace IDs, centralized config, and a Dockerized
MLflow tracking server are all done — see §"Phase 1 (Observability
foundation) — complete" below. 31/31 tests pass.

**Update (Phase 2 complete, 2026-08-16):** the evaluation framework —
expanded golden queries, retrieval + generation metrics, a dedicated MLflow
eval experiment, and a CI regression gate — is done. See §"Phase 2
(Evaluation framework) — complete" below. 191/191 tests pass.

**Update (Phase 3 complete, 2026-08-16):** a FastAPI service (`app/api.py`)
now sits in front of `MultiAgentOrchestrator`, which was itself switched onto
the MLflow-wrapped chains — resolving the "two chain paths" issue this doc
used to document below as open. See §"Phase 3 (API layer) — complete" below.
199/199 tests pass.

**Update (Phase 4 complete, 2026-08-16):** a React + TypeScript frontend
(`web/`) now sits on top of `app/api.py`, using `POST /query/stream` for
progressive, stage-by-stage rendering. See §"Phase 4 (TypeScript UI) —
complete" below for what was built and verified live (a real headless-browser
run through both servers). No Python code changed in this phase, so the test
count is unchanged at 199/199.

## Repository map (current)

```
app/                       FastAPI service — Phase 3
  api.py                    POST /query, POST /query/stream (SSE), GET /query/{trace_id}, GET /health
  schemas.py                 Pydantic request/response models mirroring AgentResult
  export_openapi.py           Dumps app.api.app's OpenAPI schema to client/openapi.json
client/                    Generated TypeScript API contract — Phase 3
  openapi.json, api-types.ts  Committed, regenerated via app/export_openapi.py + `npm run generate`
web/                       React + TypeScript frontend — Phase 4
  src/api/                   fetch-based client, hand-parsed SSE stream, view-model normalization
  src/components/            QueryForm, StageTimeline, ResultView, CitationList, ConfidenceBadge, HistorySidebar
  src/hooks/useQueryRun.ts    Drives POST /query/stream, folds stage events into one RunState
src/
  agents/                STEP 6 agents: retrieval, citation, summarization, risk_assessment
  orchestrator/          MultiAgentOrchestrator (now the one chain path — see below), agent schema/validation
  chains/                MLflow-wrapped agent chains (step6_agent_wrappers_mlflow.py) — used by
                          MultiAgentOrchestrator directly since Phase 3
  generation/            STEP 5 citation-bound answer generation (GPT-5 mini)
  retrieval/             STEP 4 embeddings + FAISS retrieval
  chunking/               Active chunking pipeline (cssf/dora/eba/gdpr/nis2), registry-driven
  observability/           Structured logging + trace-ID context (logging_config.py) — Phase 1;
                            file-based audit_store.py (data/audit_log/) — Phase 3
  evaluation/               Golden-query eval runner, metrics, LLM-judge (run_eval.py) — Phase 2
  config.py                Centralized pydantic-settings Settings — Phase 1
  ui/                      Two Streamlit UIs (step6_read_only_ui.py, ui_rag_full_advanced.py) — still call
                            src.chains.step6_agent_wrappers_mlflow directly, not the API (see known issue below)
  tests/                   pytest suite for retrieval, agents, orchestrator, MLflow lineage, the API (test_api.py),
                            golden_queries.json (53 cases — Phase 2)
archive/                   Superseded/dead code and data, kept for reference, not imported by anything active
  chunking_v1/             Earlier chunking iteration (formerly src/draft/) + its chunk output
  ui_legacy/                Four superseded Streamlit UIs (ui_rag.py, ui_rag_full.py, step5_*.py)
  unused/                  cssf_parser.py (dead OOP parser attempt, imported a since-deleted base class)
  query_history_snapshots/ Two orphaned, never-code-referenced query_history.json exports
data/
  raw/                     Source PDFs (CSSF, DORA, EBA, GDPR) — tracked in git
  processed/               Extracted text + chunks — tracked in git
  faiss/, retrieval_cache/, step5_cache/, retrieval_logs/, mlflow_artifacts/, audit_log/ — gitignored, rebuilt/repopulated on first run
  eval_results/             Per-run eval JSON (src/evaluation/run_eval.py) — gitignored — Phase 2
  eval_baseline.json        Committed regression-gate baseline, updated deliberately via
                             `--update-baseline` — Phase 2
docker/                    Dockerfile.mlflow, Dockerfile.api + docker-compose.yml (mlflow + api services) — Phase 1 / 3
docs/                      Design docs (00–08) + this file + decision log + roadmap
.github/workflows/ci.yml    pytest + eval regression gate on every push/PR — Phase 2
pyproject.toml              Single packaging/dependency source of truth (replaces setup.py + requirements.txt)
.env.example                Documents every src/config.py Settings field — Phase 1
```

## What's actually implemented (verified against code, not docs)

- **Chunking**: `src/chunking/registry.py` drives cssf/dora/eba cleaning →
  chunk building → validation → `data/processed/chunks/*.json`. Run via
  `src/run_chunking.py`.
- **Retrieval**: `src/retrieval/run_embeddings_retrieval.py` builds/loads one
  FAISS `IndexFlatIP` per regulator, applies symbolic hard filters, then
  cosine search with a similarity threshold (0.55) and result caching.
- **Generation**: `src/generation/citation_bound_answer_generation.py` calls
  `retrieve()` across all three regulators, builds a strict citation-bound
  prompt, calls `gpt-5-mini`, and caches the full response by query hash.
- **Orchestration**: `src/orchestrator/multi_agent_orchestrator.py` runs
  retrieval → citation (fail-fast on either) → summarization + risk assessment
  in parallel → confidence fusion → audit trail. Backed by `src/agents/*`.
- **UI**: `src/ui/step6_read_only_ui.py` is the current end-to-end UI (full
  agent chain) — redesigned 2026-08-16 with a formatted answer, citation
  cards, per-step progress (`st.status`), session query history, and error
  handling, instead of raw `st.json()` dumps per agent (raw JSON is still
  available per-run in a collapsed debug expander). Verified with
  Streamlit's `AppTest` framework driving a real form-fill + button-click +
  live query. `src/ui/ui_rag_full_advanced.py` is a retrieval-only debug UI
  with CSV/PDF export and term highlighting, kept because it has real
  functionality `step6_read_only_ui.py` doesn't.
- **Tests**: `src/tests/` covers agent-level contract validation
  (`test_step6_agents.py`), LangChain wrapper behavior, MLflow lineage
  logging, summarization behavior, and retrieval validation against
  `golden_queries.json`.

## Resolved in Phase 0

1. ~~Broken import in `src/chunking/cssf/cssf_parser.py`~~ — file moved to
   `archive/unused/cssf_parser.py`. It was dead code (not imported by
   `registry.py`) attempting an OOP parser pattern against a `BaseParser`
   class deleted in an earlier commit; not resurrected, since the active
   `section_parser.py`/`chunk_builder.py` functional approach already covers
   this.
2. ~~Stale `src.run_embeddings_retrieval` import path~~ — fixed in
   `src/ui/ui_rag_full_advanced.py` and `src/tests/test_retrieval_validation.py`
   (now `src.retrieval.run_embeddings_retrieval`). The other two files that
   had this import (`ui_rag.py`, `ui_rag_full.py`) were archived rather than
   fixed — superseded by `ui_rag_full_advanced.py`.
3. ~~Inconsistent import style in `src/test_run.py`~~ — fixed to
   `from src.orchestrator.multi_agent_orchestrator import ...`.
4. ~~Bare `chunking.*` imports in `src/chunking/registry.py` and
   `src/run_chunking.py`~~ — this was a second, previously undocumented
   instance of the same inconsistency (these two files assumed `src/` itself
   on the path, while everything else assumes the repo root). Fixed to
   `src.chunking.*`. Missing `__init__.py` files added to
   `src/chunking/`, `src/chunking/{cssf,dora,eba}/`, and `src/chains/` so the
   package is unambiguous.
5. ~~Multiple parallel Streamlit entry points~~ — reduced from five to two:
   `step6_read_only_ui.py` (primary, full multi-agent) and
   `ui_rag_full_advanced.py` (retrieval-only debug tool with export features
   worth keeping). `ui_rag.py`, `ui_rag_full.py`, `step5_streamlit_app.py`,
   `step5_conversational_ui.py` archived to `archive/ui_legacy/` — this is a
   deliberate deviation from the roadmap's "consolidate to one file"; they
   were strict functional subsets of the two kept, so nothing was lost.
6. ~~Empty placeholder files~~ — deleted: `agents/*.py` (top-level, 4 files),
   `app/api.py`, `app/cli.py`, `src/ui/streamlit_app.py`,
   `src/ui/test_orchestrator.py`, `src/ui/model_config.yaml`.
7. ~~`requirements.txt` incomplete~~ — `setup.py` and `requirements.txt` both
   removed, replaced by `pyproject.toml` as the single dependency/packaging
   source of truth. Also fixes packaging correctness: the old `setup.py`
   (`package_dir={"": "src"}`) would have installed subpackages as bare
   top-level names (`agents`, `orchestrator`, ...), which never matched the
   `from src.xxx import ...` convention used throughout the code — in
   practice nobody was likely running on the installed package, just on
   `PYTHONPATH` pointed at the repo root (see the old `notes.md`). The new
   `pyproject.toml` maps `src` itself as the package root, matching actual
   usage. Dependency versions are still unpinned pending a `pip freeze` from
   a working environment — nothing changed there.
8. ~~`data/` fully committed to git~~ — `data/faiss/`, `data/retrieval_cache/`,
   `data/step5_cache/`, `data/retrieval_logs/`, and `mlflow.db` are now
   gitignored and untracked (`git rm --cached`); files remain on disk
   locally. Rebuilt automatically on first run by the existing
   build-or-load logic in `run_embeddings_retrieval.py`. `data/raw/` and
   `data/processed/` (source PDFs, extracted text, chunk JSON) remain
   tracked — these are inputs/outputs of the traceable pipeline, not caches.
9. ~~`src/draft/`~~ — moved to `archive/chunking_v1/` along with its
   `data/processed/draft/` output, kept for reference.
10. ~~Duplicate, code-unreferenced `query_history.json`~~ (root and `data/`,
    different content, neither read/written by any code) — both moved to
    `archive/query_history_snapshots/` with distinguishing names.

## Resolved by running the app (not catchable by static reading alone)

1. **`src/agents/risk_assessment_agent.py` read the wrong retrieval key.**
   It checked `retrieval_result.get("documents", [])` to compute which
   retrieved sources went uncited, but the retrieval agent's real output key
   is `"retrieved_chunks"`. This silently made the "partial regulatory
   coverage" risk warning dead code — it could never fire. A test
   (`test_risk_agent_partial_coverage` in `test_step6_agents.py`) had been
   written *against* the bug (its fixture used a `"documents"` key with a
   comment `# <-- change from retrieved_chunks to documents`), so the test
   suite passed while the feature silently didn't work. Fixed the agent to
   read `"retrieved_chunks"` and corrected the fixture back to match the real
   contract.
2. **`src/ui/step6_read_only_ui.py` passed the wrong payload shape to two
   chains.** It called
   `summarization_chain.ainvoke(citation_result)` and
   `risk_assessment_chain.ainvoke({"citation_result": citation_result, ...})`
   using the *full* citation-chain envelope
   (`{"agent_result": {...}, "retrieved_chunks": ..., "timestamp": ...}`),
   but both `summarization_agent` and `risk_assessment_agent` expect the
   *unwrapped* `AgentResult` dict (i.e. `citation_result["agent_result"]`).
   This is exactly the bug a real user would have hit clicking through the
   UI: `summarization_chain.ainvoke(...)` would raise
   `TypeError: summarization_agent() got an unexpected keyword argument
   'agent_result'` immediately, and even if that were papered over, the risk
   agent would silently see an empty `citations` list every time. Fixed by
   unwrapping `citation_result["agent_result"]` before passing it to both
   downstream chains — this is the same shape `multi_agent_orchestrator.py`
   already used correctly, so the fix aligns the UI with the orchestrator's
   own convention rather than inventing a new one.
3. **MLflow logging silently fails on every run** (non-fatal, caught and
   printed, not raised): `src/chains/step6_agent_wrappers_mlflow.py`'s
   `log_agent_run` errors with *"When an mlflow-artifacts URI was supplied,
   the tracking URI must be a valid http or https URI..."* — something in
   the environment (or MLflow's own defaults) resolves an
   `mlflow-artifacts:` store URI that expects a running MLflow server, while
   the tracking URI is the local `sqlite:///mlflow.db`. The mismatch means
   no agent run is actually being logged to MLflow right now, despite no
   visible error to the user. This is a concrete, observed instance of
   exactly what `docs/10_improvement_roadmap.md` §3.2 ("Full MLflow
   application") flags as needing a real tracking server — left unfixed here
   since it's a bigger, deliberate piece of work, not a quick correction.

## Resolved by running a real query and reading the answer (2026-08-16)

Running the query *"What are the management body's responsibilities for ICT
risk governance under CSSF, DORA, and EBA?"* through the live UI and actually
reading the output (not just checking it rendered) surfaced two more bugs:

1. **`summarization_agent.py` garbled every summary containing a decimal
   citation.** `_clean_answer_text` split sentences on every `.` character,
   including the ones inside citation references like `3.2.1`. On this query
   the rendered Executive Summary was cut off mid-citation:
   *"...committees) [CSSF 3. 2."* Fixed by replacing the naive split with a
   regex (`_SENTENCE_BOUNDARY`) that only treats a period as a sentence
   boundary when it's preceded by a letter/`)`/`]` and followed by whitespace
   + an uppercase letter — decimal references (digit-to-digit) never match.
   The existing test suite didn't catch this because none of its fixtures
   used decimal-style citations in the answer text.
2. **The UI's sidebar "Query History" lagged one interaction behind** —
   it rendered before the submission-handling code that appends to
   `st.session_state.history`, so a just-completed query didn't appear until
   the *next* rerun. Fixed by moving the `with st.sidebar:` block to after
   the history append in script order (Streamlit sidebar placement doesn't
   depend on where in the script it's called, only execution order relative
   to state mutations does).
3. **The "Sources" list didn't distinguish retrieved-and-cited from
   retrieved-but-unused.** On the same query, 3 of 10 retrieved chunks
   (`DORA Article 16`, `15`, `11`) were fed to the LLM but never referenced
   in its generated answer — the UI showed all 10 as if they were equally
   "sources of the answer." Added a heuristic in the UI (`_is_cited_in_answer`,
   checks whether a chunk's reference literally appears inside a `[...]`
   bracket in the answer text) that now labels each source "✓ cited in
   answer" or "retrieved, not directly cited."

## Resolved by running a real query and reading the answer (2026-08-16, part 2)

While verifying the citation-semantics fix below, the user ran *"What are the
reporting obligations for major ICT-related incidents under DORA?"* through
the live UI and flagged the Executive Summary as inconsistent with the
Answer above it. Investigating (not just re-reading the diff) found the real
bug wasn't in the citation-semantics work at all:

- **`summarization_agent._clean_answer_text`'s dash-normalization regex
  silently merged a heading into the next paragraph.** Step 1 of the
  function (`re.sub(r"\s+[–—-]\s+", " ", answer)`) was meant to collapse an
  *inline* artifact like `". - Sentence"` onto one line, but `\s+` also
  matches newlines — so an LLM answer shaped like
  `"Summary of X\n\n- Who must report: ..."` had its blank-line-plus-bullet-dash
  collapsed into `"Summary of X Who must report: ..."` *before* the
  line-splitting loop ever ran, erasing the paragraph break the heading-drop
  logic depended on. The rendered Executive Summary read
  *"...under DORA Who must report: all financial entities..."* — heading and
  first sentence fused with no punctuation between them. Fixed by narrowing
  the regex to `[ \t]+[–—-][ \t]+` (horizontal whitespace only, no
  newlines), so it still normalizes same-line dash artifacts without
  spanning line breaks. Also hardened the heading-drop check itself (it only
  caught headings ending in `:`) to also drop a bare title line with no
  sentence-ending punctuation at all, as defense in depth.
  **Verified live**: re-ran the same query through `streamlit.testing.v1.AppTest`
  before and after — Executive Summary now starts
  *"Who must report: all financial entities must report..."* instead of the
  fused heading.
- The citation/retrieval side of that same query turned out **not** to be a
  bug: only 2 chunks were retrieved total (both DORA; nothing crossed the
  0.55 similarity threshold for CSSF/EBA), and the LLM cited both — so
  `citations == retrieved_chunks` there is the correct outcome of nothing
  going uncited, not a regression of the fix below.

## Phase 1 (Observability foundation) — complete, 2026-08-16

All five `docs/10` Phase 1 deliverables — structured logging, trace IDs,
centralized config, a Dockerized MLflow tracking server, params/metrics
logging — are done, together with the citation-semantics fix that motivated
this phase. Everything below was verified by actually running the app (live
queries through the UI, the orchestrator, and a real Docker container), not
by reading the diff.

### Citation semantics: "citations" now means "cited," not "retrieved"

`citation_agent.py` used to set `AgentResult["citations"]` to the *entire*
list of retrieved chunks handed to the LLM, not the subset it actually
referenced. That's the deeper bug behind the UI workaround described above
(`_is_cited_in_answer`): `risk_assessment_agent.py` compares `citations`
against `retrieval_result`'s chunks to detect "partial regulatory coverage,"
but since both sides were the same set by construction, that warning was
structurally unable to fire. Confirmed live before the fix: the UI showed 3
uncited DORA sources while Risk Assessment still said "No material
regulatory risks detected" — a visible contradiction.

Fixed:
- `citation_agent._extract_cited_chunks` filters `retrieved_chunks` down to
  the ones whose `source_reference` literally appears inside a `[...]`
  bracket in the answer text (the heuristic the UI used to duplicate as
  `_is_cited_in_answer`, now removed from the UI). The full retrieved set is
  still returned separately (`citation_agent`'s top-level `"retrieved_chunks"`
  key) for anything downstream — including the UI's Sources list — that
  needs the complete picture.
- `multi_agent_orchestrator.py`'s fail-fast changed from "citations list is
  non-empty" to "the citation agent produced an answer" — an empty citations
  list is now a legitimate outcome (e.g. "Information not available in
  retrieved sources" correctly cites nothing), not proof of failure.
- **Verified live**: re-running the management-body/DORA/CSSF/EBA query now
  correctly fires "Partial regulatory coverage" when sources go uncited, and
  a narrower DORA-only query that cites everything it retrieves correctly
  shows zero warnings (63% confidence, both sources cited) — both sides of
  the same logic now behave as designed.

### MLflow logging: fixed, then hardened with a real tracking server

Root cause: mlflow's SQLite-backed tracking store creates new experiments
with `artifact_location = "mlflow-artifacts:/<id>"` by default — a scheme
that only resolves through a running `mlflow server` proxy. Confirmed via
direct inspection of `mlflow.db`: the pre-existing `Default`/
`STEP6_RAG_Agents*` experiments all had this broken location, so every run
was silently failing, swallowed by a bare `except Exception: print(...)`.

Fixed in two layers:
1. **Local fallback** (works with zero setup): `step6_agent_wrappers_mlflow.py`
   gets-or-creates a dedicated `finance_compliance_rag_agents` experiment
   with an explicit local filesystem artifact root (`data/mlflow_artifacts/`,
   gitignored) whenever no real tracking server is configured. Pre-existing
   broken experiments are left untouched (their artifact_location can't be
   changed after creation anyway). Also fixed: the temp JSON file written per
   logged run was never deleted (`os.unlink` added).
2. **Real tracking server, Dockerized** (opt-in): `docker/Dockerfile.mlflow` +
   `docker/docker-compose.yml` bring up an actual `mlflow server`
   (sqlite-backed, single-node — the roadmap's Postgres/S3 "real store" is
   still future work, §3.2). `Settings.mlflow_tracking_uri` switches between
   the two with one env var; `_ensure_experiment`'s `_is_remote_tracking_uri`
   branch skips the local-artifact-root workaround when talking to a real
   server, since the server resolves `mlflow-artifacts:` itself.
- **Verified live, both paths**: local fallback — driving the UI end-to-end
  logs 4 `FINISHED` runs to `data/mlflow_artifacts/`. Docker path — started
  Docker Desktop, `docker compose up -d --build`, confirmed `/health`
  responded, then ran a real query with
  `MLFLOW_TRACKING_URI=http://localhost:5000` and confirmed all runs
  `FINISHED` with `experiment.artifact_location` resolving through the real
  server's own artifact proxy.

### Structured logging, trace IDs, and an MLflow run tree

New `src/observability/logging_config.py`: JSON log lines under the app's
own `finance_compliance_rag.*` logger namespace (doesn't hijack third-party
library logging), with a `trace_id` bound via `contextvars` — threaded
automatically through every log line and MLflow tag for one query without
changing any agent function signature. Generated once per query, in both
`MultiAgentOrchestrator.run()` and the live UI (at form submission — the UI
is the de facto "orchestrator" for the path actually exercised by users,
since `MultiAgentOrchestrator` isn't wired into either UI; see the known
issue below), included in `audit_trail["trace_id"]`, and shown in the UI
under each history entry ("Asked ... · trace `...`").

Also added `traced_query_run`: a context manager wrapping one query's full
agent sequence in a parent MLflow run tagged with `trace_id` and the query
text. Previously `mlflow.start_run(..., nested=True)` was a no-op — nothing
had an active parent run to nest under, since each UI stage ran its own
independent `asyncio.run()`. Now all 4 agent runs for one query genuinely
nest under one parent, browsable as a run tree.

**Verified live**: one `trace_id` correlated across all 4 MLflow runs and
every structured log line for a single query (confirmed via
`mlflow.search_runs(filter_string="tags.trace_id = ...")`).

### Centralized config

New `src/config.py` (`pydantic-settings`), replacing scattered constants
(`VECTOR_DIM`, `K_NEAREST`, `SIMILARITY_THRESHOLD`, cache paths, hardcoded
model names) across `run_embeddings_retrieval.py`,
`citation_bound_answer_generation.py`, and `step6_agent_wrappers_mlflow.py`.
Documented in the new `.env.example`. **Side benefit, verified live**:
`Settings` loads `.env` automatically, so `pytest`/scripts no longer need
`OPENAI_API_KEY` manually exported first — confirmed by running the full
suite in a shell with the variable unset.

### Params/metrics logging

`log_agent_run` now logs MLflow params (`embedding_model`, `llm_model`,
`similarity_threshold`, `k_nearest`, `citation_top_k`, sourced from
`Settings`) and metrics (`confidence`, `latency_seconds`, `warnings_count`)
on every run.

**Two real bugs found and fixed while implementing this**, both from
assuming a payload shape that only 2 of the 4 agents actually have —
`retrieval_agent`/`citation_agent` wrap their output as
`{"agent_result": {...}, ...}`, but `summarization_agent`/
`risk_assessment_agent` return the flat `AgentResult` dict directly:
- Metrics extraction read `payload.get("agent_result", {})`, silently
  falling back to `{}` for the two flat-shape agents and logging
  `confidence: 0.0`/`warnings_count: 0` regardless of the real values.
  Caught by inspecting a live run's logged metrics, not by assuming the code
  was correct. Fixed by falling back to `payload` itself.
- The same pattern in the run-naming code meant those two agents' MLflow
  runs were named after the Python function (`summarization_agent`) instead
  of the real short `agent_name` (`summarization`). Fixed the same way.
- **Verified live**: after both fixes, all 4 runs show correct per-agent
  confidence/warnings and consistent short run names (`retrieval`,
  `citation`, `summarization`, `risk_assessment`), nested under one parent.

## Phase 2 (Evaluation framework) — complete, 2026-08-16

All four `docs/10` §3.6 Phase 2 deliverables are done: expanded golden
queries, retrieval + generation metrics, a dedicated MLflow eval experiment,
and a CI regression gate. Verified by actually running the full 53-query
eval live against the real OpenAI API (not mocked), including hitting and
working around a real rate-limit/quota failure mid-run.

### Golden query set: 2 → 53 entries, each validated live

`src/tests/golden_queries.json` now has 46 "standard" cases (18 CSSF, 18
DORA, 10 EBA) plus 7 "no_answer" adversarial/out-of-domain cases, up from the
original 2. Every `expected_chunk_ids` entry was confirmed by actually
calling `retrieve()` against the live FAISS indexes and OpenAI embeddings —
not hand-guessed from reading chunk text. ~15% of the first-draft queries
didn't retrieve their intended chunk in the top 5 (either scoring below the
0.55 similarity threshold, or losing to a more semantically similar
neighboring chunk); those were iterated on empirically (checking real
cosine-similarity scores against candidate query phrasings) until all 53
passed. The 7 adversarial cases (unrelated topics like "sourdough bread
starter" and "offside rules in football", plus an out-of-scope DORA article
number and a GDPR question against un-indexed stores) were confirmed live to
retrieve zero chunks above threshold in every case.

`src/tests/test_retrieval_validation.py` gained a fourth parametrized test,
`test_no_answer_cases_retrieved_nothing`, asserting the 7 adversarial cases
retrieve `[]` — previously `test_expected_chunks_retrieved`'s loop over
`expected_chunk_ids` was silently a no-op for empty-list cases, asserting
nothing. 191/191 tests pass (up from 31).

### Retrieval + generation metrics

`src/evaluation/metrics.py`: `precision_at_k` and `reciprocal_rank`, both
returning `None` (not 0.0) for no-answer cases, since precision/MRR aren't
meaningful when the correct outcome is "retrieve nothing" — those cases are
scored separately as `abstention_retrieval_accuracy`.

`src/evaluation/llm_judge.py`: faithfulness + citation-accuracy scoring via
a direct OpenAI judge call (JSON-mode structured output), not RAGAS — RAGAS
was evaluated and rejected: it pulls in `datasets`/`langchain` integrations
this project doesn't otherwise need, and its generic-QA faithfulness metric
isn't tuned for this project's "must cite inline as `[REGULATION ref]`"
answer format. See the module docstring for the full reasoning.

**Verified live, full 53-query run**, all cases producing a real generated
answer and a real judge score (`data/eval_results/eval_20260816T172605Z.json`):
`mean_precision_at_5 = 0.481`, `mean_mrr = 0.834`,
`abstention_retrieval_accuracy = 1.0`, `mean_faithfulness = 0.950`,
`mean_citation_accuracy = 0.952`, `abstention_generation_accuracy = 1.0`,
**zero errors across all 53 queries**. This run is what `data/eval_baseline.json`
was built from.

**One real generation-quality issue surfaced by the judge, not a bug in the
eval code**: for `GQ_DORA_05` ("requirements for the ICT risk management
framework" — a well-covered, non-adversarial query with 11 strong-scoring
chunks retrieved), the cached LLM response was
`"Information not available in retrieved sources."` — an incorrect
abstention despite clearly sufficient context. Re-running the same
underlying call uncached produced a full, well-cited, faithful answer,
confirming this was `gpt-5-mini` response variance on that one call, not a
retrieval or prompt defect. The judge correctly scored this instance
`faithfulness=0.0, citation_accuracy=0.0` with an accurate explanation — this
is the eval framework doing exactly what it's for. Left as a known
generation-quality issue (see below) rather than "fixed," since there's
nothing wrong to fix in retrieval, prompt, or eval code; it's inherent LLM
sampling variance, and `generate_citation_bound_answer_cached`'s permanent
per-query-text caching means this specific bad answer will keep being served
for this exact query string until its cache entry is cleared or the query
text changes.

### One real bug found and fixed while implementing this: judge failures were silently eating the abstention signal

`_run_generation_eval` originally computed `abstention_generation_correct`
(whether a no-answer query's answer contains the required refusal phrase)
*inside* the same function as the LLM-judge call, both wrapped by one
try/except in the caller. When the judge call raised — which it does the
instant the OpenAI account runs out of credits, see below — the whole
function's return was lost, including the abstention check, even though
abstention only depends on the already-successfully-generated `answer` text
and has nothing to do with whether the judge call itself succeeds.
**Caught live**: a real `RateLimitError` (`credit_balance_exhausted`) partway
through a second full eval run silently zeroed `abstention_generation_accuracy`
from `1.0` to `0.0` even though every no-answer query's generation step had
already succeeded — the aggregate metric was lying about what actually
happened. Fixed by computing the abstention check immediately after
generation succeeds, independent of the judge call, which gets its own
narrower try/except (`judge_error: true` on the per-query result instead of
silently dropping the whole record). **Verified live**: re-ran with the
judge deliberately failing on every call (real exhausted-quota condition,
not simulated) — `abstention_generation_accuracy` correctly stayed `1.0`
(read from cached, already-correct answers) while `mean_faithfulness` /
`mean_citation_accuracy` correctly came back `None` (no judge scores
available), rather than either being silently wrong.

### MLflow: eval runs land in their own experiment, confirmed not to touch production

`src/evaluation/run_eval.py`'s `_ensure_eval_experiment` mirrors
`step6_agent_wrappers_mlflow.py`'s local-artifact-root fallback pattern
(duplicated rather than factored out into a shared helper, to avoid touching
the already-verified Phase 1 production logging path for this pass) but
targets `settings.mlflow_eval_experiment_name` (`finance_compliance_rag_eval`)
instead of `finance_compliance_rag_agents`. **Verified live**:
`mlflow.get_experiment_by_name(...)` for both names resolves to different
experiment IDs (3 vs. 4 in the local `mlflow.db`), and an eval run's logged
metrics (`mean_precision_at_5`, `mean_mrr`, per-run `git_commit` tag) are
queryable via `mlflow.search_runs` against the eval experiment only.

### CI gate

`.github/workflows/ci.yml`: `test` job runs the full pytest suite; `eval-gate`
job (depends on `test` passing) runs `python -m src.evaluation.run_eval
--no-mlflow --tolerance 0.05`, which exits non-zero if any current metric
falls more than `tolerance` below the committed `data/eval_baseline.json`.
Requires an `OPENAI_API_KEY` repository secret — the eval run makes real
embedding, generation, and judge calls; there's no mocked fallback, by design
(this project's whole verification approach is "run it for real," see
Phase 0/1 above). `--no-mlflow` in CI because the runner is ephemeral with no
persistent tracking store; local/dev runs of the same command log to MLflow
by default.

### Known limitation surfaced, not fixed: judge model billing is an external dependency of the CI gate

While establishing the baseline, the OpenAI account genuinely ran out of
credits mid-run (`insufficient_quota` / `credit_balance_exhausted` — verified
both chat completions and embeddings calls failing identically). This is an
account/billing fact, not a code issue, but it means: (a) the CI gate will
hard-fail (not skip) if the configured `OPENAI_API_KEY`'s account runs out of
credits, which is arguably correct fail-safe behavior but is worth knowing
before wiring the secret up, and (b) the committed baseline had to be taken
from the first clean 53/0-error run rather than a run made after the code
fix above, since credits were exhausted before a second clean run could be
made. Re-running `python -m src.evaluation.run_eval --update-baseline` once
credits are available would refresh it against the fixed code path, though
the numbers are expected to be materially the same (the fix only affects
what happens *when* a judge call fails, not the scores when it succeeds).

## Phase 3 (API layer) — complete, 2026-08-16

All `docs/10` §3.4 Phase 3 deliverables are done: a FastAPI service, typed
Pydantic request/response schemas, a streaming endpoint, and generated
TypeScript types. Verified by actually running the server (`uvicorn
app.api:app`) and the fully containerized stack (`docker compose up api`
plus a real `mlflow server`), and sending real HTTP requests that flow
through live retrieval + `gpt-5-mini` generation — not just the mocked
`TestClient` suite in `src/tests/test_api.py`.

**Update (Phase 5 partial, 2026-08-16):** GDPR is now chunked, embedded, and
indexed as its own standalone-queryable FAISS store — see "Phase 5 (Source
enrichment) — GDPR chunking/indexing complete" below for what shipped and
which roadmap questions were decided deliberately (shared base parser: a
narrow parameterization, not a class hierarchy; GDPR joining the live
orchestrator fan-out: deliberately deferred; NIS2: deliberately deferred).
243/243 tests pass (up from 199 — GDPR's own retrieval-validation suite,
kept separate from the existing 53-query `golden_queries.json`/`run_eval.py`
pipeline for reasons explained below).

**Update (Phase 5 extension, 2026-08-16):** at the user's request, four more
official documents were added to the *existing* CSSF/DORA/EBA authorities
(not new authorities — real regulatory PDFs sourced, extracted, and
chunked, human-reviewed before indexing per `docs/10` §2's ingestion
principle). Unlike GDPR, these merge into the live `cssf`/`dora`/`eba`
default query path, since that's what "more resources for the existing
authorities" means structurally. See "Phase 5 (Source enrichment) —
additional CSSF/DORA/EBA documents" below for two real parser bugs caught
and fixed before indexing, the golden-query/eval-baseline refresh this
required, and one deliberate content-scope call (an EBA guideline mostly
superseded by DORA, indexed anyway since real in-force content remained).
270/270 tests pass (up from 243).

**Update (post-Phase-4 UI polish, 2026-08-16):** two `web/` enhancements —
a sample-query dropdown, and a `FormattedText` component rendering the
Answer/Executive Summary sections as real lists with highlighted inline
citations instead of one flat, plain paragraph. See "Post-Phase-4 UI
polish" below for two real parsing-structure shapes discovered from actual
cached LLM output (not assumed) and a bug that surfaced along the way. No
Python changes; test count unchanged at 270/270.

**Update (Phase 5 complete, 2026-08-17):** NIS2 — the one item left queued
from Phase 5 — is done: chunked (DORA's parser reused, one new truncation
step for a false-positive-inducing Correlation Table annex), indexed, and
wired into the *live* default query path (unlike GDPR, deliberately, since
the roadmap's own reason for picking NIS2 requires it be searched alongside
DORA in the same query). See "Phase 5 (Source enrichment) — NIS2" below for
the four hardcoded call sites that needed updating together, a stale test
assertion this caught, and the eval-baseline refresh (all metrics flat or
improved). 295/295 tests pass. Phase 5 is now fully complete; Phase 6
(hardening) is next up per `docs/10`.

### Resolved the orchestrator/UI chain divergence by standardizing on one path

The known issue this doc used to document here — `MultiAgentOrchestrator`
calling the plain, unlogged chains in `src/orchestrator/langchain_wrappers.py`
while the live UI called the separately-defined, MLflow-wrapped chains in
`src/chains/step6_agent_wrappers_mlflow.py` — is fixed by switching
`multi_agent_orchestrator.py`'s import to the MLflow-wrapped chains directly.
`MultiAgentOrchestrator` is now the one orchestration path: `app/api.py` is
its only caller, and the live UI could switch to it too as a purely additive
follow-up (§3.4's "migration path" — not done in this pass, since it wasn't
required for the API layer itself, see the known issue below). A side effect
of the switch: every orchestrated run (currently, API-driven only) now gets
MLflow params/metrics logging and parent-run nesting under one `trace_id` for
free — `src/orchestrator/langchain_wrappers.py` itself is unchanged and still
covered by its own tests, just no longer used in production.

`src/orchestrator/langchain_wrappers.py`'s unused-`retrieval_result`
independent-re-retrieval issue in `citation_agent.py` (the other half of what
this section used to describe) is **not** touched by this pass — still open,
see below.

### FastAPI service (`app/api.py`)

Thin HTTP layer over `MultiAgentOrchestrator`, per §3.4:
- `POST /query` — full run, returns the aggregated result (including a new
  top-level `sources` field: the full retrieved-chunk set, not just what got
  cited — `MultiAgentOrchestrator.run()`'s return dict gained this field so
  an API consumer can render "retrieved, not directly cited" the way
  `step6_read_only_ui.py`'s `render_citations()` already does).
- `POST /query/stream` — Server-Sent Events, one event per agent stage
  (`retrieval`, `citation`, `summarization`, `risk_assessment`, `final`).
  Backed by a new `MultiAgentOrchestrator.run_events()` async generator that
  shares one internal `_run_stages()` generator with `run()`, so there are
  still not two independently-maintained orchestration code paths. **Verified
  live**: a real SSE request against the running server emitted all five
  events in order for a real DORA query.
- `GET /query/{trace_id}` — audit lookup, backed by a new
  `src/observability/audit_store.py` (one JSON file per trace_id under
  `data/audit_log/`, gitignored) — a lightweight stand-in for the roadmap's
  full durable-audit-log table (§3.3), scoped to what this endpoint needs.
  `trace_id` is validated against a strict `^[0-9a-f]{32}$` pattern before
  ever touching the filesystem (it's attacker-controlled input on this read
  path), returning 400 rather than passing an unsanitized value into a path
  join.
- `GET /health`.

Pydantic schemas (`app/schemas.py`) mirror `AgentResult`
(`src/orchestrator/agent_schema.py`) but model `citations`/`sources` as
chunk objects (`Citation`), not the bare-string `List[str]` the TypedDict
declares — that's what the citation/summarization/risk_assessment agents
actually populate in practice (see the schema module's docstring).

### Two real bugs found only by running the API live, not by the mocked test suite

1. **Out-of-domain queries returned 500, not 502.** The orchestrator's own
   `if not retrieval_result: raise RuntimeError(...)` fail-fast check is
   dead code for the real "nothing retrieved" case:
   `src/agents/retrieval_agent.py` raises `ValueError` directly instead of
   returning a falsy result, so that check never actually fires for it. The
   API's exception handling only caught `RuntimeError`, so a real live
   request with `"How do I make a sourdough bread starter?"` fell through to
   the generic 500 handler instead of the more accurate "pipeline couldn't
   service a well-formed request" 502. Fixed by catching `(RuntimeError,
   ValueError)` in both `/query` and `/query/stream`. **Verified live**:
   re-ran the same query against the running server post-fix — 502 with the
   real error message, and a regression test
   (`test_query_out_of_domain_returns_502_not_500`) added to
   `src/tests/test_api.py` so this can't regress silently again.
2. **The Dockerized MLflow server rejected every request from the API
   container** with `403 Invalid Host header - possible DNS rebinding attack
   detected`, discovered only when running `docker compose up` and actually
   querying the containerized API (the mocked test suite doesn't touch
   Docker at all). A recent `mlflow server` release added Host-header
   validation (`mlflow/server/security_utils.py`) that, by default, allows
   `localhost` and RFC1918 private-IP patterns but not Docker Compose's own
   service-name DNS (`http://mlflow:5000` — the value
   `MLFLOW_TRACKING_URI` is now set to for the containerized API, replacing
   the implicit "point at nothing, log to local sqlite inside the
   container" default). Fixed with `--allowed-hosts` on the `mlflow server`
   command in `docker/Dockerfile.mlflow`. Two follow-up bugs turned up
   fixing this one, also only by testing further: the match is exact-string
   unless the pattern contains `*`, so a bare `mlflow` didn't match the
   client's actual `Host: mlflow:5000` header (needed `mlflow:*`); and
   `--allowed-hosts` **replaces** mlflow's default allowlist rather than
   extending it, so an intermediate version of the flag that included
   `mlflow:*` but not `127.0.0.1` broke host-machine access to the mapped
   port (e.g. a browser hitting `http://localhost:5000` for the MLflow UI)
   that worked fine before this change. Final value reproduces mlflow's
   original localhost/127.0.0.1 defaults plus the `mlflow` service name.
   **Verified live, full loop**: rebuilt the image, brought up
   `mlflow`+`api` via `docker compose`, confirmed `GET /health` on both
   services from the host, ran a real query through the containerized API,
   and confirmed the run landed in the real MLflow server (nested run tree,
   correct `trace_id` tag) via the host-mapped port — not just that the
   container started.

### Containerization

`docker/Dockerfile.api` (multi-stage not needed at this size — a single
`python:3.12-slim` stage installing the project via `pyproject.toml`, with
`data/raw` and `data/processed` baked in so retrieval has chunks to index on
first run) plus an `api` service added to `docker/docker-compose.yml`,
pointed at the `mlflow` service by Docker DNS name and with named volumes for
`data/faiss`, the retrieval/step5 caches, and `data/audit_log` — the same
rebuildable-vs-source split `.gitignore` already documents for local dev.

### TypeScript client (`client/`)

`app/export_openapi.py` dumps `app.api.app`'s OpenAPI schema (no running
server required — FastAPI builds it from route/Pydantic declarations alone)
to `client/openapi.json`; `openapi-typescript` generates `client/api-types.ts`
from it. Both files are committed (generated, but reviewable in diffs and
consumable without a Node toolchain at clone time — same reasoning as
`data/eval_baseline.json`). Not a runtime HTTP client, just the typed
contract §3.4's future React/TS frontend (Phase 4) will import from instead
of hand-maintaining request/response types that could silently drift from
`app/schemas.py`.

## Phase 4 (TypeScript UI) — complete, 2026-08-16

`docs/10` §3.4's remaining deliverable — the React/TS frontend — is done: a
Vite + React + TypeScript app in `web/` that imports its request/response
types directly from the committed `client/api-types.ts` (a type-only import,
erased at build time, so `npm run build`'s `tsc -b` type-checks against
`client/api-types.ts` on disk without Vite's dev server ever needing to serve
a file outside its own root). No changes were needed to `app/schemas.py` or
`app/api.py` to support it, so `client/api-types.ts` didn't need
regenerating.

### Core screens

One screen, mirroring `step6_read_only_ui.py`'s spirit rather than its
five-panel layout 1:1:
- **Query form** (`QueryForm.tsx`) — a single textarea plus a static
  "Searches together: CSSF / DORA / EBA" chip row. `ui_rag_full_advanced.py`'s
  regulator multiselect was **not** ported as a real filter: `QueryRequest`
  (`app/schemas.py`) has no regulator field, and `retrieval_agent.py`
  hardcodes `VECTOR_STORES = ["cssf", "dora", "eba"]` with no filter
  parameter threaded through the orchestrator — adding one would be
  orchestration-layer work out of scope for a frontend phase. The chips are
  informational context only, matching what the API can actually do today.
- **Agent-by-agent results** (`ResultView.tsx` + `CitationList.tsx` +
  `ConfidenceBadge.tsx`) — Answer, Sources, Executive Summary, and Risk
  Assessment sections, each appearing as its SSE stage arrives rather than
  behind one spinner (see below). `ConfidenceBadge` uses the same thresholds
  as `step6_read_only_ui.py`'s `confidence_badge()` (green ≥0.75, orange
  ≥0.5, red below). `CitationList` reproduces `render_citations()`'s "cited
  vs. retrieved" distinction, but more directly than the Streamlit version:
  since Phase 1's citation-semantics fix, the API already returns "cited"
  (`answer.citations`, chunk objects) and "retrieved" (top-level `sources`,
  the full set) as two structurally distinct lists, so the frontend labels
  each source by comparing `chunk_id` membership instead of re-deriving the
  old text heuristic (`_is_cited_in_answer`) client-side.
- **History/audit view** (`HistorySidebar.tsx`) — a session-local list of
  completed queries (query text, trace_id, confidence), each clickable to
  redisplay, plus a manual "look up by trace ID" box backed directly by `GET
  /query/{trace_id}` — this is what makes it an *audit* view and not just a
  session cache: a trace_id from outside the current browser session (a
  teammate, a reload) resolves the same way. `App.tsx` normalizes both a live
  streaming run and a fetched `QueryResponse` into one `ResultViewModel`
  (`api/viewModel.ts`) so `ResultView` doesn't care which source it's
  rendering.

### Progressive rendering via `POST /query/stream`

`api/client.ts`'s `runQueryStream` hand-parses SSE frames
(`event: X\ndata: Y\n\n`) off a `fetch()` `ReadableStream` reader rather than
using the browser's native `EventSource`, which only supports GET — this
endpoint is POST. `hooks/useQueryRun.ts` folds each stage event into one
`RunState` as it arrives; `StageTimeline.tsx` renders a
retrieval/citation/summary/risk checklist that fills in live, and
`ResultView` renders each section's real content (not just a checkmark) as
soon as its stage's data is available, upgrading to the authoritative `final`
event's data once the run completes. Per-stage payload shapes
(`RetrievalStageData`, `CitationStageData`, etc., in `api/types.ts`) are
hand-typed from reading `retrieval_agent.py`/`citation_agent.py`/
`summarization_agent.py`/`risk_assessment_agent.py` directly, since only the
aggregated `final` event is shaped like the OpenAPI-generated `QueryResponse`
— the intermediate stages are the orchestrator's internal chain envelopes,
not part of the committed contract.

### Migration path: both Streamlit UIs kept, TS app becomes primary

Decided deliberately rather than assumed, per the roadmap's open question:
**both existing Streamlit UIs stay**, unconverted, still calling
`src.chains.step6_agent_wrappers_mlflow` directly rather than `app/api.py`.
Auditing what each one is actually for first:
- `step6_read_only_ui.py` (full multi-agent pipeline) is now superseded for
  end-user query answering — the new `web/` app covers the same ground
  through the API instead of the chain layer directly — but it's cheap to
  leave running as-is rather than deleting a working, tested UI.
- `ui_rag_full_advanced.py` is a **retrieval-only debug tool** with features
  the API doesn't expose at all: adjustable top-K/similarity-threshold
  sliders, raw per-chunk text with query-term highlighting, and CSV/PDF
  export. None of that is retrieval-agent or orchestrator output — it calls
  `retrieve()` directly — so porting it would mean adding new API surface
  (a raw retrieval endpoint, export endpoints) that nothing in `docs/10`'s
  Phase 4 scope calls for. It remains the tool for debugging retrieval
  quality independent of the full agent pipeline.

This matches the roadmap's explicit recommendation ("keep one Streamlit UI
alive as an internal/admin tool") — here that's effectively both, since they
serve different debugging purposes neither the API nor `web/` replaces, while
`web/` becomes the primary interface for actually asking the pipeline a
question.

### Verified live, full loop (not just `npm run build`)

Both servers run simultaneously — `uvicorn app.api:app` on `:8000`,
`npm run dev` (Vite) on `:5173` (the exact origin `src/config.py`'s
`api_cors_origins` already allowlisted, from Phase 3) — and driven with a
headless-Chromium Playwright script (no project skill for this existed yet;
`chromium-cli` wasn't available in this environment, so Python's
`playwright` package, already installed, drove it directly) through a real
query: *"What are the management body's responsibilities for ICT risk
governance under CSSF, DORA, and EBA?"* — the same query used to verify
Phase 1's citation-semantics fix.

Confirmed from the rendered page, not just that requests returned 200:
- All four stage-timeline items reached "done" and the Answer/Sources/
  Executive Summary/Risk Assessment sections rendered real, correctly
  formatted content (no garbled decimal citations — the Phase 1
  `_clean_answer_text` fix holds).
- Sources correctly split 7 cited / 3 uncited (`DORA Article 16`, `15`, `11`
  shown "retrieved, not cited") — the same three chunks Phase 1's
  citation-semantics fix section documents as the original bug repro,
  confirming the frontend's chunk_id-based comparison reproduces the
  original heuristic's correct behavior.
- Risk Assessment correctly fired "Partial regulatory coverage" (55%
  confidence, orange badge) precisely because of those three uncited
  sources.
- Confidence badges rendered with the correct color tier at both reported
  confidences (44% red, 55% orange).
- Clicking the new history-sidebar entry and separately pasting its trace_id
  into the lookup box both re-rendered the identical result via `GET
  /query/{trace_id}` — confirming the audit-lookup path, not just the
  streaming path.
- Zero browser console errors, zero page errors, zero failed network
  requests across the whole interaction.

## Phase 5 (Source enrichment) — GDPR chunking/indexing complete, 2026-08-16

`docs/10` §3.5's "finish what's started" item is done: GDPR
(`data/processed/extracted_text/gdpr_regulation.txt`) is now chunked,
embedded, and indexed as its own FAISS store, verified live end-to-end
(real chunking run, real OpenAI embedding calls, real `retrieve()` calls
against the built index). The other two §3.5 questions — a shared base
parser, and which new regulator (if any) to add next — were decided
deliberately rather than assumed; see below.

### GDPR chunking: DORA's Article-based logic reused, not reimplemented

GDPR (Regulation (EU) 2016/679) turned out to be structurally identical to
DORA: numbered `CHAPTER`s containing numbered `Article`s, one-per-line, same
EU Official Journal header/footer noise format. Confirmed before writing any
code by running DORA's actual regexes (`dora_parser.CHAPTER_PATTERN`,
`ARTICLE_PATTERN`) against the raw GDPR text: 99/99 articles and all 11
chapters matched correctly on the first try, in strict numeric order, with
no adjustment needed.

Given that, `src/chunking/dora/dora_parser.py`'s `build_article_chunks` was
parameterized to take a `document_meta` dict (`document_id`,
`document_title`, `authority`, `jurisdiction`, `binding_level`,
`chunk_id_prefix`) instead of hardcoding DORA's values inline — the
chapter/article-finding regex and chunk-assembly logic themselves are
already regulation-agnostic EU-legislative-act structure, not DORA-specific,
so parameterizing the one function that used to hardcode DORA's metadata
avoided copy-pasting ~80 lines of identical regex/assembly logic into a new
file. `dora_validate_chunks.py`'s `run_validation` was parameterized the
same way (`document_id_prefix`, `label`). Both keep their old
zero-argument call signatures working via defaults, so DORA's own chunking
run is unaffected — verified by re-running `python -m src.run_chunking --doc
dora` after the change and confirming identical output.

`src/chunking/gdpr/` (`gdpr_parser.py`, `gdpr_validate_chunks.py`) is now a
thin ~10-line config layer per file: GDPR's own `DOCUMENT_META` dict, and a
`build_article_chunks`/`run_validation` wrapper that calls DORA's
parameterized versions. `gdpr_cleaning.py` doesn't exist at all —
`dora_cleaning.remove_official_journal_noise` is imported directly into
`registry.py` as `gdpr_clean`, since that function was already
EU-Regulation-generic (nothing in it references DORA), so there was nothing
to wrap.

**Verified live**: `python -m src.run_chunking --doc gdpr` produced 99
chunks (`data/processed/chunks/gdpr_articles.json`), one per GDPR article,
chapter-tagged correctly (e.g. `gdpr_article_1`'s chapter is `"CHAPTER I –
General provisions"`, `gdpr_article_99`'s is `"CHAPTER XI – Final
provisions"`). The validator's `validate_article_boundary`/
`validate_article_order` checks pass with the `gdpr` prefix. One **pre-existing,
non-fatal false positive** surfaced by validating real GDPR text rather than
just DORA's: `dora_validate_chunks.OJ_PATTERNS` includes a bare `\bEN\b`
check apparently meant to catch leftover `"... EN Official Journal ..."`
header fragments, but GDPR Article 43 legitimately contains the string
`"EN-ISO/IEC 17065/2012"` (a real standard name), which also matches
`\bEN\b`. This prints `⚠ Official Journal noise found in gdpr_article_43`
even though the chunk text is correct (confirmed by reading it directly —
no actual OJ noise is present). Left as-is: it's a non-fatal print, was
already loosely specified before this pass (the same false positive could
happen to DORA text containing an "EN-" standard reference), and fixing the
validator's noise heuristics is out of scope for "reuse DORA's chunking
strategy" — noted here as a known cosmetic wrinkle, not fixed.

### Embedding/indexing: GDPR is a 4th standalone FAISS store, added at the retrieval layer only

`src/retrieval/run_embeddings_retrieval.py` now loads, embeds, and builds a
FAISS index for `gdpr_articles.json` alongside cssf/dora/eba, eagerly at
import time (same pattern as the existing three — this module builds all
configured stores whenever anything imports it, not lazily per query).
`retrieve(query_text=..., vector_store_key="gdpr", ...)` works standalone.

**Verified live**: importing the module actually built
`data/faiss/gdpr.index` / `gdpr_metadata.pkl` / `gdpr_vectors.npy` via real
OpenAI embedding calls (99 chunks). A dozen hand-written queries against
real GDPR concepts (consent, right to erasure, data portability, DPO
designation, breach notification, DPIAs, international transfers,
administrative fines, special-category data, data-minimisation principles)
each retrieved their intended article as the top (or only) result with
cosine similarity 0.58–0.77, comfortably clearing the 0.55 threshold; three
adversarial queries (football offside rules, sourdough starters, a
DORA-specific article number) correctly retrieved nothing from the GDPR
store.

### Deliberate decision: GDPR does **not** join the live orchestrator/API query path yet

`src/agents/retrieval_agent.py`'s `VECTOR_STORES = ["cssf", "dora", "eba"]`
and `src/generation/citation_bound_answer_generation.py`'s hardcoded
`regulators` dict were **not** touched. GDPR is indexed and queryable via
`retrieve(..., vector_store_key="gdpr")` directly, but every existing query
through the orchestrator, `app/api.py`, or `web/` still searches only
CSSF/DORA/EBA, exactly as before. Reasons, weighed explicitly rather than
defaulted into:

1. Adding a 4th source to the default fan-out changes behavior for every
   existing query, not just GDPR-relevant ones — a bigger, more visible
   change than "finish chunking text that was already extracted."
2. It would require a deliberate `--update-baseline` refresh of
   `data/eval_baseline.json`, reviewed on its own merits (precision/MRR
   necessarily shift with a 4th source competing for top-k slots) — not
   something that should happen as a side effect of a chunking task.
3. It would also require updating `web/`'s hardcoded
   `QueryForm.tsx` regulator chip list and re-verifying the frontend live.
4. It keeps this iteration's blast radius contained and independently
   reviewable, consistent with the roadmap's own "1–2 sources per iteration"
   caution (§6) — indexing and wiring-into-default-fan-out are two separable
   decisions, not one.

Confirmed this decision didn't silently change anything: re-running the
full 53-query `run_eval.py --retrieval-only` after adding GDPR reproduced
the existing baseline almost exactly (`mean_precision_at_5 = 0.4808` vs.
baseline `0.481`, `mean_mrr = 0.8341` vs. `0.834`,
`abstention_retrieval_accuracy = 1.0` unchanged) — GDPR's presence in
`vector_store`/`faiss_indexes` has no effect on CSSF/DORA/EBA queries, as
expected. `data/eval_baseline.json` was **not** updated in this pass.

### Eval coverage: a separate GDPR-only golden-query set, not `golden_queries.json`

`src/tests/golden_queries_gdpr.json` (12 standard + 2 adversarial cases,
`src/tests/test_gdpr_retrieval_validation.py`) mirrors Phase 2's process —
every `expected_chunk_ids` entry confirmed live via `retrieve()`, all 12
landing as the top hit on the first phrasing tried, no iteration needed.
This is deliberately a **separate file/test module** from the existing
`golden_queries.json`, not additional entries in it: `run_eval.py`'s
generation-eval step (`_run_generation_eval`) unconditionally runs every
`"standard"`-type case in `golden_queries.json` through
`generate_citation_bound_answer_cached`, which — per the decision above —
only ever searches CSSF/DORA/EBA. A GDPR case added there would always come
back as an incorrect abstention (nothing GDPR-relevant in those three
stores) and would have dragged `mean_faithfulness`/`mean_citation_accuracy`
down against the committed baseline for a source that was never wired into
generation — a false regression signal, not a real one. Keeping GDPR's
golden queries in their own file/module, exercised only via direct
`retrieve()` calls (243 tests total now pass, 199 + 44 new), gets the same
"validated live before committing" rigor without coupling to a pipeline
GDPR isn't part of yet. `golden_queries.json`'s existing `GQ_ADV_05`
("requirements for GDPR data subject access requests" run against the
*DORA* store, expecting nothing) still passes unchanged — it tests DORA's
own contamination resistance, unaffected by GDPR now having its own store.

### Deliberate decision: no shared `base_parser.py` class hierarchy yet

`docs/10` §3.5 flagged reviving `archive/unused/cssf_parser.py`'s intent (a
`BaseParser` class each authority module would subclass) once enough
sources shared a pattern. After GDPR, the picture is: DORA and GDPR share
an *identical* Article-based pattern (now expressed as one parameterized
function, see above); CSSF (section-based) and EBA (paragraph-based) each
have their own distinct pattern. That's not "many sources on one pattern"
yet — it's two sources on one pattern and two more on two different ones.
Building a full `BaseParser` class hierarchy now, with CSSF/EBA forced to
retrofit onto an abstraction shaped by only one example (DORA/GDPR), risks
guessing the wrong seams for structures that haven't been seen yet (NIS2,
MiCA, ECB/EIOPA/ESMA guidelines). The narrower move taken instead —
parameterizing DORA's existing functions with a metadata dict rather than
introducing a class hierarchy — captures 100% of the real duplication that
exists today (which was entirely in the hardcoded metadata, not the
parsing logic itself) without speculating about a shape for duplication
that doesn't exist yet. Worth revisiting for real once a second
Article-based EU regulation *beyond* DORA/GDPR shows up (NIS2 and MiCA are
both roadmap candidates for exactly that pattern) — at that point a third
data point would make the right abstraction boundary much clearer than it
is with two.

### Deliberate decision: NIS2 (or any other new regulator) deferred to the next iteration

Not attempted in this pass. GDPR chunking/indexing plus the base-parser
decision above were the scope for this iteration, per the roadmap's own
"1–2 sources per iteration" guidance (§6) — treating GDPR and a second new
regulator as one combined batch would violate that same guidance in the
same pass it was being followed for GDPR. NIS2 remains the roadmap's
suggested next candidate (heavy DORA overlap, real test of cross-regulation
risk detection in `risk_assessment_agent.py`) and, per the base-parser
decision above, would also be the second real data point for judging
whether the Article-based parsing pattern is worth a fuller shared
abstraction. Explicitly queued, not silently dropped.

## Phase 5 (Source enrichment) — additional CSSF/DORA/EBA documents, 2026-08-16

The user clarified that "more resources" meant more source documents for
the *existing* CSSF/DORA/EBA authorities (each currently backed by exactly
one document), not new authorities — a different axis from the GDPR/NIS2
work above, and one `docs/10`'s Phase 5 text hadn't originally scoped. Four
real, official documents were researched (via web search, not guessed
URLs), proposed to the user for explicit review before fetching — per
`docs/10` §2's "new ingestion stays human-controlled" principle — then
downloaded, extracted, chunked, and indexed after approval:

- **Circular CSSF 24/847** (ICT-related incident reporting framework, Jan
  2024) — merged into the `cssf` store.
- **Circular CSSF 22/806** (as amended by 25/883, outsourcing arrangements)
  — merged into the `cssf` store.
- **Commission Delegated Regulation (EU) 2024/1774** (DORA RTS — ICT risk
  management tools/methods/processes) — merged into the `dora` store.
- **EBA/GL/2019/04** (consolidated, as amended by EBA/GL/2025/02 — ICT and
  security risk management) — merged into the `eba` store.

Unlike GDPR, these are **not** new store keys — they extend the existing
`cssf`/`dora`/`eba` FAISS stores with more chunks, so they're
unavoidably part of every existing query through the live orchestrator/API
default fan-out (that's what "more resources for the existing authorities"
structurally means, as opposed to GDPR's separate, deliberately-excluded
store). `src/retrieval/run_embeddings_retrieval.py` now concatenates
multiple chunk files per authority (`load_chunk_files`) before building
each FAISS index; each source document keeps its own `chunk_id` namespace
(enforced by distinct prefixes per parser), so concatenation needed no
dedup step.

### A real content-currency finding, checked before indexing: EBA/GL/2019/04 is mostly (not entirely) superseded

Initial assessment (from search-result summaries alone) suggested the
consolidated EBA/GL/2019/04 was ~93% "[deleted]" post-DORA and not worth
indexing. Reading the actual extracted text before committing to that
assessment corrected it: paragraphs 1–9 (compliance/reporting obligations,
scope, addressees) are genuinely still in force and substantive — only the
guideline-proper sections 3.1–3.7 were deleted, plus section 3.8
(paragraphs 92–98, payment-service-user relationship management, still in
force because it derives from a PSD2 mandate DORA didn't touch). Net: 16
real, in-force chunks, not ~7. `eba_parser.py`'s existing `PARAGRAPH_PATTERN`
(`^(\d+)\.\s+...`) naturally skips the "[deleted]" sections — they have no
numbered paragraph, just a dotted sub-heading like "3.1. Proportionality" —
so no explicit filtering code was needed.

### Two real parser bugs, both caught by validation before indexing (not assumed away)

Checking each document's actual structure against the existing chunkers
before writing new code (rather than assuming DORA/GDPR's "it just worked"
experience would generalize) found that 3 of the 4 documents have
structures the existing CSSF/EBA parsers don't handle — Circular 22/806
uses "Section X.Y.Z Title" headers (dotted depth matching 20/750, but
prefixed with the word "Section" — 20/750's own regex matches zero
sections on it) and Circular 24/847 uses flat "N." paragraph numbering
under "Chapter N:" headers (a third, different scheme). Only the DORA RTS
turned out to be a clean drop-in reuse of `dora_parser.py`, the same way
GDPR was. Two small dedicated parsers
(`src/chunking/cssf/cssf_22_806_parser.py`,
`src/chunking/cssf/cssf_24_847_parser.py`) were written rather than forced
into existing regexes.

Writing `cssf_22_806_parser.py` surfaced two real bugs, both caught by its
own validator (`cssf_22_806_validate_chunks.py`, reusing
`cssf_validate_chunks.py`'s generic length/order checks) flagging results
that didn't look right — not assumed correct because the code ran without
raising:

1. **Table-of-contents collision.** The document's front matter lists
   every "Section X.Y.Z Title" and "Part N" heading a second time (the
   TOC) before the real body — both match the same regexes as the real
   headers, producing 16 duplicate `chunk_id`s (`cssf_22_806_4_1_1`, etc.)
   pointing at short, meaningless TOC-derived "chunks" instead of the real
   section content. Caught because the validator flagged 16 suspiciously
   short chunks and a duplicate-`chunk_id` check on the raw output
   confirmed exact collisions. Fixed by anchoring on the second occurrence
   of "Part I" (TOC mentions it once, the real heading once) and
   discarding every match before that position — chunks dropped from 38 to
   19, zero duplicates.
2. **A body sentence misread as a heading.** After fixing #1, the `part`
   metadata on every chunk read `"Part I – of this circular applies to the
   following In-Scope Entities when..."` — a garbled sentence fragment,
   not a real title. Root cause: the sentence *"Part I of this circular
   applies to the following In-Scope Entities when performing outsourcing
   other than ICT outsourcing"* (real body prose, referencing Part I by
   name) also starts a line with "Part I" and matched the same loose
   `PART_PATTERN`, and — since it appears later in the document than the
   real "Part I –" heading — became the "most recent" Part context for
   every following section. Fixed by requiring a dash before the title
   (matching the real headings' "Part I – Outsourcing arrangements" style,
   which the prose sentence doesn't have). **Verified live**: re-ran
   chunking, confirmed all 19 chunks' `part` field reads correctly ("Part I
   – Outsourcing arrangements" / "Part II – Requirements in the context of
   ICT").

`cssf_24_847_parser.py` needed one deliberate structural decision rather
than a bug fix: paragraph numbering restarts from "1." inside the
document's two Annexes (a deadlines table and an incident-notification
data-field table), which would otherwise collide with the substantive
body's own paragraphs 1–28. Paragraph-finding stops at the "Annexes"
marker, excluding the annex tables — they're form templates, not citable
regulatory obligations in the same sense as the numbered paragraphs above
them.

### Verified live: retrieval quality, existing-query regression check, and one golden-query fix

FAISS indexes for `cssf`/`dora`/`eba` were rebuilt (stale caches deleted,
real OpenAI embedding calls made) — chunk counts: cssf 25→72, dora 64→106,
eba 119→135. A dozen hand-written queries against the new content (ICT
incident classification deadlines, outsourcing due diligence, DORA RTS
asset management/encryption, EBA payment-service-user provisions) each
retrieved the correct chunk as the top result.

Re-running the full test suite against the enlarged stores surfaced exactly
one regression, not a code bug: `GQ_DORA_01`, a paraphrased query targeting
DORA's own broad "Article 1 – Subject matter" overview article, no longer
retrieved it in the top 5 — DORA RTS's 42 articles, being densely
ICT-security-themed, now out-score a generic paraphrase of an overview
article that itself just lists topic headings. Fixed by tightening the
golden query to near-verbatim phrasing of Article 1's actual opening
sentence (the same live-iteration process Phase 2 established: try
alternate phrasings, check real cosine-similarity scores, keep the one that
retrieves the intended chunk) — confirmed live, `dora_article_1` is again
the top hit (0.658). This is expected behavior, not something to "fix" at
the chunking/retrieval level: adding real, related content to a store
changes what a generic query's nearest neighbors are, and broad
overview-style articles are inherently harder to target precisely than
specific technical ones.

9 new golden queries were added directly to `golden_queries.json` (not a
separate file, unlike GDPR — these documents *are* in the live path):
`GQ_CSSF_19`–`22`, `GQ_DORA_19`–`21`, `GQ_EBA_11`–`12`, each confirmed live
against the rebuilt indexes, each landing as the top (often the only) result
above the 0.55 threshold. 270/270 tests pass (up from 243).

### Eval baseline refreshed, all metrics improved

Because these documents genuinely join the live query path (not standalone
like GDPR), the full 62-query eval (53 original + 9 new, retrieval +
generation + LLM judge, real API calls) was re-run before deciding on the
baseline: `mean_precision_at_5` 0.481→0.484, `mean_mrr` 0.834→0.864,
`mean_faithfulness` 0.950→0.990, `mean_citation_accuracy` 0.952→0.979,
both abstention-accuracy metrics unchanged at 1.0 — no regressions, every
metric flat or improved. `data/eval_baseline.json` was refreshed via
`--update-baseline` to the new 62-query numbers (necessary regardless of
direction, since the query set itself permanently grew).

## Post-Phase-4 UI polish: sample queries + formatted answer text, 2026-08-16

Two small, user-requested `web/` enhancements, done after Phase 4 was marked
complete — no Python/API changes, so `client/api-types.ts` didn't need
regenerating and the test count is unchanged at 270/270.

### Sample-query dropdown

`QueryForm.tsx` gained a `<select>` above the textarea listing 6 sample
queries — one cross-regulatory, plus at least one per regulator, including
two that exercise the CSSF/DORA content added earlier this session.
Selecting a sample fills the textarea (doesn't auto-submit) and the select
resets to its placeholder so another sample can be picked. Every sample was
confirmed live against the real FAISS indexes to retrieve strong, relevant
results before being hardcoded — not just written to sound plausible.
**Verified live**: driven with a real headless-browser session; selecting an
option populates `#query-input` correctly.

### `FormattedText`: the Answer/Executive Summary sections were rendering as one flat, plain paragraph

The Answer and Executive Summary sections were flagged as "almost plain."
Root cause: `ResultView.tsx` rendered `vm.answer.text`/`vm.summary.text` as
a single `<p>` with `white-space: pre-wrap` — real newlines survived
visually, but the LLM's actual structure (bulleted/numbered lists, nested
sub-bullets, inline `[REGULATION ref]` citations) never became real HTML,
so bullets rendered as literal `- ` dashes and citations as plain bracketed
text.

New `web/src/components/FormattedText.tsx` parses that output into real
`<ul>`/`<ol>` lists (with one level of nesting) and highlights citations as
styled pill badges, replacing the flat `<p>` in both sections. This isn't a
general markdown renderer — the LLM's output follows a narrow, predictable
shape, and a general renderer wouldn't have handled the harder case found
below anyway.

**Two real structural shapes had to be handled**, discovered by inspecting
actual cached LLM responses rather than assuming one consistent style:
1. Blank-line-separated `- ` bullets, with indented sub-bullets on their
   own lines (the citation agent's typical output).
2. `1) ... 2) ... 3) ...` numbered enumeration with **no newlines at all**
   — the entire list on one physical line, separated only by ". " between
   items (the summarization agent's typical output). A first version of the
   parser treated any line starting with a list marker as one full list
   item, which for this shape swallowed the *entire rest of the
   enumeration* into a single item's text — caught by testing against a
   real captured response, not assumed correct because the code ran
   without error. Fixed by requiring at least two consecutive marker lines
   before trusting a per-line split; a lone marker line is instead checked
   for further sequential inline markers (`splitInlineEnumeration`) before
   being treated as a single item.

**Verified two ways**: live in a real browser against a real generated
answer (13+ list items with citation badges rendering correctly across
both sections), and — after a live retrieval call turned out to be flaky
for unrelated reasons (a borderline 0.55–0.63 similarity score right at the
threshold, sensitive to real embedding-call variance between runs) —
directly against the three real distinct output shapes captured from
actual cached responses (nested dash bullets, no-newline numbered
enumeration, plain prose), via a one-off `npx tsx` script exercising the
parser's internal functions, all parsing correctly. That verification
script was not committed (it was a debugging aid, not part of the test
suite).

## Phase 5 (Source enrichment) — NIS2, the deferred item, now picked up

The one Phase 5 item explicitly queued in the previous pass — adding a new
regulator — is done: **NIS2** (Directive (EU) 2022/2555), the roadmap's own
first-recommended candidate (heavy DORA overlap, a real test of
cross-regulation risk detection). Unlike the CSSF/DORA/EBA document
additions, this is a genuinely new authority/store (like GDPR was) — but
unlike GDPR, the user explicitly decided this one **should** join the live
default fan-out, since the roadmap's whole stated reason for picking NIS2
(cross-regulation risk detection) only works if NIS2 and DORA are searched
together in the same query.

### Chunking: DORA's parser reused directly, with one new truncation step

NIS2 is structurally identical to DORA/GDPR (numbered `CHAPTER`s containing
numbered `Article`s, same older-era EU Official Journal noise format) —
confirmed by testing DORA's existing regexes against the raw text before
writing any code: 46/46 real articles and all 9 chapters matched. One real
issue surfaced by that same check, not assumed away: the document's trailing
**Correlation Table** (an annex mapping the NIS2-repealed 2016 NIS
Directive's articles to NIS2's own) contains rows starting with `"Article
N"` at line start, producing false-positive matches against the article
regex (48 matches instead of 46, with garbled trailing content). Fixed with
a NIS2-specific cleaning step (`src/chunking/nis2/nis2_cleaning.py`) that
truncates the text at `"ANNEX I"` — after which nothing is Article-numbered
regulatory text in the same sense as the 46 real Articles above it — before
handing off to DORA's reused parser. `binding_level` is recorded as `"EU
Directive"`, not `"EU Regulation"` like DORA/GDPR — NIS2 requires national
transposition and isn't directly applicable, a real legal distinction kept
accurate in the chunk metadata rather than glossed over.

**Verified live**: `python -m src.run_chunking --doc nis2` produced exactly
46 chunks, one per real Article, correctly chapter-tagged, validator clean
(no warnings). A FAISS index was built from real OpenAI embedding calls
(`data/faiss/nis2.*`); hand-written queries against real NIS2 concepts
(management-body cybersecurity governance, essential/important entity
classification, CSIRT technical requirements, information sharing,
certification schemes, jurisdiction, administrative fines) each retrieved
the correct article as the top result, and two adversarial queries
correctly retrieved nothing.

### Joining the live path: four call sites updated, not just the retrieval layer

Wiring in a new authority that's meant to be *live* (not standalone like
GDPR) touched more than the retrieval config:
`retrieval_agent.VECTOR_STORES`, `citation_bound_answer_generation.py`'s
`regulators` dict, and `run_eval.py`'s `_REGULATOR_TO_STORE_KEY` mapping
all needed the same fourth entry — three independent hardcoded lists that
have to stay in sync by hand (a real structural wrinkle worth flagging, not
just fixing: nothing enforces these three stay consistent with each other
or with `run_embeddings_retrieval.py`'s `vector_store` dict). Also updated
for consistency, since NIS2 is now genuinely part of what's searched: the
two Streamlit UIs' captions/regulator lists, and `web/`'s regulator chip
list and `App.tsx` header text (previously accurate as CSSF/DORA/EBA-only;
now would have been a stale claim if left alone).

One test (`test_retrieval_agent_returns_documents`) had `VECTOR_STORES`'s
length hardcoded as a literal `3` in its assertion — exactly the kind of
staleness the lack of single-source-of-truth above predicts. Fixed to
`len(ra.VECTOR_STORES)` so it can't go stale the same way again next time a
store is added, rather than just bumping the literal to `4`.

### Eval coverage and baseline

8 new golden queries (`GQ_NIS2_01`–`07` standard, `GQ_ADV_08` adversarial)
were added directly to `golden_queries.json` — NIS2 is in the live path, so
unlike GDPR's separate file, these belong in the same eval run as
everything else. Each was live-validated against the rebuilt index; two
first-draft phrasings needed iteration (a near-tie between two closely
related CSIRT articles, and a scope query that initially missed threshold
entirely) before landing cleanly, the same empirical process Phase 2
established. 295/295 tests pass (up from 270).

Because NIS2 joins every existing query's default fan-out, the full
70-query eval (retrieval + generation + LLM judge, real API calls) was
re-run before touching the baseline: `mean_precision_at_5` 0.484→0.520,
`mean_mrr` 0.864→0.880 — both meaningfully *improved*, not just flat —
`mean_faithfulness` 0.992→0.986 and `mean_citation_accuracy` 0.990→0.987
(both within normal LLM-judge run-to-run variance, not a real regression),
both abstention-accuracy metrics unchanged at 1.0. `data/eval_baseline.json`
was refreshed via `--update-baseline` to these 70-query numbers.

## Known issue: `citation_agent` still re-retrieves independently of the
## orchestrator's `retrieval_agent` step

Not touched by Phase 3 — this is the part of the old "known issue" section
above that Phase 3 did *not* resolve. `citation_agent.py`'s
`retrieval_result` parameter is unused — it calls STEP 5's
`generate_citation_bound_answer_cached`, which does its **own independent
retrieval** via `retrieve()` rather than reusing the `retrieval_result`
passed in from the orchestrator's `retrieval_agent` step. In practice both
calls hit the same deterministic FAISS index and should return the same
chunks, but nothing guarantees it structurally, and
`risk_assessment_agent`'s coverage check compares chunks from these two
independent retrieval calls. Worth resolving alongside a future
restructuring pass (`citation_agent` reusing the passed-in
`retrieval_result` instead of re-retrieving) rather than patching in
isolation.

## Known issues still open (not addressed in Phase 0)

- **Full package rename deferred.** The target structure in
  `docs/10_improvement_roadmap.md` proposes `src/finance_compliance_rag/...`
  as a properly namespaced package. That would mean rewriting every
  `from src.xxx import ...` across ~25 files to
  `from finance_compliance_rag.xxx import ...`. Deliberately **not** done in
  this pass: it's a large mechanical change with real breakage risk, and
  there was no Python interpreter available to verify the result. The
  current `src.*`-rooted convention is now at least internally consistent
  (see resolved item #4) and installable correctly via `pyproject.toml` — a
  reasonable stopping point until this can be done with tests run
  immediately after.
- **Dependency versions unpinned.** `pyproject.toml` lists real dependencies
  and has now been installed and run successfully in a clean venv (Python
  3.12), but versions are still unpinned (whatever pip resolved on
  2026-08-16). Worth freezing (`pip freeze`) once satisfied with the
  resolved set, so installs are reproducible rather than drifting.
- **`pytest-asyncio` was missing** (added during this pass, `asyncio_mode =
  "auto"` set in `pyproject.toml`) — without it, all 21 `@pytest.mark.asyncio`
  tests failed outright with pytest 9.x ("async def functions are not
  natively supported"). This dependency was never in the old
  `requirements.txt` either, so it's unclear the async test suite ever ran
  clean before this pass.
- ~~MLflow tracking/artifact URI mismatch~~ — fixed 2026-08-16, see "Phase 1
  (Observability foundation) — complete" above.
- **`archive/`** is new dead weight in the repo, even if clearly labeled. A
  future pass should decide whether to delete it outright (it's all still in
  git history/available via the commit before this cleanup) rather than keep
  it checked out.
- **Both Streamlit UIs still don't call `MultiAgentOrchestrator`/
  `app/api.py`** — `step6_read_only_ui.py` and `ui_rag_full_advanced.py` both
  still drive `src.chains.step6_agent_wrappers_mlflow`/`retrieve()` directly.
  As of Phase 4 this is a **deliberate, documented decision**, not an
  oversight: see "Phase 4 (TypeScript UI) — complete" → "Migration path"
  above. `web/` is now the primary interface for the full pipeline (via
  `app/api.py`); both Streamlit apps remain as admin/debug tools with
  functionality (raw retrieval tuning, CSV/PDF export) that has no API
  equivalent and wasn't in scope to add.
- **`audit_store.py`'s file-per-trace_id store has no retention/cleanup.**
  Fine at prototype scale (mirrors the existing `data/*_cache/` pattern,
  which has the same property), but would need addressing — or replacing
  with the roadmap's proper durable audit log (§3.3) — before any real
  production use.
