"""Live open-data tools: NHTSA recalls (US government, no key) and EV chargers (OpenStreetMap +
Open Charge Map).

All calls are short, cached and fail with ToolUnavailableError, so the assistant can offer a human instead.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx

from car_support.config import get_settings


class ToolUnavailableError(Exception):
    pass


def _get_json(url: str, params: dict[str, Any]) -> Any:
    try:
        resp = httpx.get(
            url, params=params, timeout=10, headers={"User-Agent": get_settings().http_user_agent}
        )
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ToolUnavailableError(f"{url}: {exc}") from exc


# ── Recalls ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Recall:
    campaign: str
    component: str
    summary: str
    remedy: str


@dataclass(frozen=True)
class RecallReport:
    vehicle: str  # e.g. "2012 HONDA ACCORD"
    recalls: tuple[Recall, ...]


# ponytail: lru_cache never expires; recall data changes slowly and the process restarts on deploy.
@lru_cache(maxsize=256)
def decode_vin(vin: str) -> tuple[str, str, int]:
    """(make, model, model year) for a VIN, from NHTSA vPIC."""
    data = _get_json(f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}", {"format": "json"})
    row = data["Results"][0]
    if not (row.get("Make") and row.get("Model") and row.get("ModelYear")):
        raise ValueError(f"NHTSA could not decode VIN {vin}")
    return row["Make"], row["Model"], int(row["ModelYear"])


@lru_cache(maxsize=256)
def find_recalls(make: str, model: str, year: int) -> RecallReport:
    """Safety recalls NHTSA has on record for a make, model and model year (US market)."""
    data = _get_json(
        "https://api.nhtsa.gov/recalls/recallsByVehicle", {"make": make, "model": model, "modelYear": year}
    )
    recalls = tuple(
        Recall(r["NHTSACampaignNumber"], r.get("Component", ""), r.get("Summary", ""), r.get("Remedy", ""))
        for r in data.get("results", [])
    )
    return RecallReport(f"{year} {make} {model}".upper(), recalls)


# ── Chargers ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Charger:
    name: str
    address: str
    distance_km: float
    max_power_kw: float | None
    connectors: tuple[str, ...]
    url: str


@lru_cache(maxsize=256)
def geocode(place: str) -> tuple[float, float, str]:
    """(lat, lon, display name) from OpenStreetMap Nominatim (max 1 request/s; results are cached)."""
    hits = _get_json("https://nominatim.openstreetmap.org/search", {"q": place, "format": "json", "limit": 1})
    if not hits:
        raise ValueError(f"place not found: {place}")
    return float(hits[0]["lat"]), float(hits[0]["lon"]), hits[0]["display_name"]


@lru_cache(maxsize=256)
def find_chargers(place: str, radius_km: int = 5, limit: int = 5) -> tuple[str, tuple[Charger, ...]]:
    """Public chargers near a place, nearest first, from Open Charge Map."""
    key = get_settings().open_charge_map_key
    if not key:
        raise ToolUnavailableError("Open Charge Map API key not configured (CS_OPEN_CHARGE_MAP_KEY)")
    lat, lon, label = geocode(place)
    pois = _get_json(
        "https://api.openchargemap.io/v3/poi",
        {
            "key": key,
            "latitude": lat,
            "longitude": lon,
            "distance": radius_km,
            "distanceunit": "KM",
            "maxresults": limit,
            "compact": "false",  # full records include connector type names
            "verbose": "false",
        },
    )
    chargers = []
    for poi in pois:
        address = poi.get("AddressInfo", {})
        connections = poi.get("Connections") or []
        powers = [c["PowerKW"] for c in connections if c.get("PowerKW")]
        chargers.append(
            Charger(
                name=address.get("Title", "Charging station"),
                address=", ".join(filter(None, [address.get("AddressLine1"), address.get("Town")])),
                distance_km=round(float(address.get("Distance") or 0), 1),
                max_power_kw=max(powers) if powers else None,
                connectors=tuple(
                    sorted({(c.get("ConnectionType") or {}).get("Title", "?") for c in connections})
                ),
                url=f"https://map.openchargemap.io/?id={poi.get('ID')}",
            )
        )
    return label, tuple(sorted(chargers, key=lambda c: c.distance_km))
