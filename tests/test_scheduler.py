"""Avtomatik hisobotlar: har dushanba (o'tgan hafta) va har oyning 1-kuni (o'tgan oy), rasm + matn."""

from datetime import datetime
from decimal import Decimal

import pytest
from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import SendMessage, SendPhoto
from sqlalchemy import select

from app.bot import scheduler
from app.bot.scheduler import send_due_reports
from app.models import User
from app.schemas import NoteAnalysis
from app.services import transaction_service as ts
from tests.bot_harness import BotHarness
from tests.conftest import TZ, make_parsed

# 2026-yil 1-noyabr yakshanba, 2-noyabr dushanba.
FIRST_MORNING = datetime(2026, 11, 1, 9, 30, tzinfo=TZ)
MONDAY_MORNING = datetime(2026, 11, 16, 9, 30, tzinfo=TZ)  # o'tgan hafta: 09–15 noyabr


@pytest.fixture
def harness(session_factory):
    return BotHarness(session_factory, FIRST_MORNING)


async def spend(session_factory, when: datetime, amount="700000", telegram_id=1001, currency="UZS", **user_fields):
    async with session_factory() as session:
        user = await ts.get_or_create_user(session, telegram_id, "ali", "Ali")
        if user_fields:
            await ts.update_user(session, user, **user_fields)
        parsed = make_parsed(amount=Decimal(amount), occurred_at=when, currency=currency)
        await ts.create_transaction(session, user, parsed, "Xarid", None, None, NoteAnalysis())


async def october_spender(session_factory, telegram_id=1001, **user_fields) -> None:
    # Haftalik hisobot bu testlarga aralashmasligi uchun standart holatda o'chiriladi.
    fields = {"weekly_report_enabled": False} | user_fields
    await spend(session_factory, datetime(2026, 10, 15, 12, 0, tzinfo=TZ), telegram_id=telegram_id, **fields)


async def last_week_spender(session_factory, **user_fields) -> None:
    fields = {"notifications_enabled": False} | user_fields
    await spend(session_factory, datetime(2026, 11, 11, 12, 0, tzinfo=TZ), amount="250000", **fields)


async def stored_user(session_factory, telegram_id=1001) -> User:
    async with session_factory() as session:
        return await session.scalar(select(User).where(User.telegram_user_id == telegram_id))


def messages(harness) -> list[SendMessage]:
    return [r for r in harness.session.requests if isinstance(r, SendMessage)]


def photos(harness) -> list[SendPhoto]:
    return [r for r in harness.session.requests if isinstance(r, SendPhoto)]


# --- Oylik ---------------------------------------------------------------------- #


async def test_previous_month_report_is_sent_on_first_morning(harness, session_factory):
    await october_spender(session_factory)
    assert await send_due_reports(harness.bot, session_factory, FIRST_MORNING) == 1
    (message,) = messages(harness)
    assert message.chat_id == 1001
    assert "Oktabr 2026" in message.text
    assert "Chiqim: <b>700 000 UZS</b>" in message.text
    assert (await stored_user(session_factory)).last_report_month == "2026-10"


async def test_monthly_report_comes_as_picture_then_text(harness, session_factory):
    await october_spender(session_factory)
    await send_due_reports(harness.bot, session_factory, FIRST_MORNING)
    sent = [r for r in harness.session.requests if isinstance(r, (SendPhoto, SendMessage))]
    assert [type(r) for r in sent] == [SendPhoto, SendMessage]
    photo = sent[0]
    assert photo.chat_id == 1001
    assert photo.photo.data.startswith(b"\x89PNG")
    assert "Oylik hisobot" in photo.caption and "Oktabr 2026" in photo.caption
    # Bitta bildirishnoma bo'lishi uchun rasm ovozsiz, matn ovozli yuboriladi.
    assert photo.disable_notification is True
    assert not sent[1].disable_notification


async def test_report_is_sent_only_once(harness, session_factory):
    await october_spender(session_factory)
    await send_due_reports(harness.bot, session_factory, FIRST_MORNING)
    assert await send_due_reports(harness.bot, session_factory, datetime(2026, 11, 1, 10, 0, tzinfo=TZ)) == 0
    assert len(messages(harness)) == 1 and len(photos(harness)) == 1


async def test_report_waits_until_nine_local_time(harness, session_factory):
    await october_spender(session_factory)
    assert await send_due_reports(harness.bot, session_factory, datetime(2026, 11, 1, 8, 0, tzinfo=TZ)) == 0
    assert messages(harness) == []
    assert (await stored_user(session_factory)).last_report_month is None


