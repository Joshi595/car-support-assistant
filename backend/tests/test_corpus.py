"""The corpus, catalog and golden set agree with each other (no Docker or models needed)."""

import html
import json
import re
from datetime import date
from pathlib import Path

import pytest

from car_support.config import get_settings
from car_support.ingest.catalog import CatalogError, DocMeta, load_catalog

DATA = get_settings().data_dir
GOLDEN = [
    json.loads(line)
    for line in (Path(__file__).parent.parent / "eval" / "golden.jsonl").open(encoding="utf-8")
]
CATEGORIES = {
    "natural", "keyword", "followup", "market", "version", "cross_lingual", "german", "model", "multi_doc",
    "public", "out_of_scope", "tool_recall", "tool_charger", "handoff", "injection", "pii",
}  # fmt: skip
ROUTES = {"kb", "refuse", "recall", "charger", "handoff"}


def doc_text(doc: DocMeta) -> str:
    """Plain text of a source document (PDFs are checked against the HTML they were rendered from)."""
    path = DATA / doc.path
    if path.suffix == ".pdf":
        path = DATA / "scripts" / "manuals" / path.with_suffix(".html").name
    return html.unescape(re.sub(r"<[^>]+>", " ", path.read_text(encoding="utf-8")))


CATALOG = load_catalog(DATA)
BY_ID = {d.doc_id: d for d in sorted(CATALOG, key=lambda d: d.valid_from)}  # latest version wins per id


def test_catalog_covers_every_market_and_format() -> None:
    assert {(d.source_type, d.market) for d in CATALOG} >= {
        ("brand", "de"), ("brand", "uk"), ("brand", "us"), ("brand", "global"), ("public", "uk"),
    }  # fmt: skip
    assert {Path(d.path).suffix for d in CATALOG} >= {".md", ".html", ".pdf"}
    assert all(d.url for d in CATALOG if d.source_type == "public")


def test_versioned_document_shares_one_id() -> None:
    versions = sorted(d.valid_from for d in CATALOG if d.doc_id == "brand/uk/en/charging-tariffs")
    assert versions == [date(2026, 1, 1), date(2027, 1, 1)]


def test_catalog_rejects_entries_for_missing_files(tmp_path: Path) -> None:
    (tmp_path / "brand").mkdir()
    (tmp_path / "catalog.toml").write_text(
        '[defaults.brand]\nlicence="x"\nvalid_from=2026-01-01\n[docs."brand/x.md"]\n'
    )
    with pytest.raises(CatalogError, match="do not exist"):
        load_catalog(tmp_path)


@pytest.mark.parametrize("case", GOLDEN, ids=[c["id"] for c in GOLDEN])
def test_golden_case_is_grounded(case: dict[str, object]) -> None:
    assert case["category"] in CATEGORIES
    assert case["route"] in ROUTES
    assert case["market"] in {"de", "uk", "us"} and case["language"] in {"en", "de"}
    relevant: list[str] = case["relevant"]  # type: ignore[assignment]
    assert bool(relevant) == (case["route"] == "kb"), "only knowledge-base answers cite documents"

    texts = []
    for ref in relevant:
        doc_id, _, section = ref.partition("#")
        assert doc_id in BY_ID, f"unknown document {doc_id}"
        text = doc_text(BY_ID[doc_id])
        assert section.lower() in text.lower(), f"section '{section}' not found in {doc_id}"
        texts.append((BY_ID[doc_id].language, text.lower()))

    # Facts must appear in a relevant document written in the question's language.
    # (Cross-lingual cases are checked by the answer evaluation instead.)
    same_language = [t for lang, t in texts if lang == case["language"]]
    if same_language and case.get("as_of") is None:
        for fact in case["facts"]:  # type: ignore[attr-defined]
            assert any(alt.lower() in t for alt in fact.split("|") for t in same_language), f"fact '{fact}'"
