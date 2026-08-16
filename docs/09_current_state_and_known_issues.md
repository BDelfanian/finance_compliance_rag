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

## Repository map (current)

```
src/
  agents/                STEP 6 agents: retrieval, citation, summarization, risk_assessment
  orchestrator/          MultiAgentOrchestrator, agent schema/validation, LangChain wrappers
  chains/                MLflow-wrapped agent chains (step6_agent_wrappers_mlflow.py)
  generation/            STEP 5 citation-bound answer generation (GPT-5 mini)
  retrieval/             STEP 4 embeddings + FAISS retrieval
  chunking/               Active chunking pipeline (cssf/dora/eba), registry-driven
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
  faiss/, retrieval_cache/, step5_cache/, retrieval_logs/  — gitignored, rebuilt on first run
docs/                      Design docs (00–08) + this file + decision log + roadmap
pyproject.toml              Single packaging/dependency source of truth (replaces setup.py + requirements.txt)
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

## Known issue surfaced but NOT fixed: citation coverage is structurally
## unable to distinguish "cited" from "retrieved"

Item 3 above is a UI-layer workaround for a deeper problem: `citation_agent.py`
sets `AgentResult["citations"]` to the full list of retrieved chunks handed to
the LLM, not the subset the LLM actually referenced in its answer. That same
`"citations"` field is what `risk_assessment_agent.py` compares against
`retrieval_result`'s chunks to detect "partial regulatory coverage" — but
since both sides are effectively the same set by construction, that warning
is structurally unable to fire (independent of the earlier `documents` vs
`retrieved_chunks` key-name bug already fixed in Phase 0). Concretely: on the
query above, the UI now visibly shows 3 uncited sources, but Risk Assessment
still says "No material regulatory risks detected" — a real, visible
contradiction. **Not fixed here** because the correct fix (deriving
`"citations"` from what the LLM actually referenced, e.g. by parsing its
answer text similarly to the new UI heuristic, or having the LLM return
structured citations) changes a field's meaning that the orchestrator also
uses for fail-fast gating (`multi_agent_orchestrator.py`'s
`if not agent_citation.get("citations"): raise RuntimeError(...)`), so it
needs its own deliberate pass rather than a quick patch alongside a UI
polish task.

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
- **MLflow tracking/artifact URI mismatch** — see item 3 above. Silent,
  non-fatal, but means no run is currently logged to MLflow.
- **`archive/`** is new dead weight in the repo, even if clearly labeled. A
  future pass should decide whether to delete it outright (it's all still in
  git history/available via the commit before this cleanup) rather than keep
  it checked out.
