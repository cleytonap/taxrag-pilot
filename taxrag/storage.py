"""Local development implementation of the raw-artifact storage boundary."""

from __future__ import annotations

import os
from pathlib import Path


class LocalObjectStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def put_bytes(self, key: str, content: bytes) -> None:
        destination = (self.root / key).resolve()
        if destination == self.root or self.root not in destination.parents:
            raise ValueError("Object storage key must remain within its configured root")

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(f"{destination.suffix}.tmp")
        temporary.write_bytes(content)
        os.replace(temporary, destination)