async def test_missed_first_day_is_caught_up_later(harness, session_factory):
    await october_spender(session_factory)
    assert await send_due_reports(harness.bot, session_factory, datetime(2026, 11, 3, 2, 0, tzinfo=TZ)) == 1


async def test_users_who_disabled_monthly_report_get_nothing(harness, session_factory):
    await october_spender(session_factory, notifications_enabled=False)
    assert await send_due_reports(harness.bot, session_factory, FIRST_MORNING) == 0
    assert messages(harness) == [] and photos(harness) == []


async def test_month_without_transactions_sends_nothing_but_is_marked(harness, session_factory):
    async with session_factory() as session:
        await ts.get_or_create_user(session, 1001, "ali", "Ali")
    assert await send_due_reports(harness.bot, session_factory, FIRST_MORNING) == 0
    assert messages(harness) == [] and photos(harness) == []
    assert (await stored_user(session_factory)).last_report_month == "2026-10"


async def test_each_user_gets_only_own_report(harness, session_factory):
    await october_spender(session_factory, telegram_id=1001)
    async with session_factory() as session:
        await ts.get_or_create_user(session, 2002, "vali", "Vali")
    await send_due_reports(harness.bot, session_factory, FIRST_MORNING)
    assert [m.chat_id for m in messages(harness)] == [1001]
    assert [p.chat_id for p in photos(harness)] == [1001]


async def test_user_who_blocked_the_bot_is_unsubscribed_from_everything(harness, session_factory, monkeypatch):
    await october_spender(session_factory)

    async def blocked(*args, **kwargs):
        raise TelegramForbiddenError(method=SendMessage(chat_id=1001, text="x"), message="bot was blocked by the user")

    monkeypatch.setattr(harness.bot, "send_photo", blocked)
    assert await send_due_reports(harness.bot, session_factory, FIRST_MORNING) == 0
    user = await stored_user(session_factory)
    assert (user.notifications_enabled, user.weekly_report_enabled) == (False, False)


async def test_text_is_still_sent_when_picture_cannot_be_drawn(harness, session_factory, monkeypatch):
    await october_spender(session_factory)

    def broken(*args, **kwargs):
        raise OSError("font file missing")

    monkeypatch.setattr(scheduler, "render_report_image", broken)
    assert await send_due_reports(harness.bot, session_factory, FIRST_MORNING) == 1
    assert photos(harness) == []
    assert "Oktabr 2026" in messages(harness)[0].text


# --- Haftalik -------------------------------------------------------------------- #


async def test_previous_week_report_is_sent_on_monday_morning(harness, session_factory):
    await last_week_spender(session_factory)
    assert await send_due_reports(harness.bot, session_factory, MONDAY_MORNING) == 1
    (photo,) = photos(harness)
    (message,) = messages(harness)
    assert "Haftalik hisobot" in photo.caption and "09.11 – 15.11.2026" in photo.caption
    assert "09.11 – 15.11.2026" in message.text
    assert "Chiqim: <b>250 000 UZS</b>" in message.text
    assert (await stored_user(session_factory)).last_weekly_report == "2026-11-09"


async def test_weekly_report_covers_only_monday_to_sunday_of_last_week(harness, session_factory):
    await last_week_spender(session_factory)
    await spend(session_factory, datetime(2026, 11, 8, 23, 59, tzinfo=TZ), amount="1111")   # oldingi yakshanba
    await spend(session_factory, datetime(2026, 11, 16, 0, 0, tzinfo=TZ), amount="2222")   # shu dushanba
    await spend(session_factory, datetime(2026, 11, 15, 23, 59, tzinfo=TZ), amount="50000")  # o'tgan yakshanba
    await send_due_reports(harness.bot, session_factory, MONDAY_MORNING)
    text = messages(harness)[0].text
    assert "Chiqim: <b>300 000 UZS</b>" in text
    assert "1 111" not in text and "2 222" not in text


async def test_weekly_report_waits_until_nine_on_monday(harness, session_factory):
    await last_week_spender(session_factory)
    assert await send_due_reports(harness.bot, session_factory, datetime(2026, 11, 16, 8, 59, tzinfo=TZ)) == 0
    assert await send_due_reports(harness.bot, session_factory, datetime(2026, 11, 16, 9, 0, tzinfo=TZ)) == 1


