"""Guardrails. Personal data is redacted before it is stored, logged or traced."""

import re
from collections.abc import Callable

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


def redact(text: str) -> str:
    """Replace emails, IBANs, VINs, payment cards and phone numbers with placeholders like [phone]."""

    def substitute(kind: str) -> Callable[[re.Match[str]], str]:
        def replace(m: re.Match[str]) -> str:
            value = m[0]
            if kind == "card" and not _luhn_ok(value):
                return value
            # 9 to 15 digits (E.164 maximum); fewer are years, prices or "2014-2015".
            if kind == "phone" and not 9 <= sum(c.isdigit() for c in value) <= 15:
                return value
            return f"[{kind}]"

        return replace

    for kind, pattern in _PATTERNS:
        text = pattern.sub(substitute(kind), text)
    return text
