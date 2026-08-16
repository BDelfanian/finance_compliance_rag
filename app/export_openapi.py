"""
Dumps `app.api.app`'s OpenAPI schema to a JSON file — no running server
required, since FastAPI builds the schema from the route/Pydantic-model
declarations alone. `client/generate.sh` (or any `openapi-typescript` run)
consumes this file to produce a typed TS client, so the future frontend's
types are generated from the same schema the API actually serves at
`/openapi.json`, not hand-maintained in parallel.

Usage:
    python -m app.export_openapi [output_path]   # default: client/openapi.json
"""

import json
import sys
from pathlib import Path

from app.api import app

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "client" / "openapi.json"


def main() -> None:
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    print(f"Wrote OpenAPI schema to {output_path}")


if __name__ == "__main__":
    main()
