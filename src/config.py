"""
Centralized configuration (roadmap §3.6 / Phase 1: "Full logging &
traceability" observability foundation).

Replaces module-level constants that were previously duplicated or
inconsistent across `src/retrieval/run_embeddings_retrieval.py`,
`src/generation/citation_bound_answer_generation.py`, and
`src/chains/step6_agent_wrappers_mlflow.py` (`VECTOR_DIM`,
`SIMILARITY_THRESHOLD`, `K_NEAREST`, cache paths, model names, MLflow
experiment/tracking config) with one environment-overridable source of
truth. See `.env.example` for the full list of overridable settings.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -------------------------------
    # OpenAI
    # -------------------------------
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    llm_model: str = "gpt-5-mini"

    # -------------------------------
    # Cost/usage tracking (roadmap §3.6 "Cost/usage tracking") — $ per 1K
    # tokens, keyed by model name and token kind. Placeholder rates: adjust
    # to match real billing if it differs from these. Overridable via env
    # as a JSON object, e.g. TOKEN_PRICING='{"gpt-5-mini": {"prompt": 0.0003, "completion": 0.0025}}'.
    # -------------------------------
    token_pricing: dict[str, dict[str, float]] = {
        "gpt-5-mini": {"prompt": 0.00025, "completion": 0.002},
        "text-embedding-3-small": {"embedding": 0.00002},
    }

    # -------------------------------
    # Retrieval (src/retrieval/run_embeddings_retrieval.py)
    # -------------------------------
    vector_dim: int = 1536
    embedding_batch_size: int = 50
    k_nearest: int = 5
    similarity_threshold: float = 0.55

    # -------------------------------
    # Generation (src/generation/citation_bound_answer_generation.py)
    # -------------------------------
    citation_top_k: int = 5
    # Versioned prompt template (roadmap §3.6 "Prompt versioning") — the
    # citation-bound prompt lives in prompts/<prompt_version>.md instead of
    # an inline f-string, so prompt changes are reviewable diffs with
    # history, and every generation logs which version produced it.
    prompts_dir: Path = Path("prompts")
    prompt_version: str = "citation_bound_v1"

    # -------------------------------
    # Paths — repo-root relative, resolved to absolute in the validators below
    # -------------------------------
    chunk_path: Path = Path("data/processed/chunks")
    faiss_path: Path = Path("data/faiss")
    retrieval_cache_path: Path = Path("data/retrieval_cache")
    step5_cache_path: Path = Path("data/step5_cache")
    mlflow_artifact_root: Path = Path("data/mlflow_artifacts")

    # -------------------------------
    # MLflow (src/chains/step6_agent_wrappers_mlflow.py)
    # -------------------------------
    # None = let mlflow resolve its own default (currently sqlite:///mlflow.db
    # in this environment). Set to e.g. http://localhost:5000 to point at the
    # Dockerized tracking server in docker/docker-compose.yml instead.
    mlflow_tracking_uri: Optional[str] = None
    mlflow_experiment_name: str = "finance_compliance_rag_agents"

    # -------------------------------
    # Evaluation (src/evaluation/) — Phase 2
    # -------------------------------
    # Separate experiment from mlflow_experiment_name above, so ad hoc eval
    # runs don't pollute the production-query run stream (roadmap §3.2).
    mlflow_eval_experiment_name: str = "finance_compliance_rag_eval"
    eval_results_path: Path = Path("data/eval_results")
    eval_baseline_path: Path = Path("data/eval_baseline.json")
    # Model used to score faithfulness/citation-accuracy; defaults to the
    # same model used for generation, override to use a stronger judge.
    eval_judge_model: str = "gpt-5-mini"

    # -------------------------------
    # Orchestration
    # -------------------------------
    model_version: str = "gpt-4.1"

    # -------------------------------
    # API (app/api.py) — Phase 3
    # -------------------------------
    # Completed orchestrator runs are persisted here (one JSON file per
    # trace_id) so GET /query/{trace_id} survives an API process restart —
    # a lightweight stand-in for the roadmap's durable audit log (§3.3),
    # not the full SQLite/Postgres table proposed there.
    audit_log_path: Path = Path("data/audit_log")
    # Human-in-the-loop review workflow (roadmap §3.6) — approve/reject/
    # annotate records per trace_id, doubling as the compliance sign-off
    # record docs/06's MRM section calls for, applied per-answer.
    review_log_path: Path = Path("data/review_log")
    # Origins allowed to call the API cross-origin, e.g. a local Vite dev
    # server for the future TypeScript UI (roadmap §3.4).
    api_cors_origins: list[str] = ["http://localhost:5173"]

    def resolved(self, path: Path) -> Path:
        """Repo-root-relative paths resolved to absolute, so behavior doesn't
        depend on the caller's current working directory."""
        return path if path.is_absolute() else (REPO_ROOT / path).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
