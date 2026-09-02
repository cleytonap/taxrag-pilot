from pathlib import Path

import pytest

from taxrag.storage import LocalObjectStorage


def test_put_bytes_writes_within_storage_root(tmp_path: Path) -> None:
    storage = LocalObjectStorage(tmp_path)

    storage.put_bytes("raw/example/original.html", b"official source")

    assert (tmp_path / "raw/example/original.html").read_bytes() == b"official source"


def test_put_bytes_rejects_path_traversal(tmp_path: Path) -> None:
    storage = LocalObjectStorage(tmp_path)

    with pytest.raises(ValueError, match="within its configured root"):
        storage.put_bytes("../outside.html", b"not allowed")


def test_get_bytes_reads_a_stored_object(tmp_path: Path) -> None:
    storage = LocalObjectStorage(tmp_path)
    storage.put_bytes("raw/example/original.html", b"official source")

    assert storage.get_bytes("raw/example/original.html") == b"official source"
