"""Hisobot va statistika.

Yig‘indilar Python’da hisoblanadi: shaxsiy bot uchun ma’lumot hajmi kichik,
va oy chegaralari foydalanuvchining vaqt zonasi bo‘yicha to‘g‘ri chiqadi.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Transaction
from app.utils.dates import month_label, period_range, previous_month

NO_CARD_LABEL = "Kartasiz"
NO_CATEGORY_LABEL = "Tursiz"
TOP_LIMIT = 5
TREND_MONTHS = 6


@dataclass(frozen=True)
class ReportFilter:
    start: datetime | None
    end: datetime
    card_id: int | None = None
    category_id: int | None = None


@dataclass
class Totals:
    income: Decimal = Decimal(0)
    expense: Decimal = Decimal(0)
    count: int = 0

    @property
    def net(self) -> Decimal:
        return self.income - self.expense

    def add(self, transaction: Transaction) -> None:
        if transaction.transaction_type == "income":
            self.income += transaction.amount
        else:
            self.expense += transaction.amount
        self.count += 1


@dataclass
class Breakdown:
    label: str
    totals: Totals


@dataclass
class MerchantStat:
    merchant: str
    count: int
    expense: Decimal


@dataclass
class CurrencyReport:
    currency: str
    totals: Totals = field(default_factory=Totals)
    by_category: list[Breakdown] = field(default_factory=list)
    by_card: list[Breakdown] = field(default_factory=list)
    top_expenses: list[Transaction] = field(default_factory=list)
    top_merchants: list[MerchantStat] = field(default_factory=list)


@dataclass
class Report:
    count: int
    currencies: list[CurrencyReport]


@dataclass
class MonthTrend:
    label: str
    totals: dict[str, Totals]


@dataclass
class Stats:
    report: Report
    trend: list[MonthTrend]


def card_label(transaction: Transaction) -> str:
    card = transaction.card
    return f"{card.name} ****{card.card_last4}" if card else NO_CARD_LABEL


def category_label(transaction: Transaction) -> str:
    category = transaction.category
    return f"{category.emoji} {category.name}" if category else NO_CATEGORY_LABEL


def _filtered(query: Select, user_id: int, flt: ReportFilter) -> Select:
    query = query.where(Transaction.user_id == user_id, Transaction.occurred_at < flt.end)
    if flt.start is not None:
        query = query.where(Transaction.occurred_at >= flt.start)
    if flt.card_id is not None:
        query = query.where(Transaction.card_id == flt.card_id)
    if flt.category_id is not None:
        query = query.where(Transaction.category_id == flt.category_id)
    return query


async def fetch_transactions(
    session: AsyncSession, user_id: int, flt: ReportFilter, limit: int | None = None, offset: int = 0
) -> list[Transaction]:
    """Filtrga mos tranzaksiyalar, eng yangisi birinchi."""
    query = _filtered(select(Transaction), user_id, flt).order_by(
        Transaction.occurred_at.desc(), Transaction.id.desc()
    )
    if limit is not None:
        query = query.limit(limit).offset(offset)
    return list(await session.scalars(query))


async def count_transactions(session: AsyncSession, user_id: int, flt: ReportFilter) -> int:
    query = _filtered(select(func.count()).select_from(Transaction), user_id, flt)
    return await session.scalar(query) or 0


def summarize(transactions: list[Transaction], preferred_currency: str = "UZS") -> Report:
    grouped: dict[str, list[Transaction]] = defaultdict(list)
    for transaction in transactions:
        grouped[transaction.currency].append(transaction)

    reports: list[CurrencyReport] = []
    for currency in sorted(grouped, key=lambda code: (code != preferred_currency, code)):
        items = grouped[currency]
        report = CurrencyReport(currency=currency)
        categories: dict[str, Totals] = defaultdict(Totals)
        cards: dict[str, Totals] = defaultdict(Totals)
        merchants: dict[str, MerchantStat] = {}

        for transaction in items:
            report.totals.add(transaction)
            categories[category_label(transaction)].add(transaction)
            cards[card_label(transaction)].add(transaction)
            if transaction.transaction_type == "expense" and transaction.merchant:
                stat = merchants.setdefault(transaction.merchant, MerchantStat(transaction.merchant, 0, Decimal(0)))
                stat.count += 1
                stat.expense += transaction.amount

        report.by_category = sorted(
            (Breakdown(label, totals) for label, totals in categories.items()),
            key=lambda item: (-item.totals.expense, -item.totals.income, item.label),
        )
        report.by_card = sorted(
            (Breakdown(label, totals) for label, totals in cards.items()),
            key=lambda item: (-(item.totals.expense + item.totals.income), item.label),
        )
        report.top_expenses = sorted(
            (t for t in items if t.transaction_type == "expense"), key=lambda t: (-t.amount, -t.id)
        )[:TOP_LIMIT]
        report.top_merchants = sorted(merchants.values(), key=lambda s: (-s.count, -s.expense, s.merchant))[:TOP_LIMIT]
        reports.append(report)

    return Report(count=len(transactions), currencies=reports)


async def build_report(
    session: AsyncSession, user_id: int, flt: ReportFilter, preferred_currency: str = "UZS"
) -> Report:
    return summarize(await fetch_transactions(session, user_id, flt), preferred_currency)


async def list_months(
    session: AsyncSession, user_id: int, tz: ZoneInfo, now: datetime, limit: int = 12
) -> list[tuple[int, int]]:
    """Joriy oydan boshlab birinchi tranzaksiya oyigacha (eng yangisi birinchi)."""
    now = now.astimezone(tz)
    earliest = await session.scalar(select(func.min(Transaction.occurred_at)).where(Transaction.user_id == user_id))
    first = (now.year, now.month)
    if earliest is not None:
        local = earliest.astimezone(tz)
        first = min(first, (local.year, local.month))

    months: list[tuple[int, int]] = []
    current = (now.year, now.month)
    while current >= first and len(months) < limit:
        months.append(current)
        current = previous_month(*current)
    return months


async def build_stats(
    session: AsyncSession, user_id: int, tz: ZoneInfo, now: datetime, preferred_currency: str = "UZS"
) -> Stats:
    """Oxirgi 30 kun bo‘yicha hisobot va oxirgi 6 oylik trend."""
    now = now.astimezone(tz)
    last_30 = period_range("30", tz, now)

    months: list[tuple[int, int]] = [(now.year, now.month)]
    while len(months) < TREND_MONTHS:
        months.append(previous_month(*months[-1]))
    months.reverse()
    trend_start = period_range(f"{months[0][0]:04d}-{months[0][1]:02d}", tz, now).start

    transactions = await fetch_transactions(session, user_id, ReportFilter(start=trend_start, end=last_30.end))

    by_month: dict[tuple[int, int], dict[str, Totals]] = {month: {} for month in months}
    for transaction in transactions:
        local = transaction.occurred_at.astimezone(tz)
        bucket = by_month.get((local.year, local.month))
        if bucket is not None:
            bucket.setdefault(transaction.currency, Totals()).add(transaction)

    recent = [t for t in transactions if t.occurred_at >= last_30.start]
    return Stats(
        report=summarize(recent, preferred_currency),
        trend=[MonthTrend(label=month_label(*month), totals=by_month[month]) for month in months],
    )
