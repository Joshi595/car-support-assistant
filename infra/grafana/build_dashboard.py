"""Generate dashboards/car-support.json (run after changing panels: python infra/grafana/build_dashboard.py).

Colours: validated categorical slots for the dark surface (fixed order, never cycled); the status red is
reserved for "unavailable". One axis per panel; headline numbers as stat tiles.
"""

import json
from pathlib import Path

BLUE, ORANGE, AQUA, YELLOW, VIOLET = "#3987e5", "#d95926", "#199e70", "#c98500", "#9085e9"
CRITICAL = "#d03b3b"
DS = {"type": "prometheus", "uid": "prometheus"}


def target(expr: str, legend: str = "", instant: bool = False) -> dict[str, object]:
    return {"datasource": DS, "expr": expr, "legendFormat": legend, "instant": instant, "range": not instant}


def stat(title: str, expr: str, unit: str, x: int, desc: str) -> dict[str, object]:
    return {
        "type": "stat",
        "title": title,
        "description": desc,
        "gridPos": {"h": 4, "w": 4, "x": x, "y": 0},
        "datasource": DS,
        "targets": [target(expr, instant=True)],
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "decimals": 1 if unit != "short" else 0,
                "color": {"mode": "fixed", "fixedColor": "text"},
            }
        },
        "options": {
            "colorMode": "none",
            "graphMode": "none",
            "textMode": "value",
            "reduceOptions": {"calcs": ["lastNotNull"]},
        },
    }


def series_colors(colors: dict[str, str]) -> list[dict[str, object]]:
    return [
        {
            "matcher": {"id": "byName", "options": name},
            "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": c}}],
        }
        for name, c in colors.items()
    ]


def timeseries(
    title: str,
    targets: list[dict[str, object]],
    colors: dict[str, str],
    unit: str,
    x: int,
    y: int,
    w: int,
    desc: str,
) -> dict[str, object]:
    return {
        "type": "timeseries",
        "title": title,
        "description": desc,
        "gridPos": {"h": 9, "w": w, "x": x, "y": y},
        "datasource": DS,
        "targets": targets,
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "custom": {"lineWidth": 2, "fillOpacity": 0, "showPoints": "never", "axisSoftMin": 0},
            },
            "overrides": series_colors(colors),
        },
        "options": {
            "legend": {"displayMode": "list", "placement": "bottom"},
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
    }


def rate(selector: str) -> str:
    return f"sum(rate(cs_answers_total{{{selector}}}[$__rate_interval])) * 60"


def ratio(numerator: str, denominator: str) -> str:
    return f"sum(increase({numerator}[$__range])) / clamp_min(sum(increase({denominator}[$__range])), 1)"


OUTCOMES = {
    "Answered": 'outcome="answer"',
    "Refused": 'outcome="refuse"',
    "Handed off": 'outcome="handoff"',
    "Tool answer": 'outcome=~"recall|chargers"',
    "Other": 'outcome=~"off_topic|blocked|clarify"',
    "Unavailable": 'outcome="unavailable"',
}

panels = [
    stat(
        "Replies",
        "sum(increase(cs_answers_total[$__range]))",
        "short",
        0,
        "Assistant replies in the selected time range.",
    ),
    stat(
        "Reply time, p95",
        "histogram_quantile(0.95, sum by (le) (rate(cs_answer_seconds_bucket[$__range])))",
        "s",
        4,
        "95% of replies were faster than this.",
    ),
    stat(
        "Refused",
        ratio('cs_answers_total{outcome="refuse"}', "cs_answers_total"),
        "percentunit",
        8,
        "Share of replies where the documents had no answer.",
    ),
    stat(
        "Handed to a person",
        ratio("cs_handoffs_total", "cs_answers_total"),
        "percentunit",
        12,
        "Handoffs per reply.",
    ),
    stat(
        "Cache hits",
        ratio('cs_answer_cache_total{result="hit"}', "cs_answer_cache_total"),
        "percentunit",
        16,
        "Knowledge-base questions answered from the cache.",
    ),
    stat(
        "Rated helpful",
        ratio('cs_feedback_total{rating="helpful"}', "cs_feedback_total"),
        "percentunit",
        20,
        "Helpful ratings out of all ratings.",
    ),
    timeseries(
        "Replies per minute by outcome",
        [target(rate(sel), name) for name, sel in OUTCOMES.items()],
        dict(zip(OUTCOMES, [BLUE, ORANGE, AQUA, YELLOW, VIOLET, CRITICAL], strict=True)),
        "short",
        0,
        4,
        14,
        "Tool answer = recall or charger lookup. "
        "Other = off-topic, blocked injection attempts, clarifying questions.",
    ),
    timeseries(
        "Reply time",
        [
            target(
                "histogram_quantile(0.5, sum by (le) (rate(cs_answer_seconds_bucket[$__rate_interval])))",
                "median",
            ),
            target(
                "histogram_quantile(0.95, sum by (le) (rate(cs_answer_seconds_bucket[$__rate_interval])))",
                "p95",
            ),
        ],
        {"median": BLUE, "p95": ORANGE},
        "s",
        14,
        4,
        10,
        "Time from receiving a message to the final, validated reply.",
    ),
    {
        "type": "bargauge",
        "title": "Slowest pipeline steps, p95",
        "description": "Where reply time goes. understand and generate call the chat model; "
        "retrieve embeds the question.",
        "gridPos": {"h": 11, "w": 14, "x": 0, "y": 13},
        "datasource": DS,
        "targets": [
            target(
                "sort_desc(histogram_quantile(0.95, "
                "sum by (le, step) (rate(cs_step_seconds_bucket[$__range]))))",
                "{{step}}",
                instant=True,
            )
        ],
        "fieldConfig": {"defaults": {"unit": "s", "min": 0, "color": {"mode": "fixed", "fixedColor": BLUE}}},
        "options": {
            "orientation": "horizontal",
            "displayMode": "basic",
            "showUnfilled": False,
            "valueMode": "text",
        },
    },
    {
        "type": "stat",
        "title": "Failures in range",
        "description": "Live tools that failed, model calls that failed after retries and fallbacks, "
        "and refused injection attempts.",
        "gridPos": {"h": 11, "w": 10, "x": 14, "y": 13},
        "datasource": DS,
        "targets": [
            target(
                "sum(increase(cs_tool_errors_total[$__range])) or vector(0)", "Tool failures", instant=True
            ),
            target(
                "sum(increase(cs_model_errors_total[$__range])) or vector(0)", "Model failures", instant=True
            ),
            target(
                "sum(increase(cs_blocked_total[$__range])) or vector(0)", "Blocked attempts", instant=True
            ),
        ],
        "fieldConfig": {
            "defaults": {"unit": "short", "decimals": 0, "color": {"mode": "fixed", "fixedColor": "text"}}
        },
        "options": {
            "colorMode": "none",
            "graphMode": "none",
            "textMode": "value_and_name",
            "orientation": "horizontal",
            "reduceOptions": {"calcs": ["lastNotNull"]},
        },
    },
]

dashboard = {
    "uid": "car-support",
    "title": "Car support assistant",
    "description": "Replies, outcomes, latency, cache and feedback from the API's /metrics.",
    "tags": ["car-support"],
    "timezone": "browser",
    "schemaVersion": 39,
    "refresh": "30s",
    "time": {"from": "now-6h", "to": "now"},
    "panels": [{"id": i + 1, **p} for i, p in enumerate(panels)],
}

out = Path(__file__).parent / "dashboards" / "car-support.json"
out.write_text(json.dumps(dashboard, indent=2) + "\n", encoding="utf-8")
print(f"wrote {out}")
