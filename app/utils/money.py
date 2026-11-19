"""Summalarni o‘qish va ko‘rsatish."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.utils.validators import unify_apostrophes

_THOUSAND_SPACES = "    "

_NUMBER = re.compile(
    rf"\d{{1,3}}(?:[{_THOUSAND_SPACES}]\d{{3}})+(?:[.,]\d{{1,2}})?(?!\d)|\d+(?:[.,]\d+)*"
)

_MULTIPLIERS: tuple[tuple[str, int], ...] = (
    (r"mlrd|milliard|млрд\.?", 1_000_000_000),
    (r"mln|million|millon|млн\.?|миллион(?:ов|а)?", 1_000_000),
    (r"ming|тысяч[аи]?|тыс\.?|k|к", 1_000),
)
_MULTIPLIER = re.compile(
    r"\s*(?:" + "|".join(f"(?P<m{i}>{pattern})" for i, (pattern, _) in enumerate(_MULTIPLIERS)) + r")(?![a-zа-яё])",
    re.IGNORECASE,
)

_CURRENCY_ALIASES: tuple[tuple[str, str], ...] = (
    (r"so'm\w*|som|sum|сум\w*|сўм\w*|uzs", "UZS"),
    (r"\$|usd|dollar\w*|доллар\w*", "USD"),
    (r"€|eur|euro|евро", "EUR"),
    (r"₽|rub|rubl\w*|руб\w*", "RUB"),
)
_CURRENCY_AFTER = re.compile(
    r"\s*(?:" + "|".join(f"(?P<c{i}>{pattern})" for i, (pattern, _) in enumerate(_CURRENCY_ALIASES)) + r")(?![a-zа-яё])",
    re.IGNORECASE,
)
_CURRENCY_BEFORE = re.compile(r"(\$|€|₽|usd|eur|uzs|rub)\s?$", re.IGNORECASE)
_SIGN_BEFORE = re.compile(r"(?:(?:^|[\s:(])([-−–+])|([➖➕]))\s?$")


@dataclass(frozen=True)
class AmountMatch:
    amount: Decimal
    currency: str | None
    sign: str | None
    has_multiplier: bool
    start: int
    end: int


def normalize_currency(token: str) -> str | None:
    """«so‘m», «$», «usd» kabi yozuvlarni ISO kodga aylantiradi."""
    token = unify_apostrophes(token).strip()
    for pattern, code in _CURRENCY_ALIASES:
        if re.fullmatch(pattern, token, re.IGNORECASE):
            return code
    return None


def parse_number(raw: str) -> Decimal | None:
    """«25.000,00», «250 000.00», «1,234,567.89» kabi yozuvlardan sonni oladi."""
    digits = re.sub(rf"[{_THOUSAND_SPACES}']", "", raw.strip()).strip(".,")
    if not re.fullmatch(r"\d[\d.,]*", digits):
        return None
    has_dot, has_comma = "." in digits, "," in digits
    if has_dot and has_comma:
        decimal_sep = "." if digits.rfind(".") > digits.rfind(",") else ","
        thousand_sep = "," if decimal_sep == "." else "."
        digits = digits.replace(thousand_sep, "").replace(decimal_sep, ".")
    elif has_dot or has_comma:
        sep = "." if has_dot else ","
        if digits.count(sep) > 1:
            digits = digits.replace(sep, "")
        else:
            whole, fraction = digits.split(sep)
            looks_like_thousands = len(fraction) == 3 and len(whole) <= 3 and whole.strip("0") != ""
            digits = whole + fraction if looks_like_thousands else f"{whole}.{fraction}"
    try:
        return Decimal(digits)
    except InvalidOperation:
        return None


def find_amounts(text: str) -> list[AmountMatch]:
    """Matndagi barcha summalarni uchragan tartibida qaytaradi."""
    text = unify_apostrophes(text)
    results: list[AmountMatch] = []
    for match in _NUMBER.finditer(text):
        value = parse_number(match.group(0))
        if value is None:
            continue
        end = match.end()

        has_multiplier = False
        multiplier = _MULTIPLIER.match(text, end)
        if multiplier:
            for index, (_, factor) in enumerate(_MULTIPLIERS):
                if multiplier.group(f"m{index}"):
                    value *= factor
                    has_multiplier = True
                    end = multiplier.end()
                    break

        currency: str | None = None
        after = _CURRENCY_AFTER.match(text, end)
        if after:
            for index, (_, code) in enumerate(_CURRENCY_ALIASES):
                if after.group(f"c{index}"):
                    currency = code
                    end = after.end()
                    break

        prefix = text[: match.start()]
        before = _CURRENCY_BEFORE.search(prefix)
        if before:
            if currency is None:
                currency = normalize_currency(before.group(1))
            prefix = prefix[: before.start()]

        sign: str | None = None
        sign_match = _SIGN_BEFORE.search(prefix)
        if sign_match:
            symbol = sign_match.group(1) or sign_match.group(2)
            sign = "+" if symbol in "+➕" else "-"

        results.append(
            AmountMatch(
                amount=value,
                currency=currency,
                sign=sign,
                has_multiplier=has_multiplier,
                start=match.start(),
                end=end,
            )
        )
    return results


def parse_amount(text: str) -> Decimal | None:
    """Foydalanuvchi yozgan bitta summani o‘qiydi: «250 ming», «250 000», «1.5 mln»."""
    matches = find_amounts(text)
    return matches[0].amount if matches else None


def format_number(amount: Decimal) -> str:
    quantized = Decimal(amount).quantize(Decimal("0.01"))
    whole = int(abs(quantized))
    grouped = f"{whole:,}".replace(",", " ")
    cents = int((abs(quantized) - whole) * 100)
    return grouped if cents == 0 else f"{grouped}.{cents:02d}"


def format_amount(amount: Decimal, currency: str) -> str:
    """«250 000 UZS» ko‘rinishida chiqaradi."""
    return f"{format_number(amount)} {currency}"
