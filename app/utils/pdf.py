"""PDF chekdan matn olish."""

from __future__ import annotations

import io

from pypdf import PdfReader

MAX_PAGES = 3


class PdfError(Exception):
    """Fayl PDF emas, buzilgan yoki parol bilan himoyalangan."""


def extract_pdf_text(data: bytes, max_pages: int = MAX_PAGES) -> str:
    """Birinchi sahifalardagi matnni qatorma-qator qaytaradi. Matn qatlami bo‘lmasa — bo‘sh satr."""
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise PdfError("PDF is password protected")
        raw = "\n".join(page.extract_text() or "" for page in reader.pages[:max_pages])
    except PdfError:
        raise
    except Exception as error:  # noqa: BLE001 - begona faylni o‘qishda kutubxona turli xato berishi mumkin
        raise PdfError(type(error).__name__) from error
    lines = (" ".join(line.split()) for line in raw.splitlines())
    return "\n".join(line for line in lines if line)
