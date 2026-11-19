"""Karta nazoratchi — ishga tushirish nuqtasi: ``python -m app.main``."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from aiogram.utils.token import TokenValidationError, validate_token
from alembic import command
from alembic.config import Config
from pydantic import ValidationError

from app.bot import texts
from app.bot.dispatcher import build_dispatcher
from app.bot.scheduler import run_scheduler
from app.config import Settings, get_settings
from app.database import create_engine, create_session_factory
from app.services.llm import build_llm_service
from app.services.notes import NoteAnalyzer
from app.services.parser import TransactionParser
from app.utils.crypto import get_cipher
from app.utils.logging import setup_logging

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DRAFT_TTL_SECONDS = 24 * 60 * 60


def run_migrations(database_url: str) -> None:
    """Bazani oxirgi sxemaga keltiradi (``alembic upgrade head`` bilan bir xil)."""
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "head")


def build_storage(settings: Settings) -> BaseStorage:
    """Suhbat holati: REDIS_URL berilgan bo‘lsa Redis’da, aks holda xotirada."""
    if settings.redis_url:
        from aiogram.fsm.storage.redis import RedisStorage

        # Tugallanmagan suhbat qoralamasi Redis’da bir sutkadan ortiq turmaydi.
        return RedisStorage.from_url(settings.redis_url, state_ttl=DRAFT_TTL_SECONDS, data_ttl=DRAFT_TTL_SECONDS)
    return MemoryStorage()


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def run(settings: Settings) -> None:
    engine = create_engine(settings.database_url, hide_parameters=True)
    session_factory = create_session_factory(engine)

    llm = build_llm_service(settings)
    logger.info("LLM: %s", settings.llm_provider if llm else "o‘chirilgan (faqat qoidalar)")

    bot = Bot(settings.bot_token.get_secret_value(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = build_storage(settings)
    dispatcher = build_dispatcher(
        session_factory=session_factory,
        parser=TransactionParser(llm),
        note_analyzer=NoteAnalyzer(llm if settings.llm_note_analysis else None),
        storage=storage,
        clock=_utcnow,
        default_timezone=settings.default_timezone,
        default_currency=settings.default_currency,
    )

    scheduler: asyncio.Task[None] | None = None
    try:
        await bot.set_my_commands([BotCommand(command=name, description=text) for name, text in texts.BOT_COMMANDS])
        scheduler = asyncio.create_task(run_scheduler(bot, session_factory, _utcnow))
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        if scheduler is not None:
            scheduler.cancel()
            with suppress(asyncio.CancelledError):
                await scheduler
        await storage.close()
        await bot.session.close()
        await engine.dispose()


def validate_bot_token(token: str) -> bool:
    try:
        return validate_token(token)
    except TokenValidationError:
        return False


def main() -> None:
    try:
        settings = get_settings()
    except ValidationError as error:
        names = ", ".join(sorted({str(item["loc"][0]).upper() for item in error.errors()}))
        raise SystemExit(
            f"Sozlamalar to‘liq emas yoki noto‘g‘ri: {names}. .env.example faylidan nusxa olib, .env ni to‘ldiring."
        ) from None
    setup_logging(settings.log_level)
    if not validate_bot_token(settings.bot_token.get_secret_value()):
        raise SystemExit("BOT_TOKEN bo‘sh yoki noto‘g‘ri ko‘rinishda. .env faylida @BotFather bergan tokenni yozing.")
    try:
        get_cipher()  # kalit noto‘g‘ri bo‘lsa, bot ishga tushmasdan oldin aniq xato beradi
    except ValueError as error:
        raise SystemExit(str(error)) from None
    run_migrations(settings.database_url)
    try:
        asyncio.run(run(settings))
    except TelegramUnauthorizedError:
        raise SystemExit("BOT_TOKEN noto‘g‘ri: Telegram uni qabul qilmadi. @BotFather bergan tokenni tekshiring.") from None
    except TelegramNetworkError:
        raise SystemExit("Telegram’ga ulanib bo‘lmadi. Internet aloqasini tekshirib, botni qayta ishga tushiring.") from None
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to‘xtatildi")


if __name__ == "__main__":
    main()
