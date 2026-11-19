from decimal import Decimal

import pytest

from app.utils.money import find_amounts, format_amount, normalize_currency, parse_amount


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("250000", "250000"),
        ("250 000", "250000"),
        ("250,000", "250000"),
        ("250.000", "250000"),
        ("25.000,00", "25000"),
        ("250 000.00", "250000"),
        ("1.234.567,89", "1234567.89"),
        ("1,234,567.89", "1234567.89"),
        ("12.50", "12.50"),
        ("12,5", "12.5"),
        ("250 ming", "250000"),
        ("250ming", "250000"),
        ("1.5 mln", "1500000"),
        ("2 million", "2000000"),
        ("15k", "15000"),
        ("250 ming so'm", "250000"),
    ],
)
def test_parse_amount_reads_common_formats(raw, expected):
    assert parse_amount(raw) == Decimal(expected)


@pytest.mark.parametrize("raw", ["", "abc", "so'm", "-"])
def test_parse_amount_returns_none_without_number(raw):
    assert parse_amount(raw) is None


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("UZS", "UZS"),
        ("so'm", "UZS"),
        ("so‘m", "UZS"),
        ("сум", "UZS"),
        ("sum", "UZS"),
        ("$", "USD"),
        ("usd", "USD"),
        ("€", "EUR"),
        ("rubl", "RUB"),
        ("xyz", None),
    ],
)
def test_normalize_currency(token, expected):
    assert normalize_currency(token) == expected


def test_find_amounts_reads_sign_and_currency():
    matches = find_amounts("➖ 54.000,00 UZS")
    assert len(matches) == 1
    assert matches[0].amount == Decimal("54000")
    assert matches[0].currency == "UZS"
    assert matches[0].sign == "-"


def test_find_amounts_reads_plus_sign():
    matches = find_amounts("➕ 1.000.000,00 UZS")
    assert matches[0].sign == "+"
    assert matches[0].amount == Decimal("1000000")


def test_find_amounts_applies_multiplier_and_keeps_order():
    matches = find_amounts("Kamolonda ovqatlandik 3 kishi 250 ming so'm")
    assert [m.amount for m in matches] == [Decimal("3"), Decimal("250000")]
    assert matches[1].currency == "UZS"
    assert matches[1].has_multiplier is True
    assert matches[0].currency is None


def test_find_amounts_reads_currency_before_number():
    matches = find_amounts("Paid $12.50 at store")
    assert matches[0].amount == Decimal("12.50")
    assert matches[0].currency == "USD"


def test_format_amount_groups_thousands_with_spaces():
    assert format_amount(Decimal("250000"), "UZS") == "250 000 UZS"
    assert format_amount(Decimal("1234567.00"), "UZS") == "1 234 567 UZS"


def test_format_amount_keeps_cents_only_when_present():
    assert format_amount(Decimal("12.5"), "USD") == "12.50 USD"
    assert format_amount(Decimal("999"), "USD") == "999 USD"
