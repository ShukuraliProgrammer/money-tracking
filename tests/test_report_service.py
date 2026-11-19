from datetime import UTC, datetime
from decimal import Decimal

import pytest_asyncio

from app.schemas import NoteAnalysis
from app.services import report_service as rs
from app.services import transaction_service as ts
from app.utils.dates import period_range
from tests.conftest import TZ, category_named, make_parsed

NOW = datetime(2026, 11, 19, 15, 30, tzinfo=TZ)


def at(day: int, hour: int = 12, month: int = 11) -> datetime:
    return datetime(2026, month, day, hour, 0, tzinfo=TZ)


async def add(session, user, *, amount, kind="expense", when, merchant="KAMOLON", category=None, card=None,
              currency="UZS", note="izoh"):  # fmt: skip
    parsed = make_parsed(
        amount=Decimal(str(amount)), transaction_type=kind, occurred_at=when, merchant=merchant, currency=currency
    )
    return await ts.create_transaction(
        session, user, parsed, note, category.id if category else None, card.id if card else None, NoteAnalysis()
    )


@pytest_asyncio.fixture
async def seeded(session, user, other_user):
    uzcard = await ts.add_card(session, user.id, name="Asosiy Uzcard", last4="1234", network="Uzcard")
    humo = await ts.add_card(session, user.id, name="Humo ish", last4="5678", network="Humo")
    food = await category_named(session, user.id, "Ovqatlanish")
    shopping = await category_named(session, user.id, "Narsa sotib olish")
    salary = await category_named(session, user.id, "Maosh")

    await add(session, user, amount=250000, when=at(19), merchant="KAMOLON", category=food, card=uzcard)
    await add(session, user, amount=100000, when=at(18), merchant="KAMOLON", category=food, card=uzcard)
    await add(session, user, amount=900000, when=at(10), merchant="UZUM MARKET", category=shopping, card=humo)
    await add(session, user, amount=12000000, kind="income", when=at(5), merchant="ISH BERUVCHI", category=salary, card=humo)
    await add(session, user, amount=50000, when=at(3), merchant="YANDEX GO", card=None)
    await add(session, user, amount=40, when=at(7), merchant="AMAZON", category=shopping, card=None, currency="USD")
    # Oktabr (o'tgan oy)
    await add(session, user, amount=700000, when=at(15, month=10), merchant="KORZINKA", category=shopping, card=uzcard)
    # Boshqa foydalanuvchi
    await add(session, other_user, amount=999999, when=at(19), merchant="BEGONA")
    return {"uzcard": uzcard, "humo": humo, "food": food, "shopping": shopping, "salary": salary}


def november(card_id=None, category_id=None) -> rs.ReportFilter:
    period = period_range("m", TZ, NOW)
    return rs.ReportFilter(start=period.start, end=period.end, card_id=card_id, category_id=category_id)


def uzs(report: rs.Report) -> rs.CurrencyReport:
    return next(c for c in report.currencies if c.currency == "UZS")


async def test_month_totals_cover_all_cards(session, user, seeded):
    report = await rs.build_report(session, user.id, november())
    totals = uzs(report).totals
    assert totals.income == Decimal("12000000")
    assert totals.expense == Decimal("1300000")
    assert totals.net == Decimal("10700000")
    assert report.count == 6


async def test_other_users_and_other_months_are_excluded(session, user, seeded):
    report = await rs.build_report(session, user.id, november())
    merchants = {m.merchant for c in report.currencies for m in c.top_merchants}
    assert "BEGONA" not in merchants
    assert "KORZINKA" not in merchants


async def test_currencies_are_reported_separately_with_preferred_first(session, user, seeded):
    report = await rs.build_report(session, user.id, november(), preferred_currency="UZS")
    assert [c.currency for c in report.currencies] == ["UZS", "USD"]
    assert report.currencies[1].totals.expense == Decimal("40")


async def test_breakdown_by_card(session, user, seeded):
    by_card = {b.label: b.totals for b in uzs(await rs.build_report(session, user.id, november())).by_card}
    assert by_card["Asosiy Uzcard ****1234"].expense == Decimal("350000")
    assert by_card["Humo ish ****5678"].expense == Decimal("900000")
    assert by_card["Humo ish ****5678"].income == Decimal("12000000")
    assert by_card["Kartasiz"].expense == Decimal("50000")


async def test_breakdown_by_category_sorted_by_expense(session, user, seeded):
    by_category = uzs(await rs.build_report(session, user.id, november())).by_category
    assert [b.label for b in by_category] == ["🛍 Narsa sotib olish", "🍽 Ovqatlanish", "Tursiz", "💼 Maosh"]
    assert by_category[1].totals.expense == Decimal("350000")
    assert by_category[1].totals.count == 2


