# Finance Compliance RAG — frontend

React + TypeScript + Vite app (roadmap Phase 4) sitting on top of
`app/api.py`. Request/response types are imported directly from
`../client/api-types.ts` (a type-only import, erased at build time) rather
than hand-declared, so they can't silently drift from the backend's Pydantic
schemas.

## Run locally

Needs the API running first (from the repo root, with the project's venv
active):

```
uvicorn app.api:app --reload --port 8000
```

Then, from this directory:

```
npm install    # first time only
npm run dev
```

Opens on `http://localhost:5173` — the exact origin `src/config.py`'s
`api_cors_origins` already allows by default. Override the API's base URL
with a `.env` file (`cp .env.example .env`) if it's running somewhere else.

## Structure

- `src/api/client.ts` — thin `fetch` wrapper: `runQuery`, `runQueryStream`
  (hand-parsed SSE, since the native `EventSource` only supports GET and this
  endpoint is POST), `fetchQueryByTraceId`, `fetchHealth`.
- `src/api/types.ts` — re-exports the generated `QueryRequest`/
  `QueryResponse`/`Citation`/etc. types from `client/api-types.ts`, plus
  hand-typed shapes for the intermediate `POST /query/stream` stage events
  (retrieval/citation/summarization/risk_assessment), which aren't part of
  the OpenAPI contract — only the aggregated `final` event is.
- `src/api/viewModel.ts` — normalizes a live streaming run and a fetched
  `QueryResponse` (history click, trace-ID lookup) into one shape so
  `ResultView` doesn't need to know which source it's rendering from.
- `src/hooks/useQueryRun.ts` — drives `runQueryStream`, folding each stage
  event into one `RunState` as it arrives.
- `src/components/` — `QueryForm`, `StageTimeline`, `ResultView`,
  `CitationList`, `ConfidenceBadge`, `HistorySidebar`.

## After an `app/schemas.py` or `app/api.py` change

Regenerate the contract this app imports from — from the repo root:

```
python -m app.export_openapi
```

then from `client/`:

```
npm run generate
```

Don't hand-edit `client/api-types.ts`; don't hand-declare request/response
types here instead of importing them.

## Regulator filtering

The query form lists CSSF/DORA/EBA as informational context only, not a
working filter — `QueryRequest` has no regulator field, and
`retrieval_agent.py` always searches all three vector stores. Adding a real
filter would mean threading a parameter through the orchestrator and
retrieval agent, not just the frontend; out of scope for this phase.

## What this app deliberately doesn't replace

Both existing Streamlit UIs (`src/ui/step6_read_only_ui.py`,
`src/ui/ui_rag_full_advanced.py`) stay as admin/debug tools — see
`docs/09_current_state_and_known_issues.md`'s "Phase 4" section for why. In
particular, `ui_rag_full_advanced.py`'s adjustable top-K/similarity
threshold, raw retrieval debugging, and CSV/PDF export have no equivalent
here or in the API.
