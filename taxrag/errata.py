"""Curated source errata: official passages excluded from retrieval because they are wrong.

Official sources occasionally contradict each other (e.g. the annual Q&A repeating a previous
year's threshold). Citing such a passage would present a wrong rule as official support, so the
passage is excluded from indexing. The raw source and the extracted document stay untouched, and
every exclusion is recorded with evidence in a reviewable, versioned data file.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from taxrag.config import PROJECT_ROOT

ERRATA_PATH = PROJECT_ROOT / "data/source-errata.json"
REQUIRED_FIELDS = {"anchor_key", "reason", "conflicting_text", "controlling_text", "identified"}


def load_errata(path: Path = ERRATA_PATH) -> dict[str, dict[str, dict[str, str]]]:
    """Return {source_key: {anchor_key: entry}} after validating every entry's evidence fields."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    errata: dict[str, dict[str, dict[str, str]]] = {}
    for source_key, entries in raw.items():
        if source_key.startswith("_"):
            continue
        for entry in entries:
            missing = REQUIRED_FIELDS - set(entry)
            if missing:
                raise ValueError(f"Erratum for {source_key} is missing {sorted(missing)}")
            errata.setdefault(source_key, {})[entry["anchor_key"]] = entry
    return errata


def excluded_anchor_keys(source_key: str) -> frozenset[str]:
    """Return anchors of one source that must not be indexed or cited."""
    return frozenset(load_errata().get(source_key, {}))


def errata_fingerprint(path: Path = ERRATA_PATH) -> str:
    """Short content hash, stored with processing output so an errata change forces reprocessing."""
    content = path.read_bytes() if path.exists() else b""
    return hashlib.sha256(content).hexdigest()[:8]
