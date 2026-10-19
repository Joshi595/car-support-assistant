"""The document catalog: one DocMeta per file in data/, from its path plus data/catalog.toml."""

import tomllib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

SOURCE_TYPES = ("brand", "public")
SUFFIXES = {".md", ".html", ".pdf", ".txt", ".docx"}


@dataclass(frozen=True)
class DocMeta:
    path: str  # relative to the data dir, e.g. "brand/uk/en/warranty.md"
    doc_id: str  # stable id shared by all versions of one document
    source_type: str  # "brand" | "public"
    market: str  # "de" | "uk" | "us" | "global"
    language: str  # ISO 639-1, e.g. "en", "de"
    valid_from: date
    licence: str
    models: tuple[str, ...] = ()  # empty = applies to every model
    url: str | None = None
    attribution: str | None = None
    extra: dict[str, object] = field(default_factory=dict, compare=False)


class CatalogError(ValueError):
    pass


def load_catalog(data_dir: Path) -> list[DocMeta]:
    """Every document under data_dir/{brand,public}, with defaults and per-file overrides applied."""
    raw = tomllib.loads((data_dir / "catalog.toml").read_text(encoding="utf-8"))
    overrides: dict[str, dict[str, object]] = raw.get("docs", {})
    files = sorted(
        p.relative_to(data_dir).as_posix()
        for kind in SOURCE_TYPES
        for p in (data_dir / kind).rglob("*")
        if p.suffix in SUFFIXES
    )
    if unknown := set(overrides) - set(files):
        raise CatalogError(f"catalog.toml lists files that do not exist: {sorted(unknown)}")

    docs = []
    for path in files:
        source_type, market, language, _ = path.split("/", 3)
        fields = {**raw["defaults"][source_type], **overrides.get(path, {})}
        doc = DocMeta(
            path=path,
            doc_id=str(fields.pop("doc_id", path.rsplit(".", 1)[0])),
            source_type=source_type,
            market=market,
            language=language,
            valid_from=fields.pop("valid_from"),  # TOML dates parse to datetime.date
            licence=str(fields.pop("licence")),
            models=tuple(fields.pop("models", ())),
            url=fields.pop("url", None),
            attribution=fields.pop("attribution", None),
            extra=fields,
        )
        if source_type == "public" and not doc.url:
            raise CatalogError(f"{path}: public documents need a source url in catalog.toml")
        docs.append(doc)
    return docs
