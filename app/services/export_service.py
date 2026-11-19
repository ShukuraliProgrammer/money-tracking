"""Tranzaksiyalarni CSV faylga chiqarish."""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.models import Transaction

CSV_COLUMNS = ("date", "type", "amount", "currency", "merchant", "category", "user_note", "card_last4", "source")

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _safe(value: str | None) -> str:
    """Excel/Sheets formulasi sifatida bajarilmasligi uchun xavfli boshlanishlarni zararsizlantiradi."""
    if not value:
        return ""
    return f"'{value}" if value.startswith(_FORMULA_PREFIXES) else value


def _plain_amount(amount: Decimal) -> str:
    quantized = Decimal(amount).quantize(Decimal("0.01"))
    return str(quantized.to_integral_value()) if quantized == quantized.to_integral_value() else str(quantized)


def build_csv(transactions: list[Transaction], tz: ZoneInfo) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for transaction in transactions:
        writer.writerow(
            [
                transaction.occurred_at.astimezone(tz).strftime("%Y-%m-%d %H:%M"),
                transaction.transaction_type,
                _plain_amount(transaction.amount),
                transaction.currency,
                _safe(transaction.merchant),
                _safe(transaction.category.name if transaction.category else None),
                _safe(transaction.user_note),
                transaction.card.card_last4 if transaction.card else "",
                transaction.source,
            ]
        )
    return buffer.getvalue().encode("utf-8-sig")


def export_filename(period_label: str, now: datetime) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", period_label.lower()).strip("_") or "hisobot"
    return f"moneytrack_{slug}_{now:%Y%m%d}.csv"
