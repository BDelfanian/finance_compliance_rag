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
    # Orchestration
    # -------------------------------
    model_version: str = "gpt-4.1"

    def resolved(self, path: Path) -> Path:
        """Repo-root-relative paths resolved to absolute, so behavior doesn't
        depend on the caller's current working directory."""
        return path if path.is_absolute() else (REPO_ROOT / path).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
