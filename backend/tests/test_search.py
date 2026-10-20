"""Hybrid search filters and fusion on a real Postgres (fake embeddings, so no Ollama needed)."""

import shutil
from datetime import date
from pathlib import Path

import pytest

from car_support.config import get_settings
from car_support.db.session import get_session
from car_support.ingest.index import index_corpus
from car_support.retrieval.search import Filters, search
from tests.test_ingest import FakeEmbedder

DATA = get_settings().data_dir
FILES = [
    "catalog.toml",
    "brand/uk/en/charging-tariffs.md",
    "brand/uk/en/charging-tariffs-2027.md",
    "brand/us/en/charging-tariffs.md",
    "brand/de/de/warranty.md",
    "brand/global/en/model-ion-x.html",
]


@pytest.fixture(scope="module")
def indexed(database_url: str, tmp_path_factory: pytest.TempPathFactory) -> None:
    root: Path = tmp_path_factory.mktemp("data")
    for rel in FILES:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(DATA / rel, root / rel)
    catalog = (root / "catalog.toml").read_text(encoding="utf-8")
    (root / "catalog.toml").write_text(catalog.split("# ── Brand: model-specific")[0], encoding="utf-8")
    with get_session() as session:
        index_corpus(session, root, FakeEmbedder(), full=True)


def _paths(query: str, filters: Filters, mode: str = "keyword") -> list[str]:
    vector = FakeEmbedder()([query])[0]
    with get_session() as session:
        return [p.path for p in search(session, query, vector, filters, k=10, mode=mode)]  # type: ignore[arg-type]


@pytest.mark.integration
@pytest.mark.usefixtures("indexed")
def test_only_the_customers_market_and_global_documents_are_searched() -> None:
    paths = _paths("charging tariff idle fee", Filters(market="us", as_of=date(2026, 10, 1)), mode="hybrid")
    assert paths and all(p.startswith(("brand/us/", "brand/global/")) for p in paths)


@pytest.mark.integration
@pytest.mark.usefixtures("indexed")
def test_the_version_valid_on_the_query_date_is_used() -> None:
    before = _paths("Charge Flex rapid", Filters(market="uk", as_of=date(2026, 10, 1)))
    after = _paths("Charge Flex rapid", Filters(market="uk", as_of=date(2027, 2, 1)))
    assert (
        "brand/uk/en/charging-tariffs.md" in before and "brand/uk/en/charging-tariffs-2027.md" not in before
    )
    assert "brand/uk/en/charging-tariffs-2027.md" in after and "brand/uk/en/charging-tariffs.md" not in after


@pytest.mark.integration
@pytest.mark.usefixtures("indexed")
def test_keyword_search_matches_any_word_with_language_specific_stemming() -> None:
    # German inflection ("Garantien" → "Garantie") and OR semantics (the other words do not occur).
    assert (
        _paths("Welche Garantien bekomme ich eigentlich?", Filters(market="de"))[0]
        == "brand/de/de/warranty.md"
    )
    assert _paths("V2L", Filters(market="uk")) == ["brand/global/en/model-ion-x.html"]
    assert _paths("zzzz qqqq", Filters(market="uk")) == []


def test_off_topic_gate_uses_the_best_similarity() -> None:
    from car_support.retrieval import is_relevant
    from car_support.retrieval.search import Passage

    def passage(similarity: float) -> Passage:
        return Passage(
            "c", "d", "p", "t", ("t",), "x", "brand", "uk", "en", None, "l", None, 0.01, similarity
        )

    assert is_relevant([passage(0.30), passage(0.55)], threshold=0.40)
    assert not is_relevant([passage(0.30), passage(0.35)], threshold=0.40)
    assert not is_relevant([], threshold=0.40)


def test_off_topic_threshold_follows_the_embedding_model() -> None:
    from car_support.config import Settings, relevance_threshold

    assert relevance_threshold(Settings(embed_model="qwen3-embedding:4b")) == 0.40
    assert relevance_threshold(Settings(embed_model="qwen3-embedding:0.6b")) == 0.28
    assert relevance_threshold(Settings(embed_model="some-other-model")) == 0.0  # unmeasured: no gate
    assert relevance_threshold(Settings(embed_model="qwen3-embedding:4b", relevance_threshold=0.5)) == 0.5
