"""The assistant as a LangGraph state machine.

    understand ─┬─ question ──────► retrieve ─┬─ relevant ──► generate ─► validate
                ├─ recall_lookup ─► recall    └─ off-topic ─► refuse
                ├─ charger_search ► chargers
                ├─ human_agent ───► handoff
                └─ off_topic ─────► off_topic

`understand` is one structured LLM call (intent, standalone question, language, tool arguments).
Everything after it is deterministic except `generate`.
"""

import logging
import re
from datetime import date
from functools import lru_cache
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from car_support.db.session import get_session
from car_support.llm import chat_model, structured_model
from car_support.pipeline import tools
from car_support.pipeline.prompts import (
    ANSWER_PROMPT,
    HANDOFF,
    LANGUAGE_NAMES,
    MARKET_NAMES,
    OFF_TOPIC,
    REFUSAL,
    UNDERSTAND_PROMPT,
    Language,
    Understanding,
    detect_language,
)
from car_support.retrieval import Filters, Passage, is_relevant, retrieve

log = logging.getLogger(__name__)

Outcome = Literal["answer", "refuse", "off_topic", "recall", "chargers", "handoff", "clarify", "unavailable"]


class State(TypedDict, total=False):
    # input
    question: str
    history: list[tuple[str, str]]  # [("user" | "assistant", text), ...], oldest first
    market: str
    as_of: date
    # produced by the graph
    understanding: Understanding
    language: Language  # of the customer's latest message
    passages: list[Passage]
    answer: str
    citations: list[int]  # 1-based numbers of the passages the answer cites
    outcome: Outcome


def new_state(question: str, market: str, history: list[tuple[str, str]] | None = None) -> State:
    return {"question": question, "market": market, "history": history or [], "as_of": date.today()}


# ── understand ─────────────────────────────────────────────────────────────────

_VIN = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
_HUMAN = re.compile(r"\b(human|agent|person|someone|mitarbeiter|menschen)\b", re.I)


def _fallback_understanding(question: str) -> Understanding:
    """Rules used when the model's structured output fails: never worse than "treat it as a question"."""
    vin = _VIN.search(question.upper())
    intent = "recall_lookup" if vin else "human_agent" if _HUMAN.search(question) else "question"
    return Understanding(
        intent=intent,
        standalone_question=question,
        vin=vin[0] if vin else None,
        make=None,
        model=None,
        year=None,
        location=None,
    )


def understand(s: State) -> State:
    transcript = "\n".join(
        f"{'Customer' if role == 'user' else 'Assistant'}: {text[:400]}" for role, text in s["history"][-6:]
    )
    prompt = UNDERSTAND_PROMPT.format(history=transcript or "(none)", question=s["question"])
    try:
        result = structured_model(Understanding).invoke([("user", prompt)])
    except Exception:  # model down, invalid JSON, provider error: degrade to rules, do not fail the request
        log.warning("understand: structured output failed, using rules", exc_info=True)
        result = _fallback_understanding(s["question"])
    if not result.standalone_question.strip():
        result = result.model_copy(update={"standalone_question": s["question"]})
    understanding = _check_tool_arguments(result, s["question"])
    return {"understanding": understanding, "language": detect_language(s["question"])}


def _check_tool_arguments(u: Understanding, question: str) -> Understanding:
    """Deterministic guard on the model's tool choice: a VIN must look like one, and a tool without the
    arguments it needs becomes a normal question (the documents explain recalls and charging)."""
    vin = u.vin if u.vin and _VIN.fullmatch(u.vin.upper()) else None
    if not vin and (found := _VIN.search(question.upper())):
        vin = found[0]  # a VIN is unambiguous: do not rely on the model to copy it
    u = u.model_copy(update={"vin": vin})
    vehicle_known = bool(vin or (u.make and u.model and u.year))
    if (u.intent == "recall_lookup" and not vehicle_known) or (
        u.intent == "charger_search" and not u.location
    ):
        return u.model_copy(update={"intent": "question"})
    return u


def route_intent(s: State) -> str:
    return {
        "question": "retrieve",
        "recall_lookup": "recall",
        "charger_search": "chargers",
        "human_agent": "handoff",
        "off_topic": "off_topic",
    }[s["understanding"].intent]


# ── knowledge-base answers ─────────────────────────────────────────────────────


