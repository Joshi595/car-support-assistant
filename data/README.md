# Knowledge base

| Folder | Contents | Licence |
|---|---|---|
| `brand/` | Support documents of **Northwind Motors**, a fictional car maker | Fictional sample data, MIT (this repository) |
| `public/` | Snapshots of real public guidance | Per source, see below |
| `catalog.toml` | Metadata the path cannot express: versions, validity dates, models, source URLs | |
| `scripts/` | `fetch_public.py` (refresh snapshots), `build_manuals.sh` + `manuals/` (render the owner-manual PDFs) | |

Northwind Motors, its products, prices, phone numbers (UK 01632 drama range, US 555-01xx) and addresses are invented. Any resemblance to a real company is coincidental. Email domains use the reserved `.example` TLD.

## Layout

```
<source_type>/<market>/<language>/<document>
brand/uk/en/warranty.md         market-specific (de | uk | us)
brand/global/en/model-ion-4.html applies to every market
public/uk/en/getting-an-mot.html
```

The ingestion pipeline derives `source_type`, `market` and `language` from the path, and the `doc_id` from the path without its extension. Everything else comes from `catalog.toml`.

## The brand corpus

| Market | Language | Documents |
|---|---|---|
| Germany (`de`) | German | 13 topics + FAQ |
| United Kingdom (`uk`) | English | 13 topics + FAQ + a future tariff version |
| United States (`us`) | English | 13 topics + FAQ |
| All (`global`) | English | 4 model guides, 2 owner manuals (PDF) |

Topics per market: warranty, service and maintenance, roadside assistance, contact, complaints, ordering and delivery, finance and leasing, EV charging, charging tariffs, connected services, cancellations and returns, privacy, recalls.

Some facts deliberately differ between markets (warranty length, hotline numbers, deposits, charging ports) to test that retrieval respects the customer's market. German documents are written in German to test cross-lingual retrieval. Formats are Markdown, HTML and PDF to exercise every converter.

**Versioning:** `brand/uk/en/charging-tariffs-2027.md` shares the `doc_id` of `charging-tariffs.md` and has `valid_from = 2027-01-01`, so the assistant must quote the version valid on the question's date.

## Public sources

| Files | Source | Licence | Attribution |
|---|---|---|---|
| `public/uk/en/*.html` | [GOV.UK Content API](https://content-api.publishing.service.gov.uk/) (6 pages, URLs in `catalog.toml`) | [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/) | Contains public sector information licensed under the Open Government Licence v3.0. |

Refresh the snapshots with `uv run python ../data/scripts/fetch_public.py` (from `backend/`), review the diff, and update `valid_from` in `catalog.toml`.

## Live open-data tools (not stored here)

| Tool | API | Licence / terms |
|---|---|---|
| VIN decoding | [NHTSA vPIC](https://vpic.nhtsa.dot.gov/api/) | US government work, public domain; no key |
| Recall lookup | [NHTSA Recalls API](https://api.nhtsa.gov/recalls/recallsByVehicle) | US government work, public domain; no key |
| Geocoding (place → coordinates) | [OpenStreetMap Nominatim](https://nominatim.org/release-docs/latest/api/Search/) | ODbL; max 1 request/s with an identifying User-Agent (results are cached) |
| EV charger search | [Open Charge Map](https://openchargemap.org/develop) | Community data under CC BY 4.0 (attribution shown with every result); free API key in `CS_OPEN_CHARGE_MAP_KEY` |

## Adding a document

1. Put the file under the right `<source_type>/<market>/<language>/` folder (`.md`, `.html`, `.pdf`, `.txt` or `.docx`).
2. Add a `catalog.toml` entry if it is public (a `url` is required), model-specific, or a new version of an existing document.
3. Run `uv run pytest tests/test_corpus.py` from `backend/`.
4. Re-run ingestion: only new or changed chunks are re-embedded.
