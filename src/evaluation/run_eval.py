"""
Evaluation runner (roadmap §3.6 / Phase 2) — runs the golden query set
end-to-end (retrieval metrics always; generation + LLM-judge unless
`--retrieval-only`), aggregates the results, logs them to their own MLflow
experiment, and — unless `--no-gate` — fails (non-zero exit) if any
aggregate metric regressed past tolerance against the committed baseline
in `data/eval_baseline.json`.

Usage:
    python -m src.evaluation.run_eval                      # full run, gated
    python -m src.evaluation.run_eval --limit 10            # cheaper subset
    python -m src.evaluation.run_eval --retrieval-only       # no LLM calls
    python -m src.evaluation.run_eval --update-baseline      # write new baseline, no gate
"""

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import mlflow

from src.config import get_settings
from src.evaluation.llm_judge import judge_answer
from src.evaluation.metrics import mean, precision_at_k, reciprocal_rank
from src.generation.citation_bound_answer_generation import generate_citation_bound_answer_cached
from src.observability.logging_config import get_logger
from src.retrieval.run_embeddings_retrieval import retrieve, vector_store

settings = get_settings()
logger = get_logger(__name__)

GOLDEN_QUERIES_PATH = Path(__file__).resolve().parents[1] / "tests" / "golden_queries.json"

_ABSTENTION_PHRASE = "information not available in retrieved sources"

# Regulator authority/jurisdiction filters, as used by
# citation_bound_answer_generation.generate_citation_bound_answer — needed
# here only to map a chunk's source_regulation back to a vector_store_key
# for text lookup (the generation response doesn't carry chunk text).
_REGULATOR_TO_STORE_KEY = {"CSSF": "cssf", "DORA": "dora", "EBA": "eba", "NIS2": "nis2"}


def _load_golden_queries(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    with open(GOLDEN_QUERIES_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)
    return cases[:limit] if limit else cases


def _lookup_chunk_text(chunk_id: str, store_key: str) -> str:
    ids = vector_store[store_key]["ids"]
    metadata = vector_store[store_key]["metadata"]
    try:
        return metadata[ids.index(chunk_id)].get("text", "")
    except ValueError:
        return ""


def _enrich_with_text(retrieved_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enriched = []
    for c in retrieved_chunks:
        store_key = _REGULATOR_TO_STORE_KEY.get(c.get("source_regulation", ""), "")
        text = _lookup_chunk_text(c["chunk_id"], store_key) if store_key else ""
        enriched.append({**c, "text": text})
    return enriched


def _run_retrieval_metrics(case: Dict[str, Any]) -> Dict[str, Any]:
    result = retrieve(
        query_text=case["query"],
        vector_store_key=case["vector_store_key"],
        authority=case["authority"],
        jurisdiction=case["jurisdiction"],
        top_k=5,
    )
    retrieved_ids = [c["chunk_id"] for c in result["retrieved_chunks"]]
    expected_ids = case["expected_chunk_ids"]

    out = {
        "id": case["id"],
        "type": case.get("type", "standard"),
        "query": case["query"],
        "retrieved_ids": retrieved_ids,
        "expected_ids": expected_ids,
        "precision_at_5": precision_at_k(retrieved_ids, expected_ids),
        "reciprocal_rank": reciprocal_rank(retrieved_ids, expected_ids),
    }
    if case.get("type") == "no_answer":
        out["abstention_retrieval_correct"] = len(retrieved_ids) == 0
    return out


def _run_generation_eval(case: Dict[str, Any], retrieval_out: Dict[str, Any]) -> Dict[str, Any]:
    generation = generate_citation_bound_answer_cached(query_text=case["query"], top_k=5)
    answer = generation.get("answer", "")
    retrieved_chunks = _enrich_with_text(generation.get("retrieved_chunks", []))

    # Computed independently of the judge call below: a judge failure (e.g.
    # a transient rate limit) must not silently drop the abstention signal,
    # since it's derived from `answer` alone, not from anything the judge
    # produces. (Previously this lived inside the same try/except as the
    # judge call, so one flaky judge call could wipe out an otherwise-valid
    # abstention_generation_correct result.)
    out: Dict[str, Any] = {"answer": answer}
    if case.get("type") == "no_answer":
        out["abstention_generation_correct"] = _ABSTENTION_PHRASE in answer.lower()

    try:
        out.update(judge_answer(case["query"], answer, retrieved_chunks))
    except Exception:
        logger.warning("LLM judge failed", extra={"case_id": case["id"]}, exc_info=True)
        out["judge_error"] = True

    return out


def _run_case(case: Dict[str, Any], retrieval_only: bool) -> Dict[str, Any]:
    result = _run_retrieval_metrics(case)
    if not retrieval_only:
        try:
            result.update(_run_generation_eval(case, result))
        except Exception as exc:
            logger.warning("generation eval failed", extra={"case_id": case["id"]}, exc_info=True)
            result["generation_error"] = str(exc)
    return result


def run_eval(
    limit: Optional[int] = None,
    retrieval_only: bool = False,
    max_workers: int = 8,
) -> Dict[str, Any]:
    cases = _load_golden_queries(limit=limit)

    per_query: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_run_case, case, retrieval_only): case for case in cases}
        for future in as_completed(futures):
            per_query.append(future.result())

    per_query.sort(key=lambda r: r["id"])

    standard = [r for r in per_query if r["type"] == "standard"]
    no_answer = [r for r in per_query if r["type"] == "no_answer"]

    aggregate = {
        "num_queries": len(per_query),
        "num_standard": len(standard),
        "num_no_answer": len(no_answer),
        "mean_precision_at_5": mean([r["precision_at_5"] for r in standard]),
        "mean_mrr": mean([r["reciprocal_rank"] for r in standard]),
        "abstention_retrieval_accuracy": mean([1.0 if r["abstention_retrieval_correct"] else 0.0 for r in no_answer])
        if no_answer
        else None,
    }

    if not retrieval_only:
        aggregate["mean_faithfulness"] = mean([r.get("faithfulness") for r in standard])
        aggregate["mean_citation_accuracy"] = mean([r.get("citation_accuracy") for r in standard])
        if no_answer:
            aggregate["abstention_generation_accuracy"] = mean(
                [1.0 if r.get("abstention_generation_correct") else 0.0 for r in no_answer]
            )

    return {"aggregate": aggregate, "per_query": per_query}


