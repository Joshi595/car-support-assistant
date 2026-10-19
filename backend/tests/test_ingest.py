import hashlib
import shutil
from collections.abc import Sequence
from pathlib import Path

import pytest
from sqlalchemy import select, text

from car_support.config import get_settings
from car_support.db.models import EMBED_DIM, ChunkRecord, DocumentRecord
from car_support.db.session import get_session
from car_support.ingest.chunk import chunk_markdown, title_of
from car_support.ingest.convert import pdf_text_to_markdown, to_markdown
from car_support.ingest.index import index_corpus

DATA = get_settings().data_dir


# ── Conversion and chunking (unit) ─────────────────────────────────────────────


def test_chunks_carry_heading_path_and_skip_empty_sections() -> None:
    md = "# Warranty\n\nIntro text.\n\n## Battery\n\n- 8 years\n\n## Keys\n\n### Lost key?\n\nCall us."
    chunks = chunk_markdown(md, title_of(md, "x"))
    assert [c.heading_path for c in chunks] == [
        ("Warranty",),
        ("Warranty", "Battery"),
        ("Warranty", "Keys", "Lost key?"),
    ]
    assert chunks[1].text == "Warranty › Battery\n- 8 years"


def test_long_sections_are_split_and_keep_their_prefix() -> None:
    body = " ".join(f"Sentence number {i} about battery care." for i in range(120))
    chunks = chunk_markdown(f"## Battery care\n\n{body}", "Manual", max_chars=500, overlap=50)
    assert len(chunks) > 1
    assert all(c.text.startswith("Manual › Battery care\n") and len(c.body) <= 500 for c in chunks)


def test_pdf_text_recovers_title_numbered_headings_and_paragraphs() -> None:
    raw = (
        "My Manual\n\n1. Driving modes\n\nThe car has\nfour modes.\n\n"
        "\f7. 12V battery\n\nIt is small.\n\n3.1 AC charging\n\nPlug in."
    )
    assert pdf_text_to_markdown(raw) == (
        "# My Manual\n\n## 1. Driving modes\n\nThe car has four modes.\n\n"
        "## 7. 12V battery\n\nIt is small.\n\n### 3.1 AC charging\n\nPlug in."
    )


def test_html_conversion_keeps_main_content_and_drops_link_urls() -> None:
    md = to_markdown(DATA / "brand/global/en/model-ion-4.html")
    assert md.startswith("# Northwind Ion 4: Model Guide")  # nav bar before <main> is gone
    assert "fictional company" not in md  # footer outside <main> is gone
    assert "](" not in md


@pytest.mark.parametrize(
    "path", ["brand/global/en/ion-4-owners-manual.pdf", "brand/global/en/vela-owners-manual.pdf"]
)
def test_owner_manual_pdfs_keep_every_numbered_section(path: str) -> None:
    md = to_markdown(DATA / path)
    sections = [c.heading_path[1] for c in chunk_markdown(md, title_of(md, path)) if len(c.heading_path) > 1]
    numbers = sorted({int(s.split(".")[0]) for s in sections})
    assert numbers == list(
        range(1, numbers[-1] + 1)
    )  # no section lost (e.g. one starting after a page break)


# ── Incremental indexing (integration, real Postgres) ──────────────────────────


class FakeEmbedder:
    """Deterministic vectors and a record of how many texts were embedded."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls += len(texts)
        return [[b / 255 for b in hashlib.sha256(t.encode()).digest()] * (EMBED_DIM // 32) for t in texts]


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    for rel in [
        "catalog.toml",
        "brand/uk/en/warranty.md",
        "brand/de/de/warranty.md",
        "public/uk/en/getting-an-mot.html",
    ]:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(DATA / rel, tmp_path / rel)
    catalog = (tmp_path / "catalog.toml").read_text(encoding="utf-8")
    keep = '[docs."public/uk/en/getting-an-mot.html"]\nurl = "https://www.gov.uk/getting-an-mot"\n'
    (tmp_path / "catalog.toml").write_text(catalog.split("# ── Brand: versioned")[0] + keep, encoding="utf-8")
    return tmp_path


@pytest.mark.integration
def test_indexing_is_incremental(database_url: str, data_dir: Path) -> None:
    embed = FakeEmbedder()
    with get_session() as session:
        first = index_corpus(session, data_dir, embed, full=True)
        assert first.documents == 3 and first.chunks == first.chunks_added == embed.calls > 0
        assert first.kb_version is not None

        again = index_corpus(session, data_dir, embed)
        assert (again.documents_changed, again.chunks_added, again.chunks_removed) == (0, 0, 0)
        assert again.kb_version is None and embed.calls == first.chunks

        uk = data_dir / "brand/uk/en/warranty.md"
        uk.write_text(
            uk.read_text(encoding="utf-8").replace(
                "Duration: 3 years, unlimited", "Duration: 4 years, unlimited"
            )
        )
        edited = index_corpus(session, data_dir, embed)
        assert (edited.documents_changed, edited.chunks_added, edited.chunks_removed) == (1, 1, 1)
        assert edited.kb_version == first.kb_version + 1
        paint = session.scalar(select(ChunkRecord.content).where(ChunkRecord.content.like("%Paintwork%")))
        assert paint is not None and "4 years" in paint

        (data_dir / "brand/de/de/warranty.md").unlink()
        removed = index_corpus(session, data_dir, embed)
        assert removed.documents_removed == 1 and removed.documents == 2
        assert session.get(DocumentRecord, "brand/de/de/warranty.md") is None


@pytest.mark.integration
def test_full_text_uses_the_chunk_language(database_url: str, data_dir: Path) -> None:
    with get_session() as session:
        index_corpus(session, data_dir, FakeEmbedder(), full=True)
        # German stemming: the query "Garantien" (plural) matches "Garantie" only under the german config.
        hits = session.scalars(
            text("SELECT document_path FROM chunks WHERE tsv @@ to_tsquery('german', 'Garantien')")
        ).all()
    assert hits and set(hits) == {"brand/de/de/warranty.md"}
