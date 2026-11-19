"""Log sozlamalari. Token, API kalit va karta raqamlari logga chiqmaydi."""

from __future__ import annotations

import logging
import re

from app.utils.validators import mask_card_numbers

_BOT_TOKEN = re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}")
_API_KEY = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}")


def redact(text: str) -> str:
    text = _BOT_TOKEN.sub("[TOKEN]", text)
    text = _API_KEY.sub("[KEY]", text)
    return mask_card_numbers(text)[0]


class RedactingFormatter(logging.Formatter):
    """Tayyor log satrini (xato izi bilan birga) maxfiy ma’lumotdan tozalaydi."""

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # HTTP mijozlari so‘rov manzillarini INFO darajasida yozadi; ular kerak emas.
    for noisy in ("httpx", "httpx2", "httpcore", "aiohttp.access", "anthropic", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