# -------------------------------
# MLflow logging (own experiment — roadmap §3.2: eval runs must not pollute
# the production-query "finance_compliance_rag_agents" experiment)
# -------------------------------
def _is_remote_tracking_uri(uri: str) -> bool:
    return uri.startswith("http://") or uri.startswith("https://")


def _ensure_eval_experiment() -> None:
    if settings.mlflow_tracking_uri:
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)

    experiment = mlflow.get_experiment_by_name(settings.mlflow_eval_experiment_name)
    if experiment is None:
        if _is_remote_tracking_uri(mlflow.get_tracking_uri()):
            mlflow.create_experiment(settings.mlflow_eval_experiment_name)
        else:
            artifact_root = settings.resolved(settings.mlflow_artifact_root)
            artifact_root.mkdir(parents=True, exist_ok=True)
            mlflow.create_experiment(
                settings.mlflow_eval_experiment_name,
                artifact_location=artifact_root.as_uri(),
            )
    mlflow.set_experiment(settings.mlflow_eval_experiment_name)


def _git_commit_sha() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=Path(__file__).resolve().parents[2])
            .decode()
            .strip()
        )
    except Exception:
        return "unknown"


def _log_to_mlflow(eval_result: Dict[str, Any], results_file: Path) -> None:
    _ensure_eval_experiment()
    with mlflow.start_run(run_name=f"eval_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"):
        mlflow.set_tag("git_commit", _git_commit_sha())
        mlflow.log_params(
            {
                "embedding_model": settings.embedding_model,
                "llm_model": settings.llm_model,
                "eval_judge_model": settings.eval_judge_model,
                "similarity_threshold": settings.similarity_threshold,
                "num_queries": eval_result["aggregate"]["num_queries"],
            }
        )
        metrics = {k: v for k, v in eval_result["aggregate"].items() if isinstance(v, (int, float))}
        mlflow.log_metrics(metrics)
        mlflow.log_artifact(str(results_file))


# -------------------------------
# Baseline comparison (the CI regression gate)
# -------------------------------
def _load_baseline() -> Optional[Dict[str, float]]:
    path = settings.resolved(settings.eval_baseline_path)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_baseline(aggregate: Dict[str, Any]) -> None:
    path = settings.resolved(settings.eval_baseline_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    numeric = {k: v for k, v in aggregate.items() if isinstance(v, (int, float))}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(numeric, f, indent=2)
    print(f"Wrote baseline to {path}")


def _check_regression(aggregate: Dict[str, Any], baseline: Dict[str, float], tolerance: float) -> List[str]:
    failures = []
    for key, baseline_value in baseline.items():
        if not isinstance(baseline_value, (int, float)):
            continue
        current_value = aggregate.get(key)
        if current_value is None:
            failures.append(f"{key}: missing from current run (baseline={baseline_value:.4f})")
            continue
        if current_value < baseline_value - tolerance:
            failures.append(
                f"{key}: regressed {current_value:.4f} < baseline {baseline_value:.4f} - tolerance {tolerance:.4f}"
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N golden queries (cost control).")
    parser.add_argument(
        "--retrieval-only", action="store_true", help="Skip generation + LLM-judge; retrieval metrics only."
    )
    parser.add_argument("--max-workers", type=int, default=8, help="Thread pool size for concurrent queries.")
    parser.add_argument("--tolerance", type=float, default=0.05, help="Allowed drop below baseline before failing.")
    parser.add_argument(
        "--no-gate", action="store_true", help="Run and log, but always exit 0 (skip regression check)."
    )
    parser.add_argument("--no-mlflow", action="store_true", help="Skip MLflow logging.")
    parser.add_argument(
        "--update-baseline", action="store_true", help="Write current results as the new baseline instead of gating."
    )
    args = parser.parse_args()

    start = time.perf_counter()
    eval_result = run_eval(limit=args.limit, retrieval_only=args.retrieval_only, max_workers=args.max_workers)
    elapsed = time.perf_counter() - start

    aggregate = eval_result["aggregate"]
    print(f"\n=== Eval run: {aggregate['num_queries']} queries in {elapsed:.1f}s ===")
    for key, value in aggregate.items():
        print(f"  {key}: {value if value is None else round(value, 4)}")

    results_path = settings.resolved(settings.eval_results_path)
    results_path.mkdir(parents=True, exist_ok=True)
    results_file = results_path / f"eval_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(eval_result, f, indent=2)
    print(f"\nFull results written to {results_file}")

    if not args.no_mlflow:
        try:
            _log_to_mlflow(eval_result, results_file)
        except Exception:
            logger.warning("MLflow eval logging skipped", exc_info=True)

    if args.update_baseline:
        _write_baseline(aggregate)
        return 0

    if args.no_gate:
        return 0

    baseline = _load_baseline()
    if baseline is None:
        print(
            f"\nNo baseline found at {settings.resolved(settings.eval_baseline_path)} — "
            "run with --update-baseline to create one. Skipping regression gate."
        )
        return 0

    failures = _check_regression(aggregate, baseline, args.tolerance)
    if failures:
        print("\nREGRESSION GATE FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("\nRegression gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
