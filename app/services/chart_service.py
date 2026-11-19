"""Avtomatik hisobot uchun rasm (PNG) chizish.

Rasmda: davr, kirim/chiqim/farq va turlar bo‘yicha chiqim ustunlari (kattasi
birinchi, bitta rangda). Aniq ro‘yxat va boshqa valyutalar matnli hisobotda.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.services.report_service import CurrencyReport
from app.utils.money import format_amount, format_number
from app.utils.validators import split_emoji

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

# O‘lchamlar 2x zichlikda (telefon ekranida aniq ko‘rinishi uchun).
IMAGE_WIDTH = 1080
PADDING = 72
BAR_HEIGHT = 28
BAR_RADIUS = 8
MIN_BAR = 4
MAX_ROWS = 8

SURFACE = (252, 252, 251)
INK = (11, 11, 11)
INK_SECONDARY = (82, 81, 78)
INK_MUTED = (137, 135, 129)
HAIRLINE = (230, 229, 225)
BAR_COLOR = (42, 120, 214)

BRAND = "MoneyTrack UZ"
REST_LABEL = "Qolganlari"
NO_EXPENSES = "Bu davrda chiqim yo‘q."


@dataclass(frozen=True)
class ChartRow:
    label: str
    amount: Decimal


@lru_cache
def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "Inter-SemiBold.otf" if bold else "Inter-Regular.otf"
    return ImageFont.truetype(str(FONT_DIR / name), size)


def _printable(text: str) -> str:
    """Shriftda yo‘q belgilarni (emoji va h.k.) olib tashlaydi."""
    kept = [
        char
        for char in text
        if not (ord(char) >= 0x1F000 or 0x2600 <= ord(char) <= 0x27BF or 0xFE00 <= ord(char) <= 0xFE0F or ord(char) == 0x200D)
    ]
    return " ".join("".join(kept).split())


def top_rows(report: CurrencyReport, limit: int = MAX_ROWS) -> list[ChartRow]:
    """Chiqimi bor turlar, kattasi birinchi. Ortiqchasi bitta «Qolganlari» qatoriga yig‘iladi."""
    rows = [
        ChartRow(label=_printable(split_emoji(item.label)[1]) or item.label, amount=item.totals.expense)
        for item in report.by_category
        if item.totals.expense > 0
    ]
    rows.sort(key=lambda row: -row.amount)
    if len(rows) <= limit:
        return rows
    head, tail = rows[: limit - 1], rows[limit - 1 :]
    return [*head, ChartRow(label=REST_LABEL, amount=sum((row.amount for row in tail), Decimal(0)))]


def bar_lengths(amounts: list[Decimal], max_length: int) -> list[int]:
    """Ustun uzunliklari: eng kattasi to‘liq, qolganlari unga nisbatan."""
    largest = max(amounts, default=Decimal(0))
    if largest <= 0:
        return [0 for _ in amounts]
    return [max(MIN_BAR, round(float(amount / largest) * max_length)) if amount > 0 else 0 for amount in amounts]


def _fit(text: str, font: ImageFont.FreeTypeFont, max_width: float) -> str:
    """Matn sig‘masa, oxirini «…» bilan qisqartiradi."""
    if font.getlength(text) <= max_width:
        return text
    while text and font.getlength(text + "…") > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def render_report_image(
    heading: str,
    period_label: str,
    report: CurrencyReport,
    other_currencies: list[str] | None = None,
) -> bytes:
    """Bitta valyuta bo‘yicha hisobot rasmini PNG bayt ko‘rinishida qaytaradi."""
    left, right = PADDING, IMAGE_WIDTH - PADDING
    content_width = right - left
    image = Image.new("RGB", (IMAGE_WIDTH, 4000), SURFACE)
    draw = ImageDraw.Draw(image)
    currency, totals = report.currency, report.totals
    y = PADDING

    # Sarlavha
    draw.text((left, y), BRAND, font=_font(26), fill=INK_MUTED)
    y += 50
    draw.text((left, y), _fit(_printable(heading), _font(52, True), content_width), font=_font(52, True), fill=INK)
    y += 76
    draw.text((left, y), _fit(_printable(period_label), _font(32), content_width), font=_font(32), fill=INK_SECONDARY)
    y += 76
    draw.line((left, y, right, y), fill=HAIRLINE, width=2)
    y += 36

    # Kirim, chiqim, farq
    for label, value in (
        ("Kirim", format_amount(totals.income, currency)),
        ("Chiqim", format_amount(totals.expense, currency)),
    ):
        draw.text((left, y), label, font=_font(34), fill=INK_SECONDARY)
        draw.text((right, y), value, font=_font(38, True), fill=INK, anchor="ra")
        y += 66
    y += 6
    draw.line((left, y, right, y), fill=HAIRLINE, width=2)
    y += 30
    net = totals.net
    net_text = f"{'+' if net >= 0 else '−'}{format_number(abs(net))} {currency}"
    draw.text((left, y + 8), "Farq", font=_font(34, True), fill=INK)
    draw.text((right, y), net_text, font=_font(48, True), fill=INK, anchor="ra")
    y += 108

    # Turlar bo‘yicha chiqim
    draw.text((left, y), f"Turlar bo‘yicha chiqim, {currency}", font=_font(30, True), fill=INK_SECONDARY)
    y += 68
    rows = top_rows(report)
    if not rows:
        draw.text((left, y), NO_EXPENSES, font=_font(32), fill=INK_MUTED)
        y += 60
    lengths = bar_lengths([row.amount for row in rows], content_width)
    for row, length in zip(rows, lengths, strict=True):
        value = format_number(row.amount)
        value_width = _font(32, True).getlength(value)
        draw.text((right, y), value, font=_font(32, True), fill=INK, anchor="ra")
        draw.text((left, y), _fit(row.label, _font(32), content_width - value_width - 40), font=_font(32), fill=INK)
        y += 52
        box = (left, y, left + length - 1, y + BAR_HEIGHT - 1)
        if length >= 2 * BAR_RADIUS:
            # Ustunning boshi tekis, uchi yumaloq.
            draw.rounded_rectangle(box, radius=BAR_RADIUS, fill=BAR_COLOR, corners=(False, True, True, False))
        else:
            draw.rectangle(box, fill=BAR_COLOR)
        y += BAR_HEIGHT + 40

    if other_currencies:
        note = f"Boshqa valyutalar ({', '.join(other_currencies)}) matnli hisobotda."
        draw.text((left, y), _fit(note, _font(26), content_width), font=_font(26), fill=INK_MUTED)
        y += 50

    image = image.crop((0, 0, IMAGE_WIDTH, y + PADDING - 30))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
