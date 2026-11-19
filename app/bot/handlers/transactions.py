"""Tranzaksiya kiritish oqimi.

Foydalanuvchi xabar yuboradi → bot uni o‘qiydi → yetishmagan ma’lumotni so‘raydi →
uchta savol beradi (nima uchun, qaysi tur, qaysi karta) → saqlaydi.

Bot faqat foydalanuvchining o‘zi yuborgan yoki forward qilgan xabar bilan ishlaydi.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timedelta
from decimal import Decimal

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    Message,
    MessageOriginChannel,
    MessageOriginChat,
    MessageOriginUser,
)
from aiogram.utils.callback_answer import CallbackAnswer
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards as kb
from app.bot import render, texts
from app.bot.common import Clock, callback_message, read_last4, remove_buttons
from app.bot.states import TxFlow
from app.models import User
from app.schemas import NoteAnalysis, ParsedTransaction
from app.services import transaction_service as ts
from app.services.llm import ImageInput, LLMError
from app.services.notes import NoteAnalyzer
from app.services.parser import RuleBasedParser, TransactionParser
from app.services.transfers import (
    Leg,
    find_transfer_counterpart,
    is_transfer_pair,
    split_pair,
)
from app.utils.dates import parse_user_datetime
from app.utils.images import guess_image_type, to_supported_image
from app.utils.money import parse_amount
from app.utils.pdf import PdfError, extract_pdf_text
from app.utils.validators import (
    contains_full_card_number,
    contains_secret_code,
    mask_card_numbers,
    split_emoji,
)

MAX_TEXT_LENGTH = 2000
MAX_NOTE_LENGTH = 500
MAX_AMOUNT = Decimal("10000000000000")
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_PDF_TEXT_LENGTH = 4000

_FORWARD_SOURCES = {"cardxabarbot": "cardxabar", "humocardbot": "humo"}
_rules = RuleBasedParser()
logger = logging.getLogger(__name__)

PLAIN_TEXT = F.text & ~F.text.startswith("/")
def image_type(message: Message) -> str | None:
    """Xabar rasm bo‘lsa (photo yoki fayl sifatida yuborilgan rasm), uning turi."""
    if message.photo:
        return "image/jpeg"
    if message.document:
        return guess_image_type(message.document.mime_type, message.document.file_name)
    return None


def is_pdf(message: Message) -> bool:
    document = message.document
    if document is None:
        return False
    return document.mime_type == "application/pdf" or (document.file_name or "").lower().endswith(".pdf")


IMAGE = F.func(lambda message: image_type(message) is not None)
PDF = F.func(is_pdf)

BUTTON_STATES = (
    TxFlow.waiting_type,
    TxFlow.waiting_duplicate,
    TxFlow.waiting_transfer,
    TxFlow.edit_menu,
    TxFlow.waiting_category,
    TxFlow.waiting_card,
)


# --------------------------------------------------------------------------- #
# Qoralama (draft) bilan ishlash
# --------------------------------------------------------------------------- #


async def load_draft(state: FSMContext) -> ParsedTransaction:
    data = await state.get_data()
    return ParsedTransaction.model_validate(data["draft"])


async def store_draft(state: FSMContext, draft: ParsedTransaction) -> None:
    draft.refresh_missing_fields()
    await state.update_data(draft=draft.model_dump(mode="json"))


def forward_info(message: Message) -> tuple[str | None, datetime | None]:
    """Forward qilingan xabar qaysi botdan va qachon yuborilganini aniqlaydi.

    Bu ma’lumot foydalanuvchi forward qilgan xabarning o‘zida keladi; bot boshqa
    botlarning xabarlarini o‘zi o‘qimaydi.
    """
    origin = message.forward_origin
    if origin is None:
        return None, None
    username: str | None = None
    if isinstance(origin, MessageOriginUser):
        username = origin.sender_user.username
    elif isinstance(origin, MessageOriginChat):
        username = origin.sender_chat.username
    elif isinstance(origin, MessageOriginChannel):
        username = origin.chat.username
    return _FORWARD_SOURCES.get((username or "").lower()), origin.date


async def advance(target: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    """Qoralamada nima yetishmasa, shuni so‘raydi; hammasi joyida bo‘lsa «Nima uchun?» deb so‘raydi."""
    data = await state.get_data()
    draft = ParsedTransaction.model_validate(data["draft"])

    if draft.amount is None:
        await state.set_state(TxFlow.waiting_amount)
        await target.answer(texts.ASK_AMOUNT, reply_markup=kb.cancel_only())
        return
    if draft.transaction_type is None:
        await state.set_state(TxFlow.waiting_type)
        await target.answer(texts.ASK_TYPE, reply_markup=kb.type_choice())
        return
    if draft.occurred_at is None:
        await state.set_state(TxFlow.waiting_date)
        await target.answer(texts.ASK_DATE, reply_markup=kb.date_choice())
        return
    if not data.get("transfer_declined"):
        # Bu xabar avval saqlangan tranzaksiyaning ikkinchi tomoni bo‘lishi mumkin (o‘z kartalar orasidagi o‘tkazma).
        counterpart = await find_transfer_counterpart(session, user.id, draft)
        if counterpart is not None:
            sent, received = split_pair(Leg.from_parsed(draft), Leg.from_transaction(counterpart))
            await state.update_data(transfer_counterpart_id=counterpart.id)
            await state.set_state(TxFlow.waiting_transfer)
            await target.answer(
                texts.TRANSFER_SUSPECTED_SAVED.format(
                    route=render.transfer_route(sent, received), line=render.transaction_line(counterpart, user.tz)
                ),
                reply_markup=kb.transfer_choice("tx:tr"),
            )
            return
    if not data.get("duplicate_accepted"):
        duplicate = await ts.find_duplicate(session, user.id, draft)
        if duplicate is not None:
            await state.set_state(TxFlow.waiting_duplicate)
            line = render.transaction_line(duplicate, user.tz)
            await target.answer(texts.DUPLICATE_WARNING.format(line=line), reply_markup=kb.duplicate_choice())
            return

    await state.set_state(TxFlow.waiting_note)
    await target.answer(
        f"{render.draft_summary(draft, user.tz)}\n\n{texts.ASK_WHY}", reply_markup=kb.draft_actions()
    )


# --------------------------------------------------------------------------- #
# Yangi xabar
# --------------------------------------------------------------------------- #


async def cmd_add(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(TxFlow.waiting_input)
    await message.answer(texts.ADD_PROMPT)


async def on_new_message(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    parser: TransactionParser,
    clock: Clock,
) -> None:
    text = (message.text or "").strip()
    if len(text) > MAX_TEXT_LENGTH:
        await message.answer(texts.TOO_LONG)
        return
    source_hint, _ = forward_info(message)
    await _process_text(message, state, session, user, parser, clock, text, source_hint, texts.NOT_UNDERSTOOD)


async def _process_text(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    parser: TransactionParser,
    clock: Clock,
    text: str,
    source_hint: str | None,
    not_understood: str,
) -> None:
    """Matnni (xabar yoki PDF’dan olingan) tranzaksiya qoralamasiga aylantiradi va oqimni boshlaydi."""
    if contains_secret_code(text):
        # Maxfiy kod bo‘lishi mumkin: hech narsa saqlanmaydi va LLM’ga yuborilmaydi.
        with suppress(TelegramAPIError):
            await message.delete()
        await message.answer(texts.SECRET_WARNING)
        return

    categories = [category.name for category in await ts.list_categories(session, user.id)]
    draft = await parser.parse(text, user.tz, clock(), source_hint=source_hint, categories=categories)

    if draft.amount is None and draft.transaction_type is None:
        await message.answer(not_understood)
        return
    if contains_full_card_number(text):
        with suppress(TelegramAPIError):
            await message.delete()
        await message.answer(texts.PAN_NOTICE)
    await _start_draft(message, state, session, user, draft)


async def _start_draft(
    message: Message, state: FSMContext, session: AsyncSession, user: User, draft: ParsedTransaction
) -> None:
    _, forwarded_at = forward_info(message)
    if draft.occurred_at is None and forwarded_at is not None:
        # Sana yozilmagan, lekin forward qilingan xabarning asl yuborilgan vaqti ma’lum.
        draft.occurred_at = forwarded_at
    draft.refresh_missing_fields()
    await state.set_data({"draft": draft.model_dump(mode="json")})
    await advance(message, state, session, user)


async def on_image(
    message: Message,
    bot: Bot,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    parser: TransactionParser,
    clock: Clock,
) -> None:
    """Screenshot: rasmni LLM o‘qiydi, keyin oqim matnli xabardagi bilan bir xil."""
    if not parser.supports_screenshots:
        await message.answer(texts.PHOTO_NEEDS_AI)
        return
    file = message.photo[-1] if message.photo else message.document
    if (file.file_size or 0) > MAX_IMAGE_BYTES:
        await message.answer(texts.PHOTO_TOO_LARGE)
        return

    with suppress(TelegramAPIError):
        await bot.send_chat_action(message.chat.id, "typing")
    try:
        buffer = await bot.download(file)
    except TelegramAPIError as error:
        logger.warning("Screenshot not downloaded: %s", type(error).__name__)
        await message.answer(texts.PHOTO_FAILED)
        return
    # Fayl sifatida yuborilgan BMP, TIFF kabi rasmlar JPEG’ga o‘giriladi.
    prepared = to_supported_image(buffer.getvalue(), image_type(message))
    if prepared is None:
        await message.answer(texts.PHOTO_FORMAT)
        return
    try:
        categories = [category.name for category in await ts.list_categories(session, user.id)]
        draft = await parser.parse_screenshot(ImageInput(*prepared), user.tz, clock(), categories=categories)
    except LLMError as error:
        logger.warning("Screenshot not read: %s", type(error).__name__)
        await message.answer(texts.PHOTO_FAILED)
        return

    if contains_secret_code(draft.raw_text):
        with suppress(TelegramAPIError):
            await message.delete()
        await message.answer(texts.SECRET_WARNING)
        return
    if draft.amount is None and draft.transaction_type is None and draft.card_last4 is None:
        await message.answer(texts.PHOTO_NO_TRANSACTION)
        return
    await _start_draft(message, state, session, user, draft)


async def on_pdf(
    message: Message,
    bot: Bot,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    parser: TransactionParser,
    clock: Clock,
) -> None:
    """PDF chek: matni olinadi va oddiy matnli xabar kabi o‘qiladi (AI kaliti shart emas)."""
    document = message.document
    if (document.file_size or 0) > MAX_IMAGE_BYTES:
        await message.answer(texts.FILE_TOO_LARGE)
        return
    try:
        buffer = await bot.download(document)
        text = await asyncio.to_thread(extract_pdf_text, buffer.getvalue())
    except (PdfError, TelegramAPIError) as error:
        logger.warning("PDF not read: %s", type(error).__name__)
        await message.answer(texts.PDF_FAILED)
        return
    if not text:
        await message.answer(texts.PDF_NO_TEXT)
        return
    if len(text) > MAX_PDF_TEXT_LENGTH:
        await message.answer(texts.PDF_TOO_LONG)
        return
    await _process_text(message, state, session, user, parser, clock, text, "pdf", texts.PDF_NO_TRANSACTION)


async def on_image_while_busy(message: Message) -> None:
    await message.answer(texts.BUSY)


async def on_unsupported(message: Message) -> None:
    await message.answer(texts.TEXT_ONLY)


async def on_text_instead_of_button(message: Message) -> None:
    await message.answer(texts.USE_BUTTONS)


# --------------------------------------------------------------------------- #
# Yetishmagan ma’lumot va tahrirlash
# --------------------------------------------------------------------------- #


async def on_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await remove_buttons(callback)
    message = callback_message(callback)
    if message is not None:
        await message.answer(texts.CANCELLED)


async def on_amount(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    amount = parse_amount(message.text or "")
    if amount is None or amount <= 0 or amount > MAX_AMOUNT:
        await message.answer(texts.BAD_AMOUNT, reply_markup=kb.cancel_only())
        return
    draft = await load_draft(state)
    draft.amount = amount
    await store_draft(state, draft)
    await advance(message, state, session, user)


async def on_type(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    draft = await load_draft(state)
    draft.transaction_type = "income" if callback.data.endswith("income") else "expense"
    await store_draft(state, draft)
    await remove_buttons(callback)
    await advance(callback_message(callback), state, session, user)


async def _set_date(
    target: Message, state: FSMContext, session: AsyncSession, user: User, value: datetime, now: datetime
) -> None:
    if value > now + timedelta(minutes=5):
        await target.answer(texts.FUTURE_DATE, reply_markup=kb.date_choice())
        return
    draft = await load_draft(state)
    draft.occurred_at = value
    await store_draft(state, draft)
    await advance(target, state, session, user)


async def on_date_button(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, clock: Clock
) -> None:
    now = clock()
    value = now - timedelta(days=1) if callback.data.endswith("yesterday") else now
    await remove_buttons(callback)
    await _set_date(callback_message(callback), state, session, user, value, now)


async def on_date_text(
    message: Message, state: FSMContext, session: AsyncSession, user: User, clock: Clock
) -> None:
    now = clock()
    value = parse_user_datetime(message.text or "", user.tz, now)
    if value is None:
        await message.answer(texts.BAD_DATE, reply_markup=kb.date_choice())
        return
    await _set_date(message, state, session, user, value, now)


async def on_duplicate_accepted(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
) -> None:
    await state.update_data(duplicate_accepted=True)
    await remove_buttons(callback)
    await advance(callback_message(callback), state, session, user)


async def on_edit(callback: CallbackQuery, state: FSMContext) -> None:
    draft = await load_draft(state)
    await state.set_state(TxFlow.edit_menu)
    await remove_buttons(callback)
    await callback_message(callback).answer(
        texts.EDIT_MENU, reply_markup=kb.edit_menu(draft.transaction_type == "income")
    )


async def on_edit_choice(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    action = callback.data.rsplit(":", 1)[1]
    message = callback_message(callback)
    await remove_buttons(callback)
    if action == "amount":
        await state.set_state(TxFlow.waiting_amount)
        await message.answer(texts.EDIT_AMOUNT, reply_markup=kb.cancel_only())
    elif action == "merchant":
        await state.set_state(TxFlow.waiting_merchant)
        await message.answer(texts.EDIT_MERCHANT, reply_markup=kb.cancel_only())
    elif action == "date":
        await state.set_state(TxFlow.waiting_date)
        await message.answer(texts.ASK_DATE, reply_markup=kb.date_choice())
    else:
        if action == "type":
            draft = await load_draft(state)
            draft.transaction_type = "expense" if draft.transaction_type == "income" else "income"
            await store_draft(state, draft)
        await advance(message, state, session, user)


async def on_merchant(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    name = " ".join((message.text or "").split())
    if not 1 <= len(name) <= 64:
        await message.answer(texts.BAD_MERCHANT, reply_markup=kb.cancel_only())
        return
    draft = await load_draft(state)
    draft.merchant = mask_card_numbers(name)[0]
    await store_draft(state, draft)
    await advance(message, state, session, user)


# --------------------------------------------------------------------------- #
# 1-savol: nima uchun qilindi?
# --------------------------------------------------------------------------- #


async def on_note(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    note_analyzer: NoteAnalyzer,
    clock: Clock,
) -> None:
    text = (message.text or "").strip()
    incoming = _as_notification(message, text, user, clock())
    if incoming is not None:
        # Oldingi tranzaksiya tugallanmay turib yana bir karta xabari keldi.
        pending = Leg.from_parsed(await load_draft(state))
        if is_transfer_pair(pending, Leg.from_parsed(incoming)):
            sent, received = split_pair(pending, Leg.from_parsed(incoming))
            await state.update_data(pair_prompt=True)
            await message.answer(
                texts.TRANSFER_SUSPECTED_PENDING.format(route=render.transfer_route(sent, received)),
                reply_markup=kb.transfer_choice("tx:trp"),
            )
            return
        await message.answer(texts.FINISH_PENDING_FIRST, reply_markup=kb.draft_actions())
        return
    if len(text) > MAX_NOTE_LENGTH:
        await message.answer(texts.NOTE_TOO_LONG)
        return

    note = mask_card_numbers(text)[0]
    await state.update_data(note=note)
    await ask_category(message, state, session, user, note_analyzer)


def _as_notification(message: Message, text: str, user: User, now: datetime) -> ParsedTransaction | None:
    """Matn izoh emas, yana bir karta xabari bo‘lsa, uni o‘qib qaytaradi."""
    source_hint, forwarded_at = forward_info(message)
    parsed = _rules.parse(text, user.tz, now, source_hint=source_hint)
    is_card_message = parsed.amount is not None and parsed.source in ("cardxabar", "humo")
    if message.forward_origin is None and not is_card_message:
        return None
    if parsed.occurred_at is None and forwarded_at is not None:
        parsed.occurred_at = forwarded_at
    return parsed


# --------------------------------------------------------------------------- #
# O‘z kartalar orasidagi o‘tkazma: hisobotga yozilmaydi
# --------------------------------------------------------------------------- #


async def on_own_transfer(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await remove_buttons(callback)
    await callback_message(callback).answer(texts.OWN_TRANSFER_SKIPPED)


async def on_pending_pair_choice(callback: CallbackQuery, state: FSMContext, callback_answer: CallbackAnswer) -> None:
    data = await state.get_data()
    if not data.get("pair_prompt"):
        # Bu savol boshqa (eski) qoralamaga tegishli edi.
        callback_answer.text = texts.STALE_BUTTON
        callback_answer.show_alert = True
        return
    await remove_buttons(callback)
    message = callback_message(callback)
    if callback.data.endswith(":yes"):
        await state.clear()
        await message.answer(texts.TRANSFER_DROPPED)
    else:
        await state.update_data(pair_prompt=False)
        await message.answer(texts.FINISH_PENDING_FIRST, reply_markup=kb.draft_actions())


async def on_saved_pair_choice(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    data = await state.get_data()
    await remove_buttons(callback)
    message = callback_message(callback)
    if callback.data.endswith(":yes"):
        await ts.delete_transaction(session, user.id, int(data["transfer_counterpart_id"]))
        await state.clear()
        await message.answer(texts.TRANSFER_DROPPED_WITH_SAVED)
    else:
        await state.update_data(transfer_declined=True)
        await advance(message, state, session, user)


# --------------------------------------------------------------------------- #
# 2-savol: qaysi turga kiradi?
# --------------------------------------------------------------------------- #


async def ask_category(
    target: Message, state: FSMContext, session: AsyncSession, user: User, note_analyzer: NoteAnalyzer
) -> None:
    data = await state.get_data()
    draft = ParsedTransaction.model_validate(data["draft"])
    categories = await ts.list_categories(session, user.id)

    analysis = await note_analyzer.analyze(
        data.get("note") or "", draft.merchant, draft.transaction_type, [category.name for category in categories]
    )
    suggestion = await ts.suggest_category(
        session, user.id, draft.merchant, analysis.category_guess or draft.category_guess
    )

    await state.update_data(analysis=analysis.model_dump(mode="json"))
    await state.set_state(TxFlow.waiting_category)
    await target.answer(
        texts.ASK_CATEGORY, reply_markup=kb.category_choice(categories, suggestion.id if suggestion else None)
    )


async def on_category(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, callback_answer: CallbackAnswer
) -> None:
    category = await ts.get_category(session, user.id, int(callback.data.rsplit(":", 1)[1]))
    if category is None:
        callback_answer.text = texts.CATEGORY_NOT_FOUND
        callback_answer.show_alert = True
        return
    await state.update_data(category_id=category.id)
    await remove_buttons(callback)
    await ask_card(callback_message(callback), state, session, user)


async def on_new_category_request(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TxFlow.waiting_new_category)
    await remove_buttons(callback)
    await callback_message(callback).answer(texts.ASK_NEW_CATEGORY, reply_markup=kb.cancel_only())


async def on_new_category_name(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    emoji, name = split_emoji(message.text or "")
    try:
        category = await ts.add_category(session, user.id, name, emoji)
    except ts.ServiceError as error:
        await message.answer(f"⚠️ {error}", reply_markup=kb.cancel_only())
        return
    await state.update_data(category_id=category.id)
    await ask_card(message, state, session, user)


# --------------------------------------------------------------------------- #
# 3-savol: qaysi kartadan?
# --------------------------------------------------------------------------- #


async def ask_card(target: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    draft = await load_draft(state)
    cards = await ts.list_cards(session, user.id, only_active=True)
    matching = next((card for card in cards if draft.card_last4 and card.card_last4 == draft.card_last4), None)
    if matching is not None:
        # Xabardagi karta ro‘yxatda bor: so‘rab o‘tirmasdan shu karta bilan saqlanadi.
        await save(target, state, session, user, matching.id)
        return

    text = texts.ASK_CARD_INCOME if draft.transaction_type == "income" else texts.ASK_CARD_EXPENSE
    await state.set_state(TxFlow.waiting_card)
    await target.answer(text, reply_markup=kb.card_choice(cards))


async def save(
    target: Message, state: FSMContext, session: AsyncSession, user: User, card_id: int | None
) -> bool:
    data = await state.get_data()
    draft = ParsedTransaction.model_validate(data["draft"])
    analysis = NoteAnalysis.model_validate(data.get("analysis") or {})
    try:
        transaction = await ts.create_transaction(
            session, user, draft, data.get("note"), data.get("category_id"), card_id, analysis
        )
    except ts.ServiceError as error:
        await target.answer(f"⚠️ {error}")
        return False
    await state.clear()
    await target.answer(render.saved_summary(transaction))
    return True


async def on_card(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, callback_answer: CallbackAnswer
) -> None:
    choice = callback.data.rsplit(":", 1)[1]
    card_id: int | None = None
    if choice != "none":
        card = await ts.get_card(session, user.id, int(choice))
        if card is None:
            callback_answer.text = texts.CARD_NOT_FOUND
            callback_answer.show_alert = True
            return
        card_id = card.id
    if await save(callback_message(callback), state, session, user, card_id):
        await remove_buttons(callback)


async def on_new_card_request(callback: CallbackQuery, state: FSMContext) -> None:
    draft = await load_draft(state)
    await remove_buttons(callback)
    message = callback_message(callback)
    if draft.card_last4:
        await state.update_data(new_card_last4=draft.card_last4)
        await state.set_state(TxFlow.waiting_new_card_name)
        await message.answer(texts.ASK_NEW_CARD_NAME.format(last4=draft.card_last4), reply_markup=kb.cancel_only())
    else:
        await state.set_state(TxFlow.waiting_new_card_last4)
        await message.answer(texts.ASK_LAST4, reply_markup=kb.cancel_only())


async def on_new_card_last4(message: Message, state: FSMContext) -> None:
    last4 = await read_last4(message)
    if last4 is None:
        return
    await state.update_data(new_card_last4=last4)
    await state.set_state(TxFlow.waiting_new_card_name)
    await message.answer(texts.ASK_NEW_CARD_NAME.format(last4=last4), reply_markup=kb.cancel_only())


async def on_new_card_name(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    data = await state.get_data()
    draft = ParsedTransaction.model_validate(data["draft"])
    last4 = data["new_card_last4"]
    network = draft.card_network if draft.card_last4 == last4 else "Unknown"
    name = mask_card_numbers(message.text or "")[0]
    try:
        card = await ts.add_card(session, user.id, name=name, last4=last4, network=network, currency=draft.currency)
    except ts.ServiceError as error:
        await message.answer(f"⚠️ {error}")
        await ask_card(message, state, session, user)
        return
    await save(message, state, session, user, card.id)


# --------------------------------------------------------------------------- #
# /delete
# --------------------------------------------------------------------------- #


async def cmd_delete(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    await state.clear()
    last = await ts.get_last_transaction(session, user.id)
    if last is None:
        await message.answer(texts.NO_TRANSACTIONS)
        return
    line = render.transaction_line(last, user.tz)
    await message.answer(texts.DELETE_CONFIRM.format(line=line), reply_markup=kb.delete_confirm(last.id))


async def on_delete_confirmed(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    deleted = await ts.delete_transaction(session, user.id, int(callback.data.rsplit(":", 1)[1]))
    await remove_buttons(callback)
    await callback_message(callback).answer(texts.DELETED if deleted else texts.NO_TRANSACTIONS)


async def on_delete_declined(callback: CallbackQuery) -> None:
    await remove_buttons(callback)
    await callback_message(callback).answer(texts.KEPT)


async def on_stale_button(callback: CallbackQuery, callback_answer: CallbackAnswer) -> None:
    callback_answer.text = texts.STALE_BUTTON
    callback_answer.show_alert = True


async def on_unknown_command(message: Message) -> None:
    await message.answer(texts.HELP)


def create_router() -> Router:
    router = Router(name="transactions")
    message, callback = router.message, router.callback_query
    message.register(cmd_add, Command("add"))
    message.register(cmd_delete, Command("delete"))
    message.register(on_unknown_command, F.text.startswith("/"))

    callback.register(on_cancel, F.data == "tx:cancel", StateFilter(TxFlow))
    callback.register(on_type, F.data.startswith("tx:type:"), TxFlow.waiting_type)
    callback.register(on_date_button, F.data.startswith("tx:date:"), TxFlow.waiting_date)
    callback.register(on_duplicate_accepted, F.data == "tx:dup:save", TxFlow.waiting_duplicate)
    callback.register(on_edit, F.data == "tx:edit", TxFlow.waiting_note)
    callback.register(on_own_transfer, F.data == "tx:own", TxFlow.waiting_note)
    callback.register(on_pending_pair_choice, F.data.regexp(r"^tx:trp:(yes|no)$"), TxFlow.waiting_note)
    callback.register(on_saved_pair_choice, F.data.regexp(r"^tx:tr:(yes|no)$"), TxFlow.waiting_transfer)
    callback.register(on_edit_choice, F.data.startswith("tx:ed:"), TxFlow.edit_menu)
    callback.register(on_new_category_request, F.data == "tx:cat:new", TxFlow.waiting_category)
    callback.register(on_category, F.data.regexp(r"^tx:cat:\d+$"), TxFlow.waiting_category)
    callback.register(on_new_card_request, F.data == "tx:card:new", TxFlow.waiting_card)
    callback.register(on_card, F.data.regexp(r"^tx:card:(\d+|none)$"), TxFlow.waiting_card)
    callback.register(on_stale_button, F.data.startswith("tx:"))
    callback.register(on_delete_confirmed, F.data.regexp(r"^del:yes:\d+$"))
    callback.register(on_delete_declined, F.data == "del:no")

    message.register(on_amount, TxFlow.waiting_amount, PLAIN_TEXT)
    message.register(on_date_text, TxFlow.waiting_date, PLAIN_TEXT)
    message.register(on_merchant, TxFlow.waiting_merchant, PLAIN_TEXT)
    message.register(on_note, TxFlow.waiting_note, PLAIN_TEXT)
    message.register(on_new_category_name, TxFlow.waiting_new_category, PLAIN_TEXT)
    message.register(on_new_card_last4, TxFlow.waiting_new_card_last4, PLAIN_TEXT)
    message.register(on_new_card_name, TxFlow.waiting_new_card_name, PLAIN_TEXT)
    message.register(on_text_instead_of_button, StateFilter(*BUTTON_STATES), PLAIN_TEXT)
    message.register(on_image, StateFilter(None, TxFlow.waiting_input), IMAGE)
    message.register(on_pdf, StateFilter(None, TxFlow.waiting_input), PDF)
    message.register(on_image_while_busy, IMAGE | PDF)
    message.register(on_new_message, StateFilter(None, TxFlow.waiting_input), PLAIN_TEXT)
    message.register(on_unsupported)
    return router
