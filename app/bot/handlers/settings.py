"""/settings va /categories: sozlamalar, turlar va ma’lumotlarni o‘chirish."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.callback_answer import CallbackAnswer
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards as kb
from app.bot import render, texts
from app.bot.common import callback_message, edit_or_send, remove_buttons
from app.bot.states import CategoryFlow, SettingsFlow
from app.models import User
from app.services import transaction_service as ts
from app.utils.validators import split_emoji

PLAIN_TEXT = F.text & ~F.text.startswith("/")


# --- Sozlamalar ---------------------------------------------------------------- #


async def cmd_settings(message: Message, state: FSMContext, user: User) -> None:
    await state.clear()
    await message.answer(render.settings_text(user), reply_markup=kb.settings_menu(user.notifications_enabled))


async def on_menu(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    await state.clear()
    await edit_or_send(callback, render.settings_text(user), kb.settings_menu(user.notifications_enabled))


async def on_timezone_request(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsFlow.timezone)
    await edit_or_send(callback, texts.ASK_TIMEZONE, kb.timezone_choice())


async def on_timezone_button(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    await ts.update_user(session, user, timezone=callback.data.split(":", 2)[2])
    await on_menu(callback, state, user)


async def on_timezone_text(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    try:
        await ts.update_user(session, user, timezone=(message.text or "").strip())
    except ts.InvalidInputError:
        await message.answer(texts.TIMEZONE_NOT_FOUND, reply_markup=kb.timezone_choice())
        return
    await cmd_settings(message, state, user)


async def on_currency_request(callback: CallbackQuery) -> None:
    await edit_or_send(callback, texts.ASK_SETTINGS_CURRENCY, kb.currency_choice("set:cur"))


async def on_currency_button(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    await ts.update_user(session, user, preferred_currency=callback.data.split(":", 2)[2])
    await on_menu(callback, state, user)


async def on_notifications_toggle(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
) -> None:
    await ts.update_user(session, user, notifications_enabled=not user.notifications_enabled)
    await on_menu(callback, state, user)


async def on_wipe_request(callback: CallbackQuery) -> None:
    await edit_or_send(callback, texts.WIPE_CONFIRM, kb.wipe_confirm())


async def on_wipe_confirmed(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    await ts.delete_user_data(session, user.id)
    await state.clear()
    await edit_or_send(callback, texts.WIPED)


# --- Turlar ---------------------------------------------------------------------- #


async def _categories_view(session: AsyncSession, user: User):
    categories = await ts.list_categories(session, user.id)
    return render.categories_list(categories), kb.categories_menu(categories)


async def cmd_categories(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    await state.clear()
    text, markup = await _categories_view(session, user)
    await message.answer(text, reply_markup=markup)


async def on_category_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CategoryFlow.name)
    await remove_buttons(callback)
    await callback_message(callback).answer(texts.ASK_NEW_CATEGORY)


async def on_category_name(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    emoji, name = split_emoji(message.text or "")
    try:
        await ts.add_category(session, user.id, name, emoji)
    except ts.ServiceError as error:
        await message.answer(f"⚠️ {error}")
        return
    await state.clear()
    text, markup = await _categories_view(session, user)
    await message.answer(f"{texts.CATEGORY_ADDED}\n\n{text}", reply_markup=markup)


async def on_category_delete(
    callback: CallbackQuery, session: AsyncSession, user: User, callback_answer: CallbackAnswer
) -> None:
    category = await ts.get_category(session, user.id, int(callback.data.rsplit(":", 1)[1]))
    if category is None or category.is_default:
        callback_answer.text = texts.CATEGORY_NOT_FOUND
        callback_answer.show_alert = True
    else:
        await ts.delete_category(session, user.id, category.id)
        callback_answer.text = texts.CATEGORY_DELETED
    text, markup = await _categories_view(session, user)
    await edit_or_send(callback, text, markup)


def create_router() -> Router:
    router = Router(name="settings")
    message, callback = router.message, router.callback_query

    message.register(cmd_settings, Command("settings"))
    message.register(cmd_categories, Command("categories"))

    callback.register(on_menu, F.data == "set:menu")
    callback.register(on_timezone_request, F.data == "set:tz")
    callback.register(on_timezone_button, F.data.startswith("set:tz:"))
    callback.register(on_currency_request, F.data == "set:cur")
    callback.register(on_currency_button, F.data.regexp(r"^set:cur:[A-Z]{3}$"))
    callback.register(on_notifications_toggle, F.data == "set:notif")
    callback.register(on_wipe_request, F.data == "set:wipe")
    callback.register(on_wipe_confirmed, F.data == "set:wipe:yes")
    callback.register(on_category_add, F.data == "cat:add")
    callback.register(on_category_delete, F.data.regexp(r"^cat:del:\d+$"))

    message.register(on_timezone_text, SettingsFlow.timezone, PLAIN_TEXT)
    message.register(on_category_name, CategoryFlow.name, PLAIN_TEXT)
    return router
