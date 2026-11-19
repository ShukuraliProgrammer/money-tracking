"""Dispatcher’ni yig‘ish: middleware, routerlar va xatolarni ushlash."""

from __future__ import annotations

import logging
from contextlib import suppress
from datetime import UTC, datetime

from aiogram import Dispatcher, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
from aiogram.types import CallbackQuery, ErrorEvent, Message
from aiogram.utils.callback_answer import CallbackAnswer, CallbackAnswerMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot import texts
from app.bot.common import Clock
from app.bot.handlers import cards, reports, settings, start, transactions
from app.bot.middlewares import DatabaseMiddleware
from app.services.notes import NoteAnalyzer
from app.services.parser import TransactionParser

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _has_live_message(callback: CallbackQuery) -> bool:
    """Juda eski xabarlardagi tugmalar uchun Telegram xabar matnini bermaydi."""
    return isinstance(callback.message, Message)


async def _on_error(event: ErrorEvent) -> bool:
    # Xato matni yoki foydalanuvchi ma’lumoti emas, faqat xato turi va joyi yoziladi.
    logger.error("Update handling failed: %s", type(event.exception).__name__, exc_info=event.exception)
    update = event.update
    target = update.message
    if update.callback_query is not None:
        with suppress(TelegramAPIError):
            await update.callback_query.answer()
        if isinstance(update.callback_query.message, Message):
            target = update.callback_query.message
    if target is not None:
        with suppress(TelegramAPIError):
            await target.answer(texts.TEMPORARY_ERROR)
    return True


async def _on_unhandled_callback(callback_answer: CallbackAnswer) -> None:
    callback_answer.text = texts.STALE_BUTTON
    callback_answer.show_alert = True


def build_dispatcher(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    parser: TransactionParser,
    note_analyzer: NoteAnalyzer,
    storage: BaseStorage | None = None,
    clock: Clock | None = None,
    default_timezone: str = "Asia/Tashkent",
    default_currency: str = "UZS",
) -> Dispatcher:
    # Bir foydalanuvchining xabarlari navbat bilan qayta ishlanadi: bir nechta xabar birdaniga
    # forward qilinganda ular bir-birining qoralamasini buzmaydi.
    dispatcher = Dispatcher(storage=storage or MemoryStorage(), events_isolation=SimpleEventIsolation())
    dispatcher["parser"] = parser
    dispatcher["note_analyzer"] = note_analyzer
    dispatcher["clock"] = clock or _utcnow

    # Bot faqat shaxsiy chatda ishlaydi: guruhda moliyaviy ma’lumot ko‘rsatilmaydi.
    dispatcher.message.filter(F.chat.type == ChatType.PRIVATE)
    dispatcher.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)

    database = DatabaseMiddleware(session_factory, default_timezone, default_currency)
    dispatcher.message.middleware(database)
    dispatcher.callback_query.middleware(CallbackAnswerMiddleware())
    dispatcher.callback_query.middleware(database)

    for module in (start, cards, reports, settings, transactions):
        router = module.create_router()
        router.callback_query.filter(_has_live_message)
        dispatcher.include_router(router)

    fallback = Router(name="fallback")
    fallback.callback_query.register(_on_unhandled_callback)
    dispatcher.include_router(fallback)

    dispatcher.errors.register(_on_error)
    return dispatcher
