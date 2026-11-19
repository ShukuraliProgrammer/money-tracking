"""O‘tkazma cheklarini (PDF kvitansiya) o‘qish.

Bank cheklarida ma’lumot «sarlavha — qiymat» juftliklari ko‘rinishida bo‘ladi. PDF’dan matn
olinganda ular ikki xil chiqadi:

1. ustun bo‘lib: avval barcha sarlavhalar, keyin shu tartibda barcha qiymatlar (Uzum Bank);
2. qatorma-qator: «Sender 986017******9298».

Chekda jo‘natuvchi va qabul qiluvchi kartasi ham bo‘lgani uchun pul qaysi tomonga ketgani
(kirim, chiqim yoki o‘z kartalar orasidagi o‘tkazma) foydalanuvchining kartalariga qarab aniqlanadi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.schemas import TransferReceipt
from app.utils.dates import find_datetime
from app.utils.money import find_amounts
from app.utils.validators import mask_card_numbers, normalize_text

_FLAGS = re.IGNORECASE
_SENDER = re.compile(r"sender|отправител|jo'natuvchi|yuboruvchi", _FLAGS)
_RECEIVER = re.compile(r"receiver|recipient|получател|qabul\s+qiluvchi|oluvchi", _FLAGS)
_NAME = re.compile(r"\bname\b|имя|\bism", _FLAGS)
_FEE = re.compile(r"\bfee\b|commission|комисси|komissiya", _FLAGS)
_AMOUNT = re.compile(r"amount|сумма|summa", _FLAGS)
_DATE = re.compile(r"\bdate\b|дата|\bsana", _FLAGS)

# Qatorma-qator ko‘rinishda sarlavha va qiymat orasida ikki nuqta bo‘lmasligi mumkin,
# shuning uchun ma’lum sarlavhalar ro‘yxati kerak (uzunrog‘i birinchi).
_KNOWN_LABELS = (
    "sender name", "sender amount", "sender fee", "sender",
    "receiver name", "receiver amount", "receiver fee", "receiver",
    "recipient name", "recipient",
    "transaction date", "transaction id", "received date", "amount", "commission", "fee",
    "имя отправителя", "сумма отправителя", "комиссия отправителя", "отправитель",
    "имя получателя", "сумма получателя", "комиссия получателя", "получатель",
    "дата транзакции", "сумма", "комиссия",
)  # fmt: skip
_INLINE_KNOWN = re.compile(
    r"^(" + "|".join(re.escape(label) for label in _KNOWN_LABELS) + r")\s*[:\-]?\s+(\S.*)$", _FLAGS
)
_INLINE_COLON = re.compile(r"^([^:\d]{2,40}):\s*(\S.*)$")
_HAS_DIGIT = re.compile(r"\d")


@dataclass(frozen=True)
class Receipt:
    transfer: TransferReceipt
    currency: str
    occurred_at: datetime | None


def _column_pairs(lines: list[str]) -> list[tuple[str, str]] | None:
    """Birinchi yarmi sarlavhalar (raqamsiz), ikkinchi yarmi qiymatlar bo‘lgan matn."""
    half = len(lines) // 2
    if len(lines) < 6 or len(lines) % 2:
        return None
    labels, values = lines[:half], lines[half:]
    if any(_HAS_DIGIT.search(label) for label in labels):
        return None
    if sum(bool(_HAS_DIGIT.search(value)) for value in values) * 2 < len(values):
        return None
    return list(zip(labels, values, strict=True))


def label_value_pairs(text: str) -> list[tuple[str, str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    columns = _column_pairs(lines)
    if columns is not None:
        return columns
    pairs = []
    for line in lines:
        # Ikki nuqta bo‘lsa, sarlavha undan oldingi butun matn («Сумма комиссии: …»); ma’lum sarlavhalar
        # ro‘yxati faqat ikki nuqtasiz qatorlar uchun.
        match = _INLINE_COLON.match(line) or _INLINE_KNOWN.match(line)
        if match:
            pairs.append((match.group(1).strip(), match.group(2).strip()))
    return pairs


def classify(label: str) -> str | None:
    """Sarlavhaning ma’nosi: sender, receiver_name, sender_amount, receiver_fee, amount, fee, date ..."""
    text = normalize_text(label)
    sender, receiver = bool(_SENDER.search(text)), bool(_RECEIVER.search(text))
    side = "sender" if sender and not receiver else "receiver" if receiver and not sender else None
    if _FEE.search(text):
        return f"{side}_fee" if side else "fee"
    if _AMOUNT.search(text):
        return f"{side}_amount" if side else "amount"
    if _NAME.search(text):
        return f"{side}_name" if side else None
    if _DATE.search(text):
        return "date"
    return side


def _amount(value: str | None) -> tuple[Decimal | None, str | None]:
    matches = find_amounts(value) if value else []
    return (matches[0].amount, matches[0].currency) if matches else (None, None)


def _card(value: str | None) -> tuple[str | None, str]:
    hints = mask_card_numbers(value)[1] if value else []
    return (hints[0].last4, hints[0].network) if hints else (None, "Unknown")


def extract_transfer_receipt(text: str, tz: ZoneInfo) -> Receipt | None:
    """Matn o‘tkazma cheki bo‘lsa, uning maydonlarini qaytaradi; bo‘lmasa ``None``."""
    fields: dict[str, str] = {}
    for label, value in label_value_pairs(text):
        key = classify(label)
        if key and key not in fields:
            fields[key] = value

    sender_last4, sender_network = _card(fields.get("sender"))
    receiver_last4, receiver_network = _card(fields.get("receiver"))
    if sender_last4 is None and receiver_last4 is None:
        return None

    generic, generic_currency = _amount(fields.get("amount"))
    sender_amount, sender_currency = _amount(fields.get("sender_amount"))
    receiver_amount, receiver_currency = _amount(fields.get("receiver_amount"))
    sender_amount = sender_amount or generic or receiver_amount
    receiver_amount = receiver_amount or generic or sender_amount
    if not sender_amount or not receiver_amount:
        return None

    date = find_datetime(fields.get("date", ""), tz)
    return Receipt(
        transfer=TransferReceipt(
            sender_last4=sender_last4,
            sender_network=sender_network,
            sender_name=fields.get("sender_name"),
            sender_amount=sender_amount,
            receiver_last4=receiver_last4,
            receiver_network=receiver_network,
            receiver_name=fields.get("receiver_name"),
            receiver_amount=receiver_amount,
        ),
        currency=sender_currency or receiver_currency or generic_currency or "UZS",
        occurred_at=date.value if date else None,
    )
