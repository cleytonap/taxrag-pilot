"""Source errata: known-wrong official passages are documented, verified and never indexed."""

import json
import re
from pathlib import Path

from taxrag import processing
from taxrag.errata import errata_fingerprint, excluded_anchor_keys, load_errata
from taxrag.extraction import (
    extract_dou_in_rfb_2312_html,
    extract_receita_guidance_html,
    extract_receita_questions_answers_pdf,
)

SNAPSHOTS = Path("data/source-snapshots")
EXTRACTORS = {
    "irpf-2026-in-rfb-2312": (extract_dou_in_rfb_2312_html, "original.html"),
    "irpf-2026-quem-deve-declarar": (extract_receita_guidance_html, "original.html"),
    "irpf-2026-perguntas-respostas": (extract_receita_questions_answers_pdf, "original.pdf"),
}


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def test_every_erratum_quotes_text_that_exists_in_the_excluded_passage() -> None:
    """An erratum must point at a real section and quote its wrong text verbatim."""
    errata = load_errata()
    assert errata, "the errata file should list the known stale P&R passages"
    for source_key, entries in errata.items():
        extractor, filename = EXTRACTORS[source_key]
        sections = {
            section.anchor_key: section
            for section in extractor(next((SNAPSHOTS / source_key).rglob(filename)).read_bytes()).sections
        }
        for anchor_key, entry in entries.items():
            assert anchor_key in sections, f"{anchor_key} no longer exists; review the erratum"
            assert _flat(entry["conflicting_text"]) in _flat(sections[anchor_key].text)
            assert entry["controlling_text"].strip()


def test_eval_fixtures_never_use_an_excluded_passage_as_evidence() -> None:
    excluded = {key for source in load_errata() for key in excluded_anchor_keys(source)}
    used = set()
    for path in Path("docs/evals").glob("*.jsonl"):
        for line in path.read_text().splitlines():
            if line.strip():
                record = json.loads(line)
                used |= set(record.get("acceptable_anchor_keys", []))
                used |= set(record.get("context_anchor_keys", []))

    assert used & excluded == set()


def test_processing_version_changes_when_errata_change() -> None:
    """Editing the errata file must force reprocessing, or excluded chunks would linger."""
    assert processing.processing_version().endswith(f"+errata.{errata_fingerprint()}")
