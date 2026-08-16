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

## Repository map (current)

```
src/
  agents/                STEP 6 agents: retrieval, citation, summarization, risk_assessment
  orchestrator/          MultiAgentOrchestrator, agent schema/validation, LangChain wrappers
  chains/                MLflow-wrapped agent chains (step6_agent_wrappers_mlflow.py)
  generation/            STEP 5 citation-bound answer generation (GPT-5 mini)
  retrieval/             STEP 4 embeddings + FAISS retrieval
  chunking/               Active chunking pipeline (cssf/dora/eba), registry-driven
  observability/           Structured logging + trace-ID context (logging_config.py) — Phase 1
  config.py                Centralized pydantic-settings Settings — Phase 1
  ui/                      Two Streamlit UIs (step6_read_only_ui.py, ui_rag_full_advanced.py)
  tests/                   pytest suite for retrieval, agents, orchestrator, MLflow lineage
archive/                   Superseded/dead code and data, kept for reference, not imported by anything active
  chunking_v1/             Earlier chunking iteration (formerly src/draft/) + its chunk output
  ui_legacy/                Four superseded Streamlit UIs (ui_rag.py, ui_rag_full.py, step5_*.py)
  unused/                  cssf_parser.py (dead OOP parser attempt, imported a since-deleted base class)
  query_history_snapshots/ Two orphaned, never-code-referenced query_history.json exports
data/
  raw/                     Source PDFs (CSSF, DORA, EBA, GDPR) — tracked in git
  processed/               Extracted text + chunks — tracked in git
  faiss/, retrieval_cache/, step5_cache/, retrieval_logs/, mlflow_artifacts/ — gitignored, rebuilt on first run
docker/                    Dockerfile.mlflow + docker-compose.yml — optional MLflow tracking server — Phase 1
docs/                      Design docs (00–08) + this file + decision log + roadmap
pyproject.toml              Single packaging/dependency source of truth (replaces setup.py + requirements.txt)
.env.example                Documents every src/config.py Settings field — Phase 1
```

`agents/` and `app/` (top-level, empty stub files) no longer exist — deleted.

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

## Known issue: `MultiAgentOrchestrator` and the live UI use different
## agent chains, so citation/retrieval divergence is possible

Not introduced or fixed in this pass, but surfaced while fixing the above:
`MultiAgentOrchestrator` (`src/orchestrator/multi_agent_orchestrator.py`)
calls the plain chains in `src/orchestrator/langchain_wrappers.py`, while the
live Streamlit UI (`step6_read_only_ui.py`) calls the separately-defined,
MLflow-wrapped chains in `src/chains/step6_agent_wrappers_mlflow.py`. Both
wrap the same underlying agent functions, so behavior is equivalent, but
`MultiAgentOrchestrator` itself is currently only exercised by
`src/tests/test_orchestrator.py` and `test_step6_agents.py`, not by either
live UI. Separately: `citation_agent.py`'s `retrieval_result` parameter is
unused — it calls STEP 5's `generate_citation_bound_answer_cached`, which
does its **own independent retrieval** via `retrieve()` rather than reusing
the `retrieval_result` passed in from the orchestrator's `retrieval_agent`
step. In practice both calls hit the same deterministic FAISS index and
should return the same chunks, but nothing guarantees it structurally, and
`risk_assessment_agent`'s coverage check compares chunks from these two
independent retrieval calls. Worth resolving alongside a future restructuring
pass (e.g. `MultiAgentOrchestrator` becoming the one true orchestration path
for both UIs, and `citation_agent` reusing the passed-in `retrieval_result`
instead of re-retrieving) rather than patching in isolation.

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