async def test_top_expenses_are_largest_first_and_exclude_income(session, user, seeded):
    top = uzs(await rs.build_report(session, user.id, november())).top_expenses
    assert [t.amount for t in top] == [Decimal("900000"), Decimal("250000"), Decimal("100000"), Decimal("50000")]


async def test_top_expenses_are_limited_to_five(session, user):
    for day in range(1, 9):
        await add(session, user, amount=day * 1000, when=at(day))
    top = uzs(await rs.build_report(session, user.id, november())).top_expenses
    assert len(top) == 5
    assert top[0].amount == Decimal("8000")


async def test_top_merchants_by_usage(session, user, seeded):
    top = uzs(await rs.build_report(session, user.id, november())).top_merchants
    assert (top[0].merchant, top[0].count, top[0].expense) == ("KAMOLON", 2, Decimal("350000"))


async def test_filter_by_card(session, user, seeded):
    report = await rs.build_report(session, user.id, november(card_id=seeded["uzcard"].id))
    assert uzs(report).totals.expense == Decimal("350000")
    assert uzs(report).totals.income == Decimal("0")
    assert report.count == 2


async def test_filter_by_category(session, user, seeded):
    report = await rs.build_report(session, user.id, november(category_id=seeded["shopping"].id))
    assert uzs(report).totals.expense == Decimal("900000")
    assert report.count == 2  # UZS + USD xarid


async def test_filter_by_card_and_category_together(session, user, seeded):
    report = await rs.build_report(
        session, user.id, november(card_id=seeded["humo"].id, category_id=seeded["salary"].id)
    )
    assert uzs(report).totals.income == Decimal("12000000")
    assert report.count == 1


async def test_empty_period_gives_empty_report(session, user):
    report = await rs.build_report(session, user.id, november())
    assert report.count == 0
    assert report.currencies == []


async def test_month_boundary_uses_user_timezone(session, user):
    # 31-oktabr 20:00 UTC = 1-noyabr 01:00 Toshkent vaqti bilan: noyabrga kiradi.
    await add(session, user, amount=1000, when=datetime(2026, 10, 31, 20, 0, tzinfo=UTC))
    # 31-oktabr 23:59 Toshkent: noyabrga kirmaydi.
    await add(session, user, amount=5000, when=datetime(2026, 10, 31, 23, 59, tzinfo=TZ))
    # 1-dekabr 00:00 Toshkent: noyabrga kirmaydi.
    await add(session, user, amount=7000, when=datetime(2026, 12, 1, 0, 0, tzinfo=TZ))
    report = await rs.build_report(session, user.id, november())
    assert uzs(report).totals.expense == Decimal("1000")


async def test_fetch_transactions_is_newest_first_and_paginated(session, user, seeded):
    page1 = await rs.fetch_transactions(session, user.id, november(), limit=4, offset=0)
    page2 = await rs.fetch_transactions(session, user.id, november(), limit=4, offset=4)
    assert [t.occurred_at.astimezone(TZ).day for t in page1] == [19, 18, 10, 7]
    assert [t.occurred_at.astimezone(TZ).day for t in page2] == [5, 3]
    assert page1[0].user_note == "izoh"
    assert page1[0].category.name == "Ovqatlanish"


async def test_count_transactions_respects_filter(session, user, seeded):
    assert await rs.count_transactions(session, user.id, november()) == 6
    assert await rs.count_transactions(session, user.id, november(card_id=seeded["uzcard"].id)) == 2


async def test_list_months_goes_back_to_first_transaction(session, user, seeded):
    assert await rs.list_months(session, user.id, TZ, NOW) == [(2026, 11), (2026, 10)]


async def test_list_months_for_new_user_is_current_month(session, user):
    assert await rs.list_months(session, user.id, TZ, NOW) == [(2026, 11)]


async def test_stats_cover_last_30_days_and_monthly_trend(session, user, seeded):
    stats = await rs.build_stats(session, user.id, TZ, NOW)
    assert uzs(stats.report).totals.expense == Decimal("1300000")  # 15-oktabr 30 kundan tashqarida
    assert [m.label for m in stats.trend] == [
        "Iyun 2026", "Iyul 2026", "Avgust 2026", "Sentabr 2026", "Oktabr 2026", "Noyabr 2026",
    ]  # fmt: skip
    assert stats.trend[-2].totals["UZS"].expense == Decimal("700000")
    assert stats.trend[-1].totals["UZS"].income == Decimal("12000000")
    assert stats.trend[0].totals == {}
