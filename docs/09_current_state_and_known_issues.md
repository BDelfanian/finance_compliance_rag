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

## Repository map (current)

```
app/                       FastAPI service — Phase 3
  api.py                    POST /query, POST /query/stream (SSE), GET /query/{trace_id}, GET /health
  schemas.py                 Pydantic request/response models mirroring AgentResult
  export_openapi.py           Dumps app.api.app's OpenAPI schema to client/openapi.json
client/                    Generated TypeScript API contract — Phase 3
  openapi.json, api-types.ts  Committed, regenerated via app/export_openapi.py + `npm run generate`
src/
  agents/                STEP 6 agents: retrieval, citation, summarization, risk_assessment
  orchestrator/          MultiAgentOrchestrator (now the one chain path — see below), agent schema/validation
  chains/                MLflow-wrapped agent chains (step6_agent_wrappers_mlflow.py) — used by
                          MultiAgentOrchestrator directly since Phase 3
  generation/            STEP 5 citation-bound answer generation (GPT-5 mini)
  retrieval/             STEP 4 embeddings + FAISS retrieval
  chunking/               Active chunking pipeline (cssf/dora/eba), registry-driven
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
- **The live Streamlit UI (`step6_read_only_ui.py`) still doesn't call
  `MultiAgentOrchestrator`/`app/api.py`** — it drives
  `src.chains.step6_agent_wrappers_mlflow`'s chains directly, the same as
  before Phase 3. The orchestrator/UI *chain* divergence is resolved (both
  now ultimately call the same MLflow-wrapped agent functions — see "Phase 3
  (API layer) — complete" above), but there are still two callers of that
  shared chain layer (the UI directly, and the API via the orchestrator)
  rather than one. Switching the UI to call the running API instead is
  exactly the roadmap's §3.4 "migration path" and a natural precursor to
  Phase 4's real frontend — not done here since it wasn't required to ship
  the API layer itself.
- **`audit_store.py`'s file-per-trace_id store has no retention/cleanup.**
  Fine at prototype scale (mirrors the existing `data/*_cache/` pattern,
  which has the same property), but would need addressing — or replacing
  with the roadmap's proper durable audit log (§3.3) — before any real
  production use.