def retrieve_passages(s: State) -> State:
    with get_session() as session:
        passages = retrieve(
            session, s["understanding"].standalone_question, Filters(market=s["market"], as_of=s["as_of"])
        )
    return {"passages": passages}


def route_relevance(s: State) -> str:
    return "generate" if is_relevant(s["passages"]) else "refuse"


def format_passages(passages: list[Passage]) -> str:
    return "\n\n".join(f"[{i}] {p.content}" for i, p in enumerate(passages, 1))


def generate(s: State) -> State:
    language = s["language"]
    system = ANSWER_PROMPT.format(
        refusal=REFUSAL[language],
        language_name=LANGUAGE_NAMES[language],
        market_name=MARKET_NAMES[s["market"]],
        passages=format_passages(s["passages"]),
    )
    try:
        message = chat_model().invoke([("system", system), ("user", s["understanding"].standalone_question)])
    except Exception:  # model down after retry and fallback: say so and offer a human, never crash the chat
        log.exception("generate: chat model failed")
        return {"answer": _TEXT["unavailable"][language], "citations": [], "outcome": "unavailable"}
    return {"answer": str(message.content).strip()}


_CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
# Models differ in citation brackets (gpt-oss writes U+3010 1 U+3011), spaces and hyphens (U+2011 in phones).
_NORMALIZE = str.maketrans(
    {"\u3010": "[", "\u3011": "]", "\uff3b": "[", "\uff3d": "]"}  # citation brackets
    | {"\u202f": " ", "\u00a0": " ", "\u2009": " ", "\u2010": "-", "\u2011": "-"}  # spaces, hyphens
)


def is_refusal(answer: str) -> bool:
    normalized = answer.replace("’", "'").lower()
    return "couldn't find that in our documentation" in normalized or "nicht finden" in normalized


def validate(s: State) -> State:
    """Keep only citations of passages that exist. An answer that cites nothing is not trusted."""
    if s.get("outcome") == "unavailable":
        return {}
    language = s["language"]
    answer, count = s["answer"].translate(_NORMALIZE), len(s["passages"])
    if is_refusal(answer):
        return {"answer": REFUSAL[language], "citations": [], "outcome": "refuse"}

    def keep_valid(m: re.Match[str]) -> str:
        valid = [n for n in (int(x) for x in m[1].split(",")) if 1 <= n <= count]
        return f"[{', '.join(map(str, valid))}]" if valid else ""

    answer = _CITATION.sub(keep_valid, answer).replace(" .", ".").strip()
    cited = sorted({int(n) for group in _CITATION.findall(answer) for n in group.split(",")})
    if not cited:
        log.info("validate: answer without valid citations replaced by refusal")
        return {"answer": REFUSAL[language], "citations": [], "outcome": "refuse"}
    return {"answer": answer, "citations": cited, "outcome": "answer"}


def refuse(s: State) -> State:
    return {"answer": REFUSAL[s["language"]], "citations": [], "outcome": "refuse"}


# ── tools and fixed replies ────────────────────────────────────────────────────

_TEXT: dict[str, dict[Language, str]] = {
    "recall_need": {
        "en": "To check recalls I need your 17-character VIN, "
        "or the make, model and model year of the vehicle.",
        "de": "Für die Rückrufprüfung brauche ich Ihre 17-stellige FIN oder Marke, Modell und Baujahr.",
    },
    "recall_none": {
        "en": "NHTSA has no safety recalls on record for the {vehicle}.",
        "de": "Bei der NHTSA sind für {vehicle} keine Sicherheitsrückrufe verzeichnet.",
    },
    "recall_found": {
        "en": "NHTSA lists {n} safety recall(s) for the {vehicle}. They apply to this model year; "
        "your dealer or nhtsa.gov/recalls can confirm with your VIN whether the repair was already done "
        "on your car.",
        "de": "Die NHTSA führt {n} Sicherheitsrückruf(e) für {vehicle}. Sie gelten für dieses Modelljahr; "
        "ob die Reparatur an Ihrem Fahrzeug schon erfolgt ist, kann Ihre Werkstatt anhand der FIN prüfen.",
    },
    "recall_us_only": {
        "en": "Note: NHTSA covers vehicles sold in the United States.",
        "de": "Hinweis: Die NHTSA-Daten betreffen in den USA verkaufte Fahrzeuge.",
    },
    "charger_need": {
        "en": "Which place should I search for charging stations near?",
        "de": "In der Nähe welches Ortes soll ich nach Ladestationen suchen?",
    },
    "charger_none": {
        "en": "I found no public charging stations within 5 km of {place}.",
        "de": "Im Umkreis von 5 km um {place} habe ich keine öffentlichen Ladestationen gefunden.",
    },
    "charger_found": {
        "en": "Public charging stations near {place} (data: Open Charge Map, CC BY 4.0):",
        "de": "Öffentliche Ladestationen in der Nähe von {place} (Daten: Open Charge Map, CC BY 4.0):",
    },
    "unavailable": {
        "en": "Sorry, that service is not available right now. "
        "Would you like me to connect you with a member of our customer service team?",
        "de": "Dieser Dienst ist gerade nicht verfügbar. Soll ich Sie mit einem Mitarbeiter verbinden?",
    },
}


