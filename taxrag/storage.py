"""Local development implementation of the raw-artifact storage boundary."""

from __future__ import annotations

import os
from pathlib import Path


class LocalObjectStorage:
    """Store raw artifacts on the local filesystem during development."""

    def __init__(self, root: Path) -> None:
        """Set the directory that all object keys must remain inside."""
        self.root = root.resolve()

    def put_bytes(self, key: str, content: bytes) -> None:
        """Atomically write bytes under a validated relative object-storage key."""
        destination = (self.root / key).resolve()
        # Resolving first exposes ``..`` traversal attempts before any file is written.
        if destination == self.root or self.root not in destination.parents:
            raise ValueError("Object storage key must remain within its configured root")

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(f"{destination.suffix}.tmp")
        temporary.write_bytes(content)
        # Replacing the completed temporary file avoids exposing a partially written artifact.
        os.replace(temporary, destination)
