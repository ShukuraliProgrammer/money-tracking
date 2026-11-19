"""O‘z kartalar orasidagi o‘tkazmani tanish.

Karta xabarida pul kimning kartasiga ketgani yozilmaydi, shuning uchun bitta
xabardan buni bilib bo‘lmaydi. Lekin ikkala tomon ham kelsa (bir kartadan chiqim,
boshqasiga deyarli shu summada kirim, orasi bir necha daqiqa), bu juftlik.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Transaction
from app.schemas import ParsedTransaction, TransferReceipt

TRANSFER_WINDOW = timedelta(minutes=10)
# Jo‘natuvchi kartadan ushlanadigan komissiya uchun ruxsat etilgan farq.
MAX_FEE_SHARE = Decimal("0.02")


@dataclass(frozen=True)
class Leg:
    """O‘tkazmaning bir tomoni."""

    transaction_type: str | None
    amount: Decimal | None
    currency: str
    occurred_at: datetime | None
    card_last4: str | None

    @classmethod
    def from_parsed(cls, parsed: ParsedTransaction) -> Leg:
        return cls(parsed.transaction_type, parsed.amount, parsed.currency, parsed.occurred_at, parsed.card_last4)

    @classmethod
    def from_transaction(cls, transaction: Transaction) -> Leg:
        return cls(
            transaction.transaction_type,
            transaction.amount,
            transaction.currency,
            transaction.occurred_at,
            transaction.card.card_last4 if transaction.card else None,
        )


def split_pair(first: Leg, second: Leg) -> tuple[Leg, Leg]:
    """(chiqim tomoni, kirim tomoni)."""
    return (first, second) if first.transaction_type == "expense" else (second, first)


def is_transfer_pair(first: Leg, second: Leg) -> bool:
    if None in (first.amount, second.amount, first.occurred_at, second.occurred_at):
        return False
    if {first.transaction_type, second.transaction_type} != {"expense", "income"}:
        return False
    if first.currency != second.currency:
        return False
    if abs(first.occurred_at - second.occurred_at) > TRANSFER_WINDOW:
        return False
    if first.card_last4 and second.card_last4 and first.card_last4 == second.card_last4:
        return False
    sent, received = split_pair(first, second)
    return received.amount <= sent.amount <= received.amount * (1 + MAX_FEE_SHARE)


async def find_transfer_counterpart(
    session: AsyncSession, user_id: int, parsed: ParsedTransaction
) -> Transaction | None:
    """Yangi xabarning ikkinchi tomoni avval saqlanganmi. Faqat shu foydalanuvchining yozuvlari qaraladi."""
    incoming = Leg.from_parsed(parsed)
    if incoming.amount is None or incoming.occurred_at is None or incoming.transaction_type is None:
        return None
    opposite = "income" if incoming.transaction_type == "expense" else "expense"
    candidates = await session.scalars(
        select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.transaction_type == opposite,
            Transaction.currency == incoming.currency,
            Transaction.occurred_at >= incoming.occurred_at - TRANSFER_WINDOW,
            Transaction.occurred_at <= incoming.occurred_at + TRANSFER_WINDOW,
        )
    )
    matches = [item for item in candidates if is_transfer_pair(incoming, Leg.from_transaction(item))]
    return min(matches, key=lambda item: abs(item.occurred_at - incoming.occurred_at), default=None)


def _same_amount(first: Decimal, second: Decimal) -> bool:
    low, high = sorted((first, second))
    return high <= low * (1 + MAX_FEE_SHARE)


async def find_saved_receipt_legs(
    session: AsyncSession, user_id: int, parsed: ParsedTransaction
) -> list[Transaction]:
    """O‘tkazma chekiga tegishli, avval saqlangan tomonlar (masalan, shu o‘tkazmaning karta xabari)."""
    receipt: TransferReceipt | None = parsed.transfer
    if receipt is None or parsed.occurred_at is None:
        return []
    candidates = await session.scalars(
        select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.currency == parsed.currency,
            Transaction.occurred_at >= parsed.occurred_at - TRANSFER_WINDOW,
            Transaction.occurred_at <= parsed.occurred_at + TRANSFER_WINDOW,
        )
    )
    legs = []
    for item in candidates:
        last4 = item.card.card_last4 if item.card else None
        if last4 is None:
            continue
        is_received = item.transaction_type == "income" and last4 == receipt.receiver_last4
        is_sent = item.transaction_type == "expense" and last4 == receipt.sender_last4
        expected = receipt.receiver_amount if is_received else receipt.sender_amount
        if (is_received or is_sent) and _same_amount(item.amount, expected):
            legs.append(item)
    return legs
