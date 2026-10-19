"""Snapshot open-licensed public guidance into data/public/ (run by hand when refreshing; stdlib only).

GOV.UK content is © Crown copyright, available under the Open Government Licence v3.0:
https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/

    uv run python ../data/scripts/fetch_public.py      (from backend/)
"""

import json
import urllib.request
from pathlib import Path

GOV_UK_PAGES = [
    "vehicle-recalls-and-faults",
    "consumer-protection-rights",
    "getting-an-mot",
    "vehicle-tax-rate-tables",
    "guidance/regulations-electric-vehicle-smart-charge-points",
    "driving-abroad",
]
OUT = Path(__file__).resolve().parent.parent / "public" / "uk" / "en"


def fetch_gov_uk(path: str) -> str:
    """Return one GOV.UK page as a small, clean HTML document (title + body, or one <h2> per guide part)."""
    with urllib.request.urlopen(f"https://www.gov.uk/api/content/{path}", timeout=30) as resp:  # noqa: S310 (fixed https host)
        item = json.load(resp)
    details = item["details"]
    parts = details.get("parts") or [{"title": None, "body": details.get("body", "")}]
    body = "\n".join((f"<h2>{p['title']}</h2>\n" if p["title"] else "") + p["body"] for p in parts)
    return f"<html><head><title>{item['title']}</title></head><body>\n<h1>{item['title']}</h1>\n{body}\n</body></html>\n"


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for page in GOV_UK_PAGES:
        target = OUT / (page.rsplit("/", 1)[-1] + ".html")
        target.write_text(fetch_gov_uk(page), encoding="utf-8")
        print(f"saved {target.relative_to(OUT.parent.parent.parent)}  <-  https://www.gov.uk/{page}")
