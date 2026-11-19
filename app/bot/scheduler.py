"""Oy boshida o‘tgan oy hisobotini avtomatik yuborish.

Har oyning 1-kuni mahalliy vaqt bilan 09:00 dan keyin yuboriladi. Bot o‘sha
paytda ishlamay turgan bo‘lsa, keyingi tekshiruvda yuboradi (oyiga bir marta).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot import keyboards as kb
from app.bot import render, texts
from app.bot.common import Clock
from app.models import User
from app.services import report_service as rs
from app.services import transaction_service as ts
from app.utils.dates import period_range, previous_month

logger = logging.getLogger(__name__)

SEND_HOUR = 9
CHECK_INTERVAL_SECONDS = 30 * 60


async def send_monthly_reports(bot: Bot, session_factory: async_sessionmaker[AsyncSession], now: datetime) -> int:
    """Hisobot yuborilishi kerak bo‘lgan foydalanuvchilarga yuboradi. Yuborilganlar sonini qaytaradi."""
    sent = 0
    async with session_factory() as session:
        users = list(await session.scalars(select(User).where(User.notifications_enabled.is_(True))))
        for user in users:
            local = now.astimezone(user.tz)
            year, month = previous_month(local.year, local.month)
            month_key = f"{year:04d}-{month:02d}"
            if user.last_report_month == month_key:
                continue
            if local.day == 1 and local.hour < SEND_HOUR:
                continue

            period = period_range(month_key, user.tz, now)
            report = await rs.build_report(
                session, user.id, rs.ReportFilter(start=period.start, end=period.end), user.preferred_currency
            )
            if report.count:
                filter_line = f"💳 {texts.ALL_CARDS} · 🏷 {texts.ALL_CATEGORIES}"
                text = texts.MONTHLY_REPORT_INTRO + render.report_text(period.label, filter_line, report, user.tz)
                try:
                    await bot.send_message(
                        user.telegram_user_id,
                        render.clip(text),
                        reply_markup=kb.report_summary_actions(month_key, 0, 0, report.count),
                    )
                except TelegramForbiddenError:
                    # Foydalanuvchi botni bloklagan: unga boshqa yozmaymiz.
                    await ts.update_user(session, user, notifications_enabled=False)
                    continue
                except TelegramAPIError as error:
                    logger.warning("Monthly report not delivered (%s), will retry", type(error).__name__)
                    continue
                sent += 1
            await ts.update_user(session, user, last_report_month=month_key)
    return sent


async def run_scheduler(bot: Bot, session_factory: async_sessionmaker[AsyncSession], clock: Clock) -> None:
    while True:
        try:
            sent = await send_monthly_reports(bot, session_factory, clock())
            if sent:
                logger.info("Monthly reports sent: %s", sent)
        except Exception as error:  # noqa: BLE001 - fon vazifasi har qanday xatodan keyin ham ishlashda davom etishi kerak
            logger.error("Monthly report check failed: %s", type(error).__name__)
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
