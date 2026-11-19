"""/report, /stat va /export.

Hisobot uch bosqichda tanlanadi: davr → karta → tur. Natijani tranzaksiyalar
ro‘yxati (har birining izohi bilan) yoki CSV fayl sifatida ko‘rish mumkin.
"""

from __future__ import annotations

import asyncio
import logging
from math import ceil

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from aiogram.utils.callback_answer import CallbackAnswer
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards as kb
from app.bot import render, texts
from app.bot.common import Clock, callback_message, edit_or_send
from app.models import User
from app.services import report_service as rs
from app.services import transaction_service as ts
from app.services.chart_service import render_report_image
from app.services.export_service import build_csv, export_filename
from app.utils.dates import Period, period_range

PAGE_SIZE = 10

logger = logging.getLogger(__name__)


async def _periods_view(session: AsyncSession, user: User, clock: Clock):
    months = await rs.list_months(session, user.id, user.tz, clock())
    return texts.ASK_PERIOD, kb.report_periods(months)


async def cmd_report(message: Message, state: FSMContext, session: AsyncSession, user: User, clock: Clock) -> None:
    await state.clear()
    text, markup = await _periods_view(session, user, clock)
    await message.answer(text, reply_markup=markup)


async def on_report_start(callback: CallbackQuery, session: AsyncSession, user: User, clock: Clock) -> None:
    text, markup = await _periods_view(session, user, clock)
    await edit_or_send(callback, text, markup)


def _period(code: str, user: User, clock: Clock) -> Period | None:
    try:
        return period_range(code, user.tz, clock())
    except ValueError:
        return None


async def on_period(
    callback: CallbackQuery, session: AsyncSession, user: User, clock: Clock, callback_answer: CallbackAnswer
) -> None:
    code = callback.data.split(":", 1)[1]
    period = _period(code, user, clock)
    if period is None:
        callback_answer.text = texts.STALE_BUTTON
        return
    cards = await ts.list_cards(session, user.id)
    await edit_or_send(callback, f"📊 <b>{period.label}</b>\n{texts.ASK_REPORT_CARD}", kb.report_cards(code, cards))


async def on_card(
    callback: CallbackQuery, session: AsyncSession, user: User, clock: Clock, callback_answer: CallbackAnswer
) -> None:
    _, code, card_id = callback.data.split(":")
    period = _period(code, user, clock)
    if period is None:
        callback_answer.text = texts.STALE_BUTTON
        return
    categories = await ts.list_categories(session, user.id)
    await edit_or_send(
        callback,
        f"📊 <b>{period.label}</b>\n{texts.ASK_REPORT_CATEGORY}",
        kb.report_categories(code, int(card_id), categories),
    )


async def _filter(
    session: AsyncSession, user: User, period: Period, card_id: int, category_id: int
) -> tuple[rs.ReportFilter, str]:
    """Filtr va uning foydalanuvchiga ko‘rinadigan tavsifi. Begona ID’lar hech narsa topmaydi."""
    card_label, category_label = texts.ALL_CARDS, texts.ALL_CATEGORIES
    if card_id:
        card = await ts.get_card(session, user.id, card_id)
        card_label = render.card_title(card) if card else texts.UNKNOWN_CARD
    if category_id:
        category = await ts.get_category(session, user.id, category_id)
        category_label = f"{category.emoji} {category.name}" if category else texts.UNKNOWN_CATEGORY
    report_filter = rs.ReportFilter(
        start=period.start, end=period.end, card_id=card_id or None, category_id=category_id or None
    )
    return report_filter, f"💳 {card_label} · 🏷 {category_label}"


async def on_view(
    callback: CallbackQuery, session: AsyncSession, user: User, clock: Clock, callback_answer: CallbackAnswer
) -> None:
    _, code, card_raw, category_raw, page_raw = callback.data.split(":")
    card_id, category_id, page = int(card_raw), int(category_raw), int(page_raw)
    period = _period(code, user, clock)
    if period is None:
        callback_answer.text = texts.STALE_BUTTON
        return
    report_filter, filter_line = await _filter(session, user, period, card_id, category_id)

    total = await rs.count_transactions(session, user.id, report_filter) if page else 0
    if page and total:
        pages = ceil(total / PAGE_SIZE)
        page = min(page, pages)
        transactions = await rs.fetch_transactions(
            session, user.id, report_filter, limit=PAGE_SIZE, offset=(page - 1) * PAGE_SIZE
        )
        text = render.transactions_page(period.label, filter_line, transactions, page, pages, user.tz)
        markup = kb.report_list_actions(code, card_id, category_id, page, pages)
    else:
        report = await rs.build_report(session, user.id, report_filter, user.preferred_currency)
        text = render.report_text(period.label, filter_line, report, user.tz)
        markup = kb.report_summary_actions(code, card_id, category_id, report.count)
    await edit_or_send(callback, text, markup)


