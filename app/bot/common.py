"""Handlerlar uchun umumiy yordamchilar."""

from __future__ import annotations

import re
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime

from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from app.bot import texts
from app.utils.validators import is_valid_last4

Clock = Callable[[], datetime]


def callback_message(callback: CallbackQuery) -> Message | None:
    """Tugma bosilgan xabar (juda eski xabarlar uchun ``None``)."""
    return callback.message if isinstance(callback.message, Message) else None


async def remove_buttons(callback: CallbackQuery) -> None:
    """Bosilgan xabardagi tugmalarni olib tashlaydi, qayta bosilmasligi uchun."""
    message = callback_message(callback)
    if message is not None:
        with suppress(TelegramAPIError):
            await message.edit_reply_markup(reply_markup=None)


async def edit_or_send(callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    """Xabarni joyida yangilaydi; bo‘lmasa yangi xabar yuboradi."""
    message = callback_message(callback)
    if message is None:
        await callback.bot.send_message(callback.from_user.id, text, reply_markup=reply_markup)
        return
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as error:
        if "message is not modified" not in str(error):
            await message.answer(text, reply_markup=reply_markup)


async def read_last4(message: Message) -> str | None:
    """Oxirgi 4 raqamni o‘qiydi. To‘liq karta raqami yuborilsa rad etadi va xabarni o‘chirishga urinadi."""
    raw = (message.text or "").strip()
    if len(re.sub(r"\D", "", raw)) > 4:
        with suppress(TelegramAPIError):
            await message.delete()
        await message.answer(texts.FULL_PAN_REFUSED)
        return None
    cleaned = raw.lstrip("*• ").strip()
    if not is_valid_last4(cleaned):
        await message.answer(texts.BAD_LAST4)
        return None
    return cleaned
