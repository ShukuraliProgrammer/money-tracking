"""Kiruvchi matnni tozalash va tekshirish: karta raqamini yashirish, maxfiy kodlarni aniqlash."""

from __future__ import annotations

import re
from dataclasses import dataclass

_APOSTROPHES = str.maketrans({"‘": "'", "’": "'", "ʻ": "'", "ʼ": "'", "`": "'", "´": "'"})


def unify_apostrophes(text: str) -> str:
    """O‘zbekcha tutuq belgilarini bitta ko‘rinishga keltiradi (uzunlik o‘zgarmaydi)."""
    return text.translate(_APOSTROPHES)


def normalize_text(text: str) -> str:
    return unify_apostrophes(text).lower()


@dataclass(frozen=True)
class CardHint:
    last4: str
    network: str


def detect_network_from_pan(prefix: str) -> str:
    """Karta raqamining boshidagi raqamlar (BIN) bo‘yicha to‘lov tizimini aniqlaydi."""
    if prefix.startswith(("8600", "5614", "6262")):
        return "Uzcard"
    if prefix.startswith("9860"):
        return "Humo"
    if prefix.startswith("4"):
        return "Visa"
    if len(prefix) >= 2 and prefix[:2].isdigit() and 51 <= int(prefix[:2]) <= 55:
        return "Mastercard"
    if len(prefix) >= 4 and prefix[:4].isdigit() and 2221 <= int(prefix[:4]) <= 2720:
        return "Mastercard"
    return "Unknown"


_FULL_PAN = re.compile(
    r"(?<![\d*•])(?:\d{4}([ -]?)\d{4}\1\d{4}\1\d{4}(?:\1\d{1,3})?|\d{13,19})(?!\d)"
)
_PARTIAL_PAN = re.compile(r"(?<!\d)(\d{4}(?:\s?\d{2})?)\s?[*•xX][*•xX\s]*(\d{4})(?!\d)")
_SHORT_MASK = re.compile(r"(?:[*•]+|[xX]{2,})[ ]?(\d{4})(?!\d)")


def mask_card_numbers(text: str) -> tuple[str, list[CardHint]]:
    """Karta raqamlarini ``****1234`` ko‘rinishiga keltiradi.

    To‘liq raqam hech qayerda saqlanmasligi uchun bu funksiya matn bazaga,
    logga yoki LLM’ga ketishidan oldin chaqiriladi.
    """
    hints: dict[str, CardHint] = {}

    def remember(last4: str, network: str) -> None:
        known = hints.get(last4)
        if known is None or known.network == "Unknown":
            hints[last4] = CardHint(last4=last4, network=network)

    def replace_full(match: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", match.group(0))
        remember(digits[-4:], detect_network_from_pan(digits))
        return f"****{digits[-4:]}"

    def replace_partial(match: re.Match[str]) -> str:
        prefix = re.sub(r"\D", "", match.group(1))
        remember(match.group(2), detect_network_from_pan(prefix))
        return f"****{match.group(2)}"

    def replace_short(match: re.Match[str]) -> str:
        remember(match.group(1), "Unknown")
        return f"****{match.group(1)}"

    text = _FULL_PAN.sub(replace_full, text)
    text = _PARTIAL_PAN.sub(replace_partial, text)
    text = _SHORT_MASK.sub(replace_short, text)
    return text, list(hints.values())


_STRONG_SECRET = re.compile(
    r"tasdiqlash\s+kodi|kod\w*\s+podtverzhd|код\w*\s+подтвержд|sms[- ]?kod|смс[- ]?код"
    r"|одноразов|bir\s+martalik|\botp\b|\bcvv2?\b|\bcvc2?\b|\bpin\b|pin[- ]?kod|пин[- ]?код"
    r"|\bparol|пароль|\bpassword",
    re.IGNORECASE,
)
_GENERIC_CODE = re.compile(r"\b(?:kod|code|код)\w*\W{0,3}\d{4,8}\b", re.IGNORECASE)
_DO_NOT_SHARE = re.compile(
    r"nikomu\s+ne\s+soobsh|никому\s+не\s+сообщ|hech\s+kimga\s+(?:aytmang|bermang)"
    r"|do\s?n[o']t\s+share",
    re.IGNORECASE,
)


def contains_secret_code(text: str) -> bool:
    """SMS kod, CVV, PIN yoki parolga o‘xshash xabarni aniqlaydi."""
    text = unify_apostrophes(text)
    if _STRONG_SECRET.search(text):
        return True
    return bool(_GENERIC_CODE.search(text) and _DO_NOT_SHARE.search(text))


_TRAILING_NOISE = {"uz", "uzb", "tashkent", "toshkent"}


def normalize_merchant(name: str) -> str:
    """Merchant nomini qoidalar jadvalida solishtirish uchun soddalashtiradi."""
    cleaned = re.sub(r"[^\w']+|_", " ", normalize_text(name))
    tokens = [token for token in cleaned.split() if not token.isdigit()]
    while len(tokens) > 1 and tokens[-1] in _TRAILING_NOISE:
        tokens.pop()
    return " ".join(tokens)


def is_valid_last4(value: str) -> bool:
    return bool(re.fullmatch(r"\d{4}", value))


def contains_full_card_number(text: str) -> bool:
    """Matnda to‘liq (yashirilmagan) karta raqami bormi."""
    return bool(_FULL_PAN.search(text))


_LEADING_EMOJI = re.compile(r"^([^\w\s'\"]{1,8})\s*(.+)$", re.DOTALL)


def split_emoji(name: str, default: str = "🏷") -> tuple[str, str]:
    """«🚕 Transport» → («🚕», «Transport»). Emoji bo‘lmasa standart belgi qo‘yiladi."""
    name = name.strip()
    match = _LEADING_EMOJI.match(name)
    if match and not match.group(1).isascii():
        return match.group(1), match.group(2).strip()
    return default, name