async def test_weekly_report_is_sent_once_per_week(harness, session_factory):
    await last_week_spender(session_factory)
    await send_due_reports(harness.bot, session_factory, MONDAY_MORNING)
    assert await send_due_reports(harness.bot, session_factory, datetime(2026, 11, 18, 12, 0, tzinfo=TZ)) == 0
    assert len(messages(harness)) == 1


async def test_missed_monday_is_caught_up_midweek(harness, session_factory):
    await last_week_spender(session_factory)
    assert await send_due_reports(harness.bot, session_factory, datetime(2026, 11, 18, 3, 0, tzinfo=TZ)) == 1


async def test_weekly_report_can_be_disabled_separately(harness, session_factory):
    await last_week_spender(session_factory, weekly_report_enabled=False)
    assert await send_due_reports(harness.bot, session_factory, MONDAY_MORNING) == 0
    assert messages(harness) == []


async def test_week_without_transactions_sends_nothing_but_is_marked(harness, session_factory):
    async with session_factory() as session:
        user = await ts.get_or_create_user(session, 1001, "ali", "Ali")
        await ts.update_user(session, user, notifications_enabled=False)
    assert await send_due_reports(harness.bot, session_factory, MONDAY_MORNING) == 0
    assert (await stored_user(session_factory)).last_weekly_report == "2026-11-09"


async def test_weekly_and_monthly_both_arrive_when_both_are_due(harness, session_factory):
    # 2026-yil 1-iyun dushanba: o'tgan hafta (25–31 may) va o'tgan oy (may) bir vaqtda.
    await spend(session_factory, datetime(2026, 5, 27, 12, 0, tzinfo=TZ), amount="90000")
    assert await send_due_reports(harness.bot, session_factory, datetime(2026, 6, 1, 9, 30, tzinfo=TZ)) == 2
    captions = [p.caption for p in photos(harness)]
    assert "Haftalik hisobot" in captions[0] and "Oylik hisobot" in captions[1]


async def test_report_buttons_open_the_same_week(harness, session_factory):
    await last_week_spender(session_factory)
    await send_due_reports(harness.bot, session_factory, MONDAY_MORNING)
    harness.now = MONDAY_MORNING
    await harness.click("Tranzaksiyalar")
    assert "09.11 – 15.11.2026" in harness.last_text()
    assert "Xarid" in harness.last_text()


async def test_picture_uses_main_currency_and_mentions_others(harness, session_factory, monkeypatch):
    await last_week_spender(session_factory)
    await spend(session_factory, datetime(2026, 11, 12, 12, 0, tzinfo=TZ), amount="40", currency="USD")
    seen = {}

    def spy(heading, period_label, report, other_currencies=None):
        seen.update(heading=heading, period=period_label, currency=report.currency, others=other_currencies)
        return b"\x89PNG-fake"

    monkeypatch.setattr(scheduler, "render_report_image", spy)
    await send_due_reports(harness.bot, session_factory, MONDAY_MORNING)
    assert seen == {"heading": "Haftalik hisobot", "period": "09.11 – 15.11.2026", "currency": "UZS", "others": ["USD"]}


async def test_weekly_toggle_is_respected_when_monthly_stays_on(harness, session_factory):
    await spend(session_factory, datetime(2026, 11, 11, 12, 0, tzinfo=TZ), weekly_report_enabled=False)
    assert await send_due_reports(harness.bot, session_factory, MONDAY_MORNING) == 0
    assert photos(harness) == [] and messages(harness) == []
    assert (await stored_user(session_factory)).last_weekly_report is None


# --- Kunlik: har kuni 21:00 da shu kungi hisobot, faqat matn -------------------------- #

TODAY = datetime(2026, 11, 19, tzinfo=TZ)  # payshanba
EVENING = TODAY.replace(hour=21, minute=5)


async def todays_spender(session_factory, **user_fields) -> None:
    fields = {"weekly_report_enabled": False, "notifications_enabled": False} | user_fields
    await spend(session_factory, TODAY.replace(hour=10, minute=15), amount="250000", **fields)
    await spend(session_factory, TODAY.replace(hour=12, minute=1), amount="54000")


async def test_daily_report_is_sent_at_nine_in_the_evening_as_text_only(harness, session_factory):
    await todays_spender(session_factory)
    assert await send_due_reports(harness.bot, session_factory, EVENING) == 1
    assert photos(harness) == []
    (message,) = messages(harness)
    assert message.chat_id == 1001
    assert "Bugungi hisobot" in message.text and "19.11.2026" in message.text
    assert "Chiqim: <b>304 000 UZS</b>" in message.text
    assert (await stored_user(session_factory)).last_daily_report == "2026-11-19"


