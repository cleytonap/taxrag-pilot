"""Runtime configuration kept deliberately small for the first vertical slice."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EMBEDDING_DIMENSIONS = 1536


def _load_local_env() -> None:
    """Load the gitignored project `.env` for local development without overriding deployment env."""
    load_dotenv(PROJECT_ROOT / ".env", override=False)


_load_local_env()


def _object_storage_root() -> Path:
    """Return an absolute path for local object storage from the environment setting."""
    configured_path = Path(os.getenv("TAXRAG_OBJECT_STORAGE_ROOT", "var/object-storage"))
    return configured_path if configured_path.is_absolute() else PROJECT_ROOT / configured_path


@dataclass(frozen=True)
class Settings:
    """Runtime settings for storage, database access, embeddings, and answer generation."""

    database_url: str
    object_storage_root: Path
    openai_api_key: str | None
    embedding_model: str
    embedding_dimensions: int
    answer_model: str


settings = Settings(
    database_url=os.getenv(
        "DATABASE_URL", "postgresql+psycopg://taxrag:taxrag@localhost:5432/taxrag"
    ),
    object_storage_root=_object_storage_root(),
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    embedding_model=os.getenv("TAXRAG_EMBEDDING_MODEL", "text-embedding-3-small"),
    # This initial pgvector column is deliberately fixed at the model's native size.
    # A different size requires an explicit schema/model migration, not an env toggle.
    embedding_dimensions=EMBEDDING_DIMENSIONS,
    answer_model=os.getenv("TAXRAG_ANSWER_MODEL", "gpt-4.1-mini"),
)
