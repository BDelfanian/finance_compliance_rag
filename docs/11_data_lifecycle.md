# Data Lifecycle Management

Phase 6 (`docs/10` §3.6) adopted DVC for `data/raw/` — this doc records what
is and isn't DVC-tracked, and why, since the split is deliberate rather than
"DVC-track everything under `data/`".

## The split

| Path | How it's tracked | Why |
|---|---|---|
| `data/raw/` (source PDFs, ~8MB, 9 files) | **DVC**, pushed to a remote | Binary PDFs — git already stores full blobs per change with no diffing benefit, and they only grow as more sources are added (`docs/10` §3.5). This is the actual fix for "unbounded binary growth in git." |
| `data/processed/` (extracted text, chunk JSON) | **Plain git** | `docs/10` §2's ingestion principle — new/changed chunks are human-reviewed via PR diff before anything is indexed. DVC-tracking this would replace readable JSON diffs with opaque content-hash pointers, undermining that review step. This is a deliberate deviation from "DVC everything," not an oversight. |
| `data/faiss/`, `data/retrieval_cache/`, `data/step5_cache/`, `data/mlflow_artifacts/`, `data/eval_results/`, `data/audit_log/`, `data/review_log/` | **gitignored**, rebuilt on first run | Unchanged since Phase 0 — these are pure derived/rebuildable caches, not source, and DVC-tracking rebuildable output nobody needs to reproduce byte-for-byte adds no value. |
| `data/eval_baseline.json` | **Plain git** | Deliberately-updated regression-gate baseline (Phase 2), not a cache. |

## Setup (new step, after Phase 6)

```bash
pip install -e ".[dev,data]"
dvc pull          # fetches data/raw/*.pdf from the configured remote
```

Without `dvc pull`, `data/raw/` will be empty after a fresh clone — chunking
and retrieval only ever read `data/processed/`, so this doesn't block
running the app, but you won't have the original source PDFs on disk (e.g.
to re-extract text or verify provenance against `docs/01_data_inventory.md`).

## Remote storage

The default remote (`.dvc/config`) is a **local directory**
(`../finance_compliance_rag_dvc_storage/`, a sibling of the repo, not
committed) — there are no cloud credentials in this environment, matching
the same "local fallback, real backend optional" pattern already used for
MLflow (`docs/09`'s Phase 1 section). For a real deployment, point it at
durable storage instead:

```bash
dvc remote modify localstorage url s3://your-bucket/finance-compliance-rag-dvc
# or azure://, gs://, etc. — see https://dvc.org/doc/command-reference/remote/modify
```

## Pipeline reproducibility (`dvc.yaml`)

Two stages, picking up from the human-reviewed output
`docs/03_text_extraction.md` describes (raw PDF → extracted text is a
**manual, human-reviewed** pdfplumber pass with no repeatable CLI in this
repo — deliberately not automated, per the same ingestion-review principle
above):

- `chunk` — runs `src/run_chunking.py --doc <x>` for every entry in
  `src/chunking/registry.py`'s `DOCUMENT_REGISTRY`, from
  `data/processed/extracted_text/` to `data/processed/chunks/`. Declared
  with `cache: false` so the output stays plain-git-diffable (see above);
  DVC still tracks it as a dependency for staleness detection.
- `index` — runs `src/retrieval/run_embeddings_retrieval.py`'s
  build-or-load logic, from `data/processed/chunks/` to `data/faiss/`.

```bash
dvc status    # "is my derived data stale relative to its inputs?"
dvc repro     # re-run only the stages whose deps actually changed
```

Verified live (2026-08-18): `dvc repro` ran both stages clean end-to-end,
producing byte-identical chunk output to what was already committed
(confirmed via `git diff --stat`), and a second `dvc repro` correctly
no-opped ("didn't change, skipping") on both stages. `dvc push` confirmed
all 9 raw PDFs land in the configured remote.

**One real, pre-existing bug found and fixed while wiring this up** (not a
DVC bug, surfaced by running the `chunk` stage in a non-interactive shell):
`src/run_chunking.py` printed unicode symbols (`✅`, and `⚠` in the chunk
validators it calls) without ever setting an explicit output encoding —
fine in an interactive terminal with a UTF-8 codepage active, but a
`UnicodeEncodeError` crash under the plain `cp1252` encoding a
non-interactive Windows process gets by default (exactly what `dvc repro`
spawns). Fixed by reconfiguring `sys.stdout`/`sys.stderr` to UTF-8 at the
top of `run_chunking.py`'s entrypoint, rather than editing each print site.
