"""Yuborilgan rasmni LLM qabul qiladigan formatga keltirish."""

from __future__ import annotations

import io
from pathlib import PurePath

from PIL import Image, UnidentifiedImageError

# Anthropic va OpenAI to‘g‘ridan-to‘g‘ri qabul qiladigan formatlar.
SUPPORTED_TYPES = frozenset({"image/jpeg", "image/png", "image/gif", "image/webp"})

_TYPE_BY_EXTENSION = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".heic": "image/heic",
    ".heif": "image/heif",
}


def guess_image_type(mime_type: str | None, file_name: str | None) -> str | None:
    """Fayl rasm bo‘lsa, uning turini qaytaradi. Telegram turni bermasa, fayl nomiga qaraladi."""
    if mime_type:
        return mime_type if mime_type.startswith("image/") else None
    if file_name:
        return _TYPE_BY_EXTENSION.get(PurePath(file_name).suffix.lower())
    return None


def to_supported_image(data: bytes, media_type: str | None) -> tuple[bytes, str] | None:
    """Qo‘llab-quvvatlanadigan format bo‘lsa o‘zini, bo‘lmasa JPEG’ga o‘girilganini qaytaradi.

    Faylni rasm sifatida ochib bo‘lmasa (masalan, HEIC), ``None``.
    """
    if media_type in SUPPORTED_TYPES:
        return data, media_type
    try:
        with Image.open(io.BytesIO(data)) as image:
            buffer = io.BytesIO()
            image.convert("RGB").save(buffer, format="JPEG", quality=90)
    except (UnidentifiedImageError, OSError, ValueError):
        return None
    return buffer.getvalue(), "image/jpeg"
