"""/cards va /addcard: kartalarni ko‘rish, qo‘shish, o‘chirish.

Kartaning faqat oxirgi 4 ta raqami so‘raladi va saqlanadi.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.callback_answer import CallbackAnswer
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards as kb
from app.bot import render, texts
from app.bot.common import callback_message, edit_or_send, read_last4, remove_buttons
from app.bot.states import CardFlow
from app.models import User
from app.services import transaction_service as ts
from app.utils.validators import mask_card_numbers

PLAIN_TEXT = F.text & ~F.text.startswith("/")


async def _cards_view(session: AsyncSession, user: User):
    cards = await ts.list_cards(session, user.id)
    return render.cards_list(cards), kb.cards_menu(cards)


async def cmd_cards(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    await state.clear()
    text, markup = await _cards_view(session, user)
    await message.answer(text, reply_markup=markup)


async def on_cards_list(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    text, markup = await _cards_view(session, user)
    await edit_or_send(callback, text, markup)


async def cmd_addcard(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(CardFlow.name)
    await message.answer(texts.ASK_CARD_NAME)


async def on_add_card(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(CardFlow.name)
    await callback_message(callback).answer(texts.ASK_CARD_NAME)


async def on_name(message: Message, state: FSMContext) -> None:
    name = " ".join(mask_card_numbers(message.text or "")[0].split())
    if not 1 <= len(name) <= 64:
        await message.answer(texts.BAD_CARD_NAME)
        return
    await state.update_data(name=name)
    await state.set_state(CardFlow.last4)
    await message.answer(texts.ASK_LAST4)


async def on_last4(message: Message, state: FSMContext) -> None:
    last4 = await read_last4(message)
    if last4 is None:
        return
    await state.update_data(last4=last4)
    await state.set_state(CardFlow.network)
    await message.answer(texts.ASK_NETWORK, reply_markup=kb.network_choice())


async def on_network(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(network=callback.data.rsplit(":", 1)[1])
    await state.set_state(CardFlow.bank)
    await remove_buttons(callback)
    await callback_message(callback).answer(texts.ASK_BANK, reply_markup=kb.skip_bank())


async def on_bank_text(message: Message, state: FSMContext) -> None:
    await state.update_data(bank=" ".join((message.text or "").split())[:64])
    await state.set_state(CardFlow.currency)
    await message.answer(texts.ASK_CURRENCY, reply_markup=kb.currency_choice("card:cur"))


async def on_bank_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(bank=None)
    await state.set_state(CardFlow.currency)
    await remove_buttons(callback)
    await callback_message(callback).answer(texts.ASK_CURRENCY, reply_markup=kb.currency_choice("card:cur"))


async def _create(target: Message, state: FSMContext, session: AsyncSession, user: User, currency: str) -> None:
    data = await state.get_data()
    await state.clear()
    try:
        card = await ts.add_card(
            session,
            user.id,
            name=data["name"],
            last4=data["last4"],
            network=data.get("network", "Unknown"),
            bank_name=data.get("bank"),
            currency=currency,
        )
    except ts.ServiceError as error:
        await target.answer(f"⚠️ {error}")
        return
    await target.answer(texts.CARD_ADDED.format(card=render.esc(render.card_title(card))))


async def on_currency_button(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    await remove_buttons(callback)
    await _create(callback_message(callback), state, session, user, callback.data.rsplit(":", 1)[1])


async def on_currency_text(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    code = (message.text or "").strip().upper()
    if len(code) != 3 or not code.isalpha():
        await message.answer(texts.BAD_CURRENCY, reply_markup=kb.currency_choice("card:cur"))
        return
    await _create(message, state, session, user, code)


async def on_use_buttons(message: Message) -> None:
    await message.answer(texts.USE_BUTTONS)


async def on_toggle(
    callback: CallbackQuery, session: AsyncSession, user: User, callback_answer: CallbackAnswer
) -> None:
    if await ts.toggle_card_active(session, user.id, int(callback.data.rsplit(":", 1)[1])) is None:
        callback_answer.text = texts.CARD_NOT_FOUND
        callback_answer.show_alert = True
    text, markup = await _cards_view(session, user)
    await edit_or_send(callback, text, markup)


async def on_delete_request(
    callback: CallbackQuery, session: AsyncSession, user: User, callback_answer: CallbackAnswer
) -> None:
    card = await ts.get_card(session, user.id, int(callback.data.rsplit(":", 1)[1]))
    if card is None:
        callback_answer.text = texts.CARD_NOT_FOUND
        callback_answer.show_alert = True
        return
    text = texts.CARD_DELETE_CONFIRM.format(card=render.esc(render.card_title(card)))
    await edit_or_send(callback, text, kb.card_delete_confirm(card.id))


async def on_delete_confirmed(
    callback: CallbackQuery, session: AsyncSession, user: User, callback_answer: CallbackAnswer
) -> None:
    deleted = await ts.delete_card(session, user.id, int(callback.data.rsplit(":", 1)[1]))
    callback_answer.text = texts.CARD_DELETED if deleted else texts.CARD_NOT_FOUND
    text, markup = await _cards_view(session, user)
    await edit_or_send(callback, text, markup)


def create_router() -> Router:
    router = Router(name="cards")
    message, callback = router.message, router.callback_query

    message.register(cmd_cards, Command("cards"))
    message.register(cmd_addcard, Command("addcard"))

    callback.register(on_cards_list, F.data == "card:list")
    callback.register(on_add_card, F.data == "card:add")
    callback.register(on_network, F.data.startswith("card:net:"), CardFlow.network)
    callback.register(on_bank_skip, F.data == "card:bank:skip", CardFlow.bank)
    callback.register(on_currency_button, F.data.startswith("card:cur:"), CardFlow.currency)
    callback.register(on_toggle, F.data.regexp(r"^card:toggle:\d+$"))
    callback.register(on_delete_request, F.data.regexp(r"^card:del:\d+$"))
    callback.register(on_delete_confirmed, F.data.regexp(r"^card:delok:\d+$"))

    message.register(on_name, CardFlow.name, PLAIN_TEXT)
    message.register(on_last4, CardFlow.last4, PLAIN_TEXT)
    message.register(on_use_buttons, StateFilter(CardFlow.network), PLAIN_TEXT)
    message.register(on_bank_text, CardFlow.bank, PLAIN_TEXT)
    message.register(on_currency_text, CardFlow.currency, PLAIN_TEXT)
    return router