async def _send_csv(target: Message, session: AsyncSession, user: User, period: Period, report_filter, now) -> bool:
    transactions = await rs.fetch_transactions(session, user.id, report_filter)
    if not transactions:
        return False
    document = BufferedInputFile(build_csv(transactions, user.tz), filename=export_filename(period.label, now))
    caption = texts.CSV_CAPTION.format(label=period.label, count=len(transactions))
    await target.answer_document(document, caption=caption)
    return True


async def on_report_csv(
    callback: CallbackQuery, session: AsyncSession, user: User, clock: Clock, callback_answer: CallbackAnswer
) -> None:
    _, code, card_raw, category_raw = callback.data.split(":")
    period = _period(code, user, clock)
    if period is None:
        callback_answer.text = texts.STALE_BUTTON
        return
    report_filter, _ = await _filter(session, user, period, int(card_raw), int(category_raw))
    if not await _send_csv(callback_message(callback), session, user, period, report_filter, clock()):
        callback_answer.text = texts.REPORT_EMPTY
        callback_answer.show_alert = True


async def on_report_picture(
    callback: CallbackQuery, session: AsyncSession, user: User, clock: Clock, callback_answer: CallbackAnswer
) -> None:
    _, code, card_raw, category_raw = callback.data.split(":")
    period = _period(code, user, clock)
    if period is None:
        callback_answer.text = texts.STALE_BUTTON
        return
    report_filter, filter_line = await _filter(session, user, period, int(card_raw), int(category_raw))
    report = await rs.build_report(session, user.id, report_filter, user.preferred_currency)
    if report.count == 0:
        callback_answer.text = texts.REPORT_EMPTY
        callback_answer.show_alert = True
        return
    main, others = report.currencies[0], [item.currency for item in report.currencies[1:]]
    try:
        image = await asyncio.to_thread(render_report_image, texts.REPORT_HEADING, period.label, main, others)
    except Exception as error:  # noqa: BLE001 - rasm chiqmasa ham bot ishlashda davom etadi
        logger.warning("Report picture failed: %s", type(error).__name__)
        callback_answer.text = texts.PICTURE_FAILED
        callback_answer.show_alert = True
        return
    await callback_message(callback).answer_photo(
        BufferedInputFile(image, filename="hisobot.png"), caption=f"📊 {period.label}\n{filter_line}"
    )


async def cmd_stat(message: Message, state: FSMContext, session: AsyncSession, user: User, clock: Clock) -> None:
    await state.clear()
    stats = await rs.build_stats(session, user.id, user.tz, clock(), user.preferred_currency)
    await message.answer(render.stats_text(stats))


async def cmd_export(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.ASK_EXPORT_PERIOD, reply_markup=kb.export_periods())


async def on_export(
    callback: CallbackQuery, session: AsyncSession, user: User, clock: Clock, callback_answer: CallbackAnswer
) -> None:
    period = _period(callback.data.split(":", 1)[1], user, clock)
    if period is None:
        callback_answer.text = texts.STALE_BUTTON
        return
    report_filter = rs.ReportFilter(start=period.start, end=period.end)
    message = callback_message(callback)
    if not await _send_csv(message, session, user, period, report_filter, clock()):
        await message.answer(f"📄 {period.label}: {texts.REPORT_EMPTY}")


def create_router() -> Router:
    router = Router(name="reports")
    message, callback = router.message, router.callback_query

    message.register(cmd_report, Command("report"))
    message.register(cmd_stat, Command("stat"))
    message.register(cmd_export, Command("export"))

    callback.register(on_report_start, F.data == "rp:start")
    callback.register(on_period, F.data.regexp(r"^rpp:[\w-]+$"))
    callback.register(on_card, F.data.regexp(r"^rpc:[\w-]+:\d+$"))
    callback.register(on_view, F.data.regexp(r"^rpv:[\w-]+:\d+:\d+:\d+$"))
    callback.register(on_report_csv, F.data.regexp(r"^rpx:[\w-]+:\d+:\d+$"))
    callback.register(on_report_picture, F.data.regexp(r"^rpi:[\w-]+:\d+:\d+$"))
    callback.register(on_export, F.data.regexp(r"^ex:[\w-]+$"))
    return router