async def test_daily_report_lists_each_transaction_with_its_label_newest_first(harness, session_factory):
    await todays_spender(session_factory)
    await send_due_reports(harness.bot, session_factory, EVENING)
    text = messages(harness)[0].text
    assert "<b>−54 000 UZS</b>" in text and "<b>−250 000 UZS</b>" in text
    assert text.count("📝 Xarid") == 2
    assert text.index("12:01") < text.index("10:15")
    assert "19.11 12:01" not in text  # kunlik hisobotda sana takrorlanmaydi, faqat vaqt


async def test_daily_report_is_not_sent_before_nine_in_the_evening(harness, session_factory):
    await todays_spender(session_factory)
    assert await send_due_reports(harness.bot, session_factory, TODAY.replace(hour=20, minute=59)) == 0
    assert messages(harness) == []
    assert (await stored_user(session_factory)).last_daily_report is None


async def test_daily_report_is_sent_once_per_day_and_again_next_day(harness, session_factory):
    await todays_spender(session_factory)
    await send_due_reports(harness.bot, session_factory, EVENING)
    assert await send_due_reports(harness.bot, session_factory, TODAY.replace(hour=23, minute=30)) == 0
    await spend(session_factory, datetime(2026, 11, 20, 13, 0, tzinfo=TZ), amount="9000")
    assert await send_due_reports(harness.bot, session_factory, datetime(2026, 11, 20, 21, 0, tzinfo=TZ)) == 1
    second = messages(harness)[1].text
    assert "20.11.2026" in second and "Chiqim: <b>9 000 UZS</b>" in second
    assert "304 000" not in second


async def test_daily_report_covers_only_today(harness, session_factory):
    await todays_spender(session_factory)
    await spend(session_factory, datetime(2026, 11, 18, 23, 59, tzinfo=TZ), amount="7777")
    await send_due_reports(harness.bot, session_factory, EVENING)
    assert "7 777" not in messages(harness)[0].text


async def test_missed_evening_is_not_reported_next_morning(harness, session_factory):
    await todays_spender(session_factory)
    assert await send_due_reports(harness.bot, session_factory, datetime(2026, 11, 20, 8, 0, tzinfo=TZ)) == 0
    assert messages(harness) == []


async def test_daily_report_can_be_disabled_separately(harness, session_factory):
    await todays_spender(session_factory, daily_report_enabled=False, notifications_enabled=True)
    assert await send_due_reports(harness.bot, session_factory, EVENING) == 0
    assert messages(harness) == []


async def test_day_without_transactions_sends_nothing_but_is_marked(harness, session_factory):
    async with session_factory() as session:
        await ts.get_or_create_user(session, 1001, "ali", "Ali")
    assert await send_due_reports(harness.bot, session_factory, EVENING) == 0
    assert messages(harness) == []
    assert (await stored_user(session_factory)).last_daily_report == "2026-11-19"


async def test_long_day_is_shortened_with_a_pointer_to_the_full_list(harness, session_factory):
    await todays_spender(session_factory)
    for minute in range(20):
        await spend(session_factory, TODAY.replace(hour=15, minute=minute), amount=str(1000 + minute))
    await send_due_reports(harness.bot, session_factory, EVENING)
    text = messages(harness)[0].text
    assert text.count("📝") == 15
    assert "yana 7 ta" in text
    assert len(text) < 4096


async def test_daily_report_buttons_open_that_day_even_later(harness, session_factory):
    await todays_spender(session_factory)
    await send_due_reports(harness.bot, session_factory, EVENING)
    harness.now = datetime(2026, 11, 21, 10, 0, tzinfo=TZ)
    await harness.click("Tranzaksiyalar")
    assert "19.11.2026" in harness.last_text()
    assert harness.last_text().count("📝 Xarid") == 2


async def test_blocked_user_is_unsubscribed_from_daily_too(harness, session_factory, monkeypatch):
    await todays_spender(session_factory)

    async def blocked(*args, **kwargs):
        raise TelegramForbiddenError(method=SendMessage(chat_id=1001, text="x"), message="bot was blocked by the user")

    monkeypatch.setattr(harness.bot, "send_message", blocked)
    assert await send_due_reports(harness.bot, session_factory, EVENING) == 0
    assert (await stored_user(session_factory)).daily_report_enabled is False
