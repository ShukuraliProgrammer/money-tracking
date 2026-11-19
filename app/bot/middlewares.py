"""Har bir yangilanish uchun baza sessiyasi va foydalanuvchi profilini tayyorlaydi."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services import transaction_service as ts


class DatabaseMiddleware(BaseMiddleware):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], timezone: str, currency: str) -> None:
        self._session_factory = session_factory
        self._timezone = timezone
        self._currency = currency

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        telegram_user = data.get("event_from_user")
        if telegram_user is None or telegram_user.is_bot:
            return None
        async with self._session_factory() as session:
            data["session"] = session
            data["user"] = await ts.get_or_create_user(
                session,
                telegram_user_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                timezone=self._timezone,
                currency=self._currency,
            )
            return await handler(event, data)
