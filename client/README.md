# Typed API contract

`api-types.ts` is generated from `app/api.py`'s FastAPI OpenAPI schema via
[`openapi-typescript`](https://openapi-ts.dev/) — the future TypeScript
frontend (roadmap Phase 4) imports its request/response types from here
instead of hand-maintaining them, so they can't silently drift from the
backend's Pydantic models.

This directory is the typed contract only, not a runtime HTTP client — pair
`api-types.ts` with `openapi-fetch` (or plain `fetch`) in the actual frontend
app when Phase 4 starts.

## Regenerating after an `app/schemas.py` or `app/api.py` change

From the repo root (with the project's venv active):

```
python -m app.export_openapi          # writes client/openapi.json
```

Then, from this directory:

```
npm install    # first time only
npm run generate   # writes client/api-types.ts
```

Commit both `openapi.json` and `api-types.ts` — they're generated but
checked in, the same way `data/eval_baseline.json` is: reviewable in diffs,
and consumable without regenerating on every clone.
