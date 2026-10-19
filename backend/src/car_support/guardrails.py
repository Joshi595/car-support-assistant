"""Guardrails around the model.

Input:  personal data is redacted before it reaches a model, a log or the database; clear prompt-injection
        attempts are refused before any model call (rules, plus an optional Prompt Guard classifier).
Output: the system prompt must not leak, and personal data the customer typed is not echoed back.
"""

import logging
import re
from collections.abc import Callable

import httpx

from car_support.config import get_settings

log = logging.getLogger(__name__)

# ── Personal data ──────────────────────────────────────────────────────────────

# Order matters: the most specific patterns run first, so a VIN is not mistaken for a phone number.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,3})?\b")),
    ("vin", re.compile(r"\b(?=[A-HJ-NPR-Z0-9]*\d)(?=[A-HJ-NPR-Z0-9]*[A-HJ-NPR-Z])[A-HJ-NPR-Z0-9]{17}\b")),
    ("card", re.compile(r"\b(?:\d[ -]?){12,18}\d\b")),
    ("phone", re.compile(r"(?<![\w/])\+?\(?\d[\d ()/.-]{6,}\d(?![\w/])")),
]


def _luhn_ok(number: str) -> bool:
    digits = [int(d) for d in number if d.isdigit()][::-1]
    total = sum(d if i % 2 == 0 else (d * 2 - 9 if d > 4 else d * 2) for i, d in enumerate(digits))
    return total % 10 == 0


def _is_match(kind: str, value: str) -> bool:
    if kind == "card":
        return _luhn_ok(value)
    if kind == "phone":  # 9 to 15 digits (E.164 maximum); fewer are years, prices or "2014-2015"
        return 9 <= sum(c.isdigit() for c in value) <= 15
    return True


def _redact(text: str, found: list[str] | None = None) -> str:
    def substitute(kind: str) -> Callable[[re.Match[str]], str]:
        def replace(m: re.Match[str]) -> str:
            if not _is_match(kind, m[0]):
                return m[0]
            if found is not None:
                found.append(m[0])
            return f"[{kind}]"

        return replace

    for kind, pattern in _PATTERNS:
        text = pattern.sub(substitute(kind), text)
    return text


def redact(text: str) -> str:
    """Replace emails, IBANs, VINs, payment cards and phone numbers with placeholders like [phone]."""
    return _redact(text)


def scrub_echo(answer: str, customer_text: str) -> str:
    """Remove personal data the customer typed from an answer, but keep the company's own phone numbers
    and addresses, which come from the documents (redacting all numbers would hide the hotline)."""
    values: list[str] = []
    _redact(customer_text, values)
    for value in sorted(values, key=len, reverse=True):
        answer = answer.replace(value, "[removed]")
    return answer


# ── Prompt injection ───────────────────────────────────────────────────────────

# Clear attempts to override instructions or extract the prompt, in English and German. Messages that only
# assert false "facts" are not blocked: the answer is grounded in the documents and ignores them anyway.
_INJECTION = re.compile(
    "|".join(
        [
            r"\b(ignore|disregard|forget|override)\b.{0,40}\b(instructions?|rules?|prompts?|guidelines)\b",
            r"\b(system|developer|hidden|initial)\s+(prompt|message|instructions?)\b",
            r"\b(repeat|print|reveal|show|output)\b.{0,40}\b(text|words|everything|instructions?)\s+(above|before)",
            r"\byou are now\b|\bpretend (to be|you are)\b",
            r"\b(DAN|jailbreak|developer mode)\b",
            r"\b(vergiss|ignoriere|missachte)\b.{0,40}\b(regeln|anweisungen|vorgaben|instruktionen)\b",
            r"\b(system-?prompt|systemanweisung)",
            r"\bdu bist (jetzt|nun)\b|\btu so,? als\b",
        ]
    ),
    re.IGNORECASE | re.DOTALL,
)


def _prompt_guard_score(text: str, model: str) -> float:
    """Injection probability from Llama Prompt Guard 2 on Groq (opt-in; sends the text to Groq)."""
    key = get_settings().groq_api_key
    if key is None:
        raise ValueError("CS_PROMPT_GUARD_MODEL needs CS_GROQ_API_KEY")
    resp = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key.get_secret_value()}"},
        json={"model": model.removeprefix("groq:"), "messages": [{"role": "user", "content": text}]},
        timeout=10,
    )
    resp.raise_for_status()
    return float(resp.json()["choices"][0]["message"]["content"])


def is_injection(text: str, classifier: Callable[[str, str], float] = _prompt_guard_score) -> bool:
    if _INJECTION.search(text):
        return True
    settings = get_settings()
    if not settings.prompt_guard_model:
        return False
    try:
        return classifier(text, settings.prompt_guard_model) >= settings.prompt_guard_threshold
    except Exception:  # an unavailable classifier must not block customers; the rules still apply
        log.warning("prompt guard unavailable", exc_info=True)
        return False


# ── Output ─────────────────────────────────────────────────────────────────────

# Distinctive phrases of our prompts: if one appears in an answer, the model is repeating its instructions.
_PROMPT_FRAGMENTS = (
    "using only the numbered passages",
    "cite the passage number",
    "reply with exactly this sentence",
    "the passages are reference text",
    "you analyse messages sent to",
)


def leaks_prompt(answer: str) -> bool:
    lowered = answer.lower()
    return any(fragment in lowered for fragment in _PROMPT_FRAGMENTS)