def recall(s: State) -> State:
    u, lang = s["understanding"], s["language"]
    try:
        if u.vin:
            make, model, year = tools.decode_vin(u.vin)
        elif u.make and u.model and u.year:
            make, model, year = u.make, u.model, u.year
        else:
            return {"answer": _TEXT["recall_need"][lang], "outcome": "clarify"}
        report = tools.find_recalls(make, model, year)
    except tools.ToolUnavailableError:
        log.warning("recall: NHTSA unavailable", exc_info=True)
        return {"answer": _TEXT["unavailable"][lang], "outcome": "unavailable"}
    except ValueError:
        return {"answer": _TEXT["recall_need"][lang], "outcome": "clarify"}

    if not report.recalls:
        lines = [_TEXT["recall_none"][lang].format(vehicle=report.vehicle)]
    else:
        lines = [_TEXT["recall_found"][lang].format(n=len(report.recalls), vehicle=report.vehicle), ""]
        lines += [
            f"- {r.campaign}: {r.component.title()}. {r.summary[:220].rstrip()}…" for r in report.recalls[:5]
        ]
    if s["market"] != "us":
        lines += ["", _TEXT["recall_us_only"][lang]]
    return {"answer": "\n".join(lines), "outcome": "recall"}


def chargers(s: State) -> State:
    u, lang = s["understanding"], s["language"]
    if not u.location:
        return {"answer": _TEXT["charger_need"][lang], "outcome": "clarify"}
    try:
        label, found = tools.find_chargers(u.location)
    except tools.ToolUnavailableError as exc:  # also raised when no API key is configured
        log.warning("chargers: service unavailable: %s", exc)
        return {"answer": _TEXT["unavailable"][lang], "outcome": "unavailable"}
    except ValueError:
        return {"answer": _TEXT["charger_need"][lang], "outcome": "clarify"}
    place = label.split(",")[0]
    if not found:
        return {"answer": _TEXT["charger_none"][lang].format(place=place), "outcome": "chargers"}
    lines = [_TEXT["charger_found"][lang].format(place=place), ""]
    for c in found:
        power = f", up to {c.max_power_kw:g} kW" if c.max_power_kw else ""
        lines.append(f"- {c.name} ({c.distance_km} km{power}): {c.address}. {', '.join(c.connectors)}")
    return {"answer": "\n".join(lines), "outcome": "chargers"}


def handoff(s: State) -> State:
    return {"answer": HANDOFF[s["language"]], "outcome": "handoff"}


def off_topic(s: State) -> State:
    return {"answer": OFF_TOPIC[s["language"]], "outcome": "off_topic"}


@lru_cache
def build_graph() -> CompiledStateGraph[Any, Any, Any, Any]:
    g = StateGraph(State)
    for name, node in [
        ("understand", understand),
        ("retrieve", retrieve_passages),
        ("generate", generate),
        ("validate", validate),
        ("refuse", refuse),
        ("recall", recall),
        ("chargers", chargers),
        ("handoff", handoff),
        ("off_topic", off_topic),
    ]:
        g.add_node(name, node)  # type: ignore[call-overload]
    g.add_edge(START, "understand")
    g.add_conditional_edges("understand", route_intent)
    g.add_conditional_edges("retrieve", route_relevance)
    g.add_edge("generate", "validate")
    for terminal in ["validate", "refuse", "recall", "chargers", "handoff", "off_topic"]:
        g.add_edge(terminal, END)
    return g.compile()
