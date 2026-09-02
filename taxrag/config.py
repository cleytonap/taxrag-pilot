"""Runtime configuration kept deliberately small for the first vertical slice."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _object_storage_root() -> Path:
    """Return an absolute path for local object storage from the environment setting."""
    configured_path = Path(os.getenv("TAXRAG_OBJECT_STORAGE_ROOT", "var/object-storage"))
    return configured_path if configured_path.is_absolute() else PROJECT_ROOT / configured_path


@dataclass(frozen=True)
class Settings:
    database_url: str
    object_storage_root: Path


settings = Settings(
    database_url=os.getenv(
        "DATABASE_URL", "postgresql+psycopg://taxrag:taxrag@localhost:5432/taxrag"
    ),
    object_storage_root=_object_storage_root(),
)
