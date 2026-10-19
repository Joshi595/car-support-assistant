import pytest

from car_support.guardrails import redact


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Mail me at jane.doe@example.com please", "Mail me at [email] please"),
        ("Call +44 7700 900456 or 07700 900123", "Call [phone] or [phone]"),
        ("US: (555) 010-0199", "US: [phone]"),
        ("My VIN is 1HGCM82633A004352.", "My VIN is [vin]."),
        ("IBAN DE89 3704 0044 0532 0130 00 and DE89370400440532013000", "IBAN [iban] and [iban]"),
        ("Card 4111 1111 1111 1111", "Card [card]"),
    ],
)
def test_personal_data_is_redacted(text: str, expected: str) -> None:
    assert redact(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "The warranty is 8 years or 100,000 miles.",
        "2014-2015 models, 10 to 80% in 28 minutes",
        "Price £46,995, final payment £19,800",
        "Hotline opening 8:00 to 20:00, model Ion 4",
        "Order number 1234 5678",  # 8 digits: not a phone number
        "Card-like but invalid 4111 1111 1111 1112",
    ],
)
def test_ordinary_numbers_are_kept(text: str) -> None:
    assert redact(text) == text
