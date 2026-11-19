"""Avtomatik hisobotlar (foydalanuvchining mahalliy vaqti bilan).

- Haftalik: har dushanba 09:00 dan keyin, o‘tgan hafta uchun. Rasm + matn.
- Oylik: har oyning 1-kuni 09:00 dan keyin, o‘tgan oy uchun. Rasm + matn.
- Kunlik: har kuni 21:00 dan keyin, shu kun uchun. Faqat matn.

Rasm ovozsiz, matn bildirishnoma bilan yuboriladi. Haftalik va oylik hisobot bot
o‘sha paytda ishlamay turgan bo‘lsa, keyingi tekshiruvda yuboriladi; kunlik hisobot
faqat o‘sha kunning o‘zida yuboriladi. Har bir davr uchun bir martadan.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.types import BufferedInputFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot import keyboards as kb
from app.bot import render, texts
from app.bot.common import Clock
from app.models import User
from app.services import report_service as rs
from app.services import transaction_service as ts
from app.services.chart_service import render_report_image
from app.utils.dates import Period, period_range, previous_month

logger = logging.getLogger(__name__)

SEND_HOUR = 9
DAILY_HOUR = 21
DAILY_LIST_LIMIT = 15
CHECK_INTERVAL_SECONDS = 30 * 60


@dataclass(frozen=True)
class DueReport:
    kind: str  # "daily", "weekly" yoki "monthly"
    key: str  # davr belgisi: kun ("2026-11-19"), hafta dushanbasi ("2026-11-09") yoki oy ("2026-10")
    period_code: str
    heading: str


def due_reports(user: User, now: datetime) -> list[DueReport]:
    """Shu foydalanuvchiga hozir yuborilishi kerak bo‘lgan hisobotlar."""
    local = now.astimezone(user.tz)
    too_early = local.hour < SEND_HOUR
    due: list[DueReport] = []

    if user.weekly_report_enabled:
        last_monday = (local - timedelta(days=local.weekday() + 7)).date().isoformat()
        if user.last_weekly_report != last_monday and not (local.weekday() == 0 and too_early):
            due.append(DueReport("weekly", last_monday, f"wk{last_monday}", texts.WEEKLY_HEADING))

    if user.notifications_enabled:
        year, month = previous_month(local.year, local.month)
        month_key = f"{year:04d}-{month:02d}"
        if user.last_report_month != month_key and not (local.day == 1 and too_early):
            due.append(DueReport("monthly", month_key, month_key, texts.MONTHLY_HEADING))

    if user.daily_report_enabled and local.hour >= DAILY_HOUR:
        today = local.date().isoformat()
        if user.last_daily_report != today:
            due.append(DueReport("daily", today, f"day{today}", texts.DAILY_HEADING))
    return due


async def _deliver_daily(
    bot: Bot, session: AsyncSession, user: User, due: DueReport, period: Period, report: rs.Report
) -> None:
    report_filter = rs.ReportFilter(start=period.start, end=period.end)
    transactions = await rs.fetch_transactions(session, user.id, report_filter, limit=DAILY_LIST_LIMIT)
    await bot.send_message(
        user.telegram_user_id,
        render.daily_report_text(period.label, report, transactions, user.tz),
        reply_markup=kb.report_summary_actions(kb.ReportKey(due.period_code, period.label), report.count),
    )


async def _deliver(bot: Bot, user: User, due: DueReport, period: Period, report: rs.Report) -> None:
    main = report.currencies[0]
    others = [item.currency for item in report.currencies[1:]]
    try:
        image = await asyncio.to_thread(render_report_image, due.heading, period.label, main, others)
    except Exception as error:  # noqa: BLE001 - rasm chiqmasa ham matnli hisobot yuborilishi kerak
        logger.warning("Report picture failed: %s", type(error).__name__)
        image = None

    if image is not None:
        await bot.send_photo(
            user.telegram_user_id,
            BufferedInputFile(image, filename=f"hisobot_{due.key}.png"),
            caption=texts.REPORT_PHOTO_CAPTION.format(heading=due.heading, period=period.label),
            disable_notification=True,
        )
    await bot.send_message(
        user.telegram_user_id,
        render.report_text(period.label, "", report, user.tz),
        reply_markup=kb.report_summary_actions(kb.ReportKey(due.period_code, period.label), report.count),
    )


async def _mark_sent(session: AsyncSession, user: User, due: DueReport) -> None:
    if due.kind == "daily":
        await ts.update_user(session, user, last_daily_report=due.key)
    elif due.kind == "weekly":
        await ts.update_user(session, user, last_weekly_report=due.key)
    else:
        await ts.update_user(session, user, last_report_month=due.key)


async def send_due_reports(bot: Bot, session_factory: async_sessionmaker[AsyncSession], now: datetime) -> int:
    """Vaqti kelgan kunlik, haftalik va oylik hisobotlarni yuboradi. Yuborilganlar sonini qaytaradi."""
    sent = 0
    async with session_factory() as session:
        users = list(
            await session.scalars(
                select(User).where(
                    User.daily_report_enabled.is_(True)
                    | User.weekly_report_enabled.is_(True)
                    | User.notifications_enabled.is_(True)
                )
            )
        )
        for user in users:
            for due in due_reports(user, now):
                period = period_range(due.period_code, user.tz, now)
                report = await rs.build_report(
                    session, user.id, rs.ReportFilter(start=period.start, end=period.end), user.preferred_currency
                )
                if report.count:
                    try:
                        if due.kind == "daily":
                            await _deliver_daily(bot, session, user, due, period, report)
                        else:
                            await _deliver(bot, user, due, period, report)
                    except TelegramForbiddenError:
                        # Foydalanuvchi botni bloklagan: unga boshqa yozmaymiz.
                        await ts.update_user(
                            session,
                            user,
                            daily_report_enabled=False,
                            weekly_report_enabled=False,
                            notifications_enabled=False,
                        )
                        break
                    except TelegramAPIError as error:
                        logger.warning("%s report not delivered (%s), will retry", due.kind, type(error).__name__)
                        continue
                    sent += 1
                await _mark_sent(session, user, due)
    return sent


async def run_scheduler(bot: Bot, session_factory: async_sessionmaker[AsyncSession], clock: Clock) -> None:
    while True:
        try:
            sent = await send_due_reports(bot, session_factory, clock())
            if sent:
                logger.info("Scheduled reports sent: %s", sent)
        except Exception as error:  # noqa: BLE001 - fon vazifasi har qanday xatodan keyin ham ishlashda davom etishi kerak
            logger.error("Scheduled report check failed: %s", type(error).__name__)
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
