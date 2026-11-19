from datetime import datetime
from decimal import Decimal

import pytest
from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import SendMessage
from sqlalchemy import select

from app.bot.scheduler import send_monthly_reports
from app.models import User
from app.schemas import NoteAnalysis
from app.services import transaction_service as ts
from tests.bot_harness import BotHarness
from tests.conftest import TZ, make_parsed

FIRST_MORNING = datetime(2026, 11, 1, 9, 30, tzinfo=TZ)


@pytest.fixture
def harness(session_factory):
    return BotHarness(session_factory, FIRST_MORNING)


async def october_spender(session_factory, telegram_id=1001, **user_fields) -> None:
    async with session_factory() as session:
        user = await ts.get_or_create_user(session, telegram_id, "ali", "Ali")
        if user_fields:
            await ts.update_user(session, user, **user_fields)
        parsed = make_parsed(amount=Decimal("700000"), occurred_at=datetime(2026, 10, 15, 12, 0, tzinfo=TZ))
        await ts.create_transaction(session, user, parsed, "Oktabr xaridi", None, None, NoteAnalysis())


async def stored_user(session_factory, telegram_id=1001) -> User:
    async with session_factory() as session:
        return await session.scalar(select(User).where(User.telegram_user_id == telegram_id))


def sent(harness) -> list[SendMessage]:
    return [r for r in harness.session.requests if isinstance(r, SendMessage)]


async def test_previous_month_report_is_sent_on_first_morning(harness, session_factory):
    await october_spender(session_factory)
    assert await send_monthly_reports(harness.bot, session_factory, FIRST_MORNING) == 1
    (message,) = sent(harness)
    assert message.chat_id == 1001
    assert "Oktabr 2026" in message.text
    assert "Chiqim: <b>700 000 UZS</b>" in message.text
    assert (await stored_user(session_factory)).last_report_month == "2026-10"


async def test_report_is_sent_only_once(harness, session_factory):
    await october_spender(session_factory)
    await send_monthly_reports(harness.bot, session_factory, FIRST_MORNING)
    assert await send_monthly_reports(harness.bot, session_factory, datetime(2026, 11, 1, 10, 0, tzinfo=TZ)) == 0
    assert len(sent(harness)) == 1


async def test_report_waits_until_nine_local_time(harness, session_factory):
    await october_spender(session_factory)
    assert await send_monthly_reports(harness.bot, session_factory, datetime(2026, 11, 1, 8, 0, tzinfo=TZ)) == 0
    assert sent(harness) == []
    assert (await stored_user(session_factory)).last_report_month is None


async def test_missed_first_day_is_caught_up_later(harness, session_factory):
    await october_spender(session_factory)
    assert await send_monthly_reports(harness.bot, session_factory, datetime(2026, 11, 3, 2, 0, tzinfo=TZ)) == 1


async def test_users_who_disabled_notifications_get_nothing(harness, session_factory):
    await october_spender(session_factory, notifications_enabled=False)
    assert await send_monthly_reports(harness.bot, session_factory, FIRST_MORNING) == 0
    assert sent(harness) == []


async def test_month_without_transactions_sends_nothing_but_is_marked(harness, session_factory):
    async with session_factory() as session:
        await ts.get_or_create_user(session, 1001, "ali", "Ali")
    assert await send_monthly_reports(harness.bot, session_factory, FIRST_MORNING) == 0
    assert sent(harness) == []
    assert (await stored_user(session_factory)).last_report_month == "2026-10"


async def test_each_user_gets_only_own_report(harness, session_factory):
    await october_spender(session_factory, telegram_id=1001)
    async with session_factory() as session:
        await ts.get_or_create_user(session, 2002, "vali", "Vali")
    await send_monthly_reports(harness.bot, session_factory, FIRST_MORNING)
    assert [m.chat_id for m in sent(harness)] == [1001]


async def test_user_who_blocked_the_bot_is_unsubscribed(harness, session_factory, monkeypatch):
    await october_spender(session_factory)

    async def blocked(*args, **kwargs):
        raise TelegramForbiddenError(method=SendMessage(chat_id=1001, text="x"), message="bot was blocked by the user")

    monkeypatch.setattr(harness.bot, "send_message", blocked)
    assert await send_monthly_reports(harness.bot, session_factory, FIRST_MORNING) == 0
    assert (await stored_user(session_factory)).notifications_enabled is False
