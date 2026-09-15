"""Tests for the deliberately small configuration boundary."""

from pathlib import Path

from taxrag import config


def test_local_dotenv_loader_uses_project_file_without_overriding_environment(
    monkeypatch,
) -> None:
    """Local secrets are convenient, while container and CI configuration remains authoritative."""
    observed: dict[str, object] = {}

    def fake_load_dotenv(path: Path, *, override: bool) -> None:
        observed["path"] = path
        observed["override"] = override

    monkeypatch.setattr(config, "load_dotenv", fake_load_dotenv)

    config._load_local_env()

    assert observed == {"path": config.PROJECT_ROOT / ".env", "override": False}
