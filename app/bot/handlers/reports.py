"""/report, /stat va /export.

/report darhol shu oyning hamma kartalar bo‘yicha hisobotini ko‘rsatadi. Davr, karta va
tur filtri hisobot ostidagi tugmalarda; har biri bir bosishda o‘zgaradi va qolganlari saqlanadi.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
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


@dataclass(frozen=True)
class View:
    """Callback’dan o‘qilgan hisobot ko‘rinishi."""

    period: Period
    key: kb.ReportKey
    report_filter: rs.ReportFilter
    filter_line: str  # faqat faol filtrlar; filtr bo‘lmasa bo‘sh


async def _view(
    session: AsyncSession, user: User, clock: Clock, code: str, card_id: int, category_id: int
) -> View | None:
    """Davr va filtrlarni tekshiradi. Begona karta yoki tur ID’si hech narsa topmaydi."""
    try:
        period = period_range(code, user.tz, clock())
    except ValueError:
        return None

    card_label, category_label = texts.ALL_CARDS, f"🏷 {texts.ALL_CATEGORIES}"
    active: list[str] = []
    if card_id:
        card = await ts.get_card(session, user.id, card_id)
        card_label = card.name if card else texts.UNKNOWN_CARD
        active.append(f"💳 {render.card_title(card) if card else texts.UNKNOWN_CARD}")
    if category_id:
        category = await ts.get_category(session, user.id, category_id)
        category_label = f"{category.emoji} {category.name}" if category else texts.UNKNOWN_CATEGORY
        active.append(category_label)

    return View(
        period=period,
        key=kb.ReportKey(code, period.label, card_id, card_label, category_id, category_label),
        report_filter=rs.ReportFilter(
            start=period.start, end=period.end, card_id=card_id or None, category_id=category_id or None
        ),
        filter_line=" · ".join(active),
    )


async def _view_from_callback(
    callback: CallbackQuery, session: AsyncSession, user: User, clock: Clock, callback_answer: CallbackAnswer
) -> View | None:
    _, code, card_raw, category_raw, *_ = callback.data.split(":")
    view = await _view(session, user, clock, code, int(card_raw), int(category_raw))
    if view is None:
        callback_answer.text = texts.STALE_BUTTON
    return view


async def _summary(session: AsyncSession, user: User, view: View):
    report = await rs.build_report(session, user.id, view.report_filter, user.preferred_currency)
    text = render.report_text(view.period.label, view.filter_line, report, user.tz)
    return text, kb.report_summary_actions(view.key, report.count)


async def cmd_report(message: Message, state: FSMContext, session: AsyncSession, user: User, clock: Clock) -> None:
    await state.clear()
    view = await _view(session, user, clock, "m", 0, 0)
    text, markup = await _summary(session, user, view)
    await message.answer(text, reply_markup=markup)


async def on_view(
    callback: CallbackQuery, session: AsyncSession, user: User, clock: Clock, callback_answer: CallbackAnswer
) -> None:
    view = await _view_from_callback(callback, session, user, clock, callback_answer)
    if view is None:
        return
    page = int(callback.data.rsplit(":", 1)[1])
    total = await rs.count_transactions(session, user.id, view.report_filter) if page else 0
    if page and total:
        pages = ceil(total / PAGE_SIZE)
        page = min(page, pages)
        transactions = await rs.fetch_transactions(
            session, user.id, view.report_filter, limit=PAGE_SIZE, offset=(page - 1) * PAGE_SIZE
        )
        text = render.transactions_page(view.period.label, view.filter_line, transactions, page, pages, user.tz)
        markup = kb.report_list_actions(view.key, page, pages)
    else:
        text, markup = await _summary(session, user, view)
    await edit_or_send(callback, text, markup)


async def on_pick_period(
    callback: CallbackQuery, session: AsyncSession, user: User, clock: Clock, callback_answer: CallbackAnswer
) -> None:
    view = await _view_from_callback(callback, session, user, clock, callback_answer)
    if view is None:
        return
    months = await rs.list_months(session, user.id, user.tz, clock())
    await edit_or_send(callback, texts.ASK_PERIOD, kb.report_periods(view.key, months))


async def on_pick_card(
    callback: CallbackQuery, session: AsyncSession, user: User, clock: Clock, callback_answer: CallbackAnswer
) -> None:
    view = await _view_from_callback(callback, session, user, clock, callback_answer)
    if view is None:
        return
    cards = await ts.list_cards(session, user.id)
    await edit_or_send(callback, texts.ASK_REPORT_CARD, kb.report_cards(view.key, cards))


async def on_pick_category(
    callback: CallbackQuery, session: AsyncSession, user: User, clock: Clock, callback_answer: CallbackAnswer
) -> None:
    view = await _view_from_callback(callback, session, user, clock, callback_answer)
    if view is None:
        return
    categories = await ts.list_categories(session, user.id)
    await edit_or_send(callback, texts.ASK_REPORT_CATEGORY, kb.report_categories(view.key, categories))


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
    view = await _view_from_callback(callback, session, user, clock, callback_answer)
    if view is None:
        return
    sent = await _send_csv(callback_message(callback), session, user, view.period, view.report_filter, clock())
    if not sent:
        callback_answer.text = texts.REPORT_EMPTY
        callback_answer.show_alert = True


async def on_report_picture(
    callback: CallbackQuery, session: AsyncSession, user: User, clock: Clock, callback_answer: CallbackAnswer
) -> None:
    view = await _view_from_callback(callback, session, user, clock, callback_answer)
    if view is None:
        return
    report = await rs.build_report(session, user.id, view.report_filter, user.preferred_currency)
    if report.count == 0:
        callback_answer.text = texts.REPORT_EMPTY
        callback_answer.show_alert = True
        return
    main, others = report.currencies[0], [item.currency for item in report.currencies[1:]]
    try:
        image = await asyncio.to_thread(render_report_image, texts.REPORT_HEADING, view.period.label, main, others)
    except Exception as error:  # noqa: BLE001 - rasm chiqmasa ham bot ishlashda davom etadi
        logger.warning("Report picture failed: %s", type(error).__name__)
        callback_answer.text = texts.PICTURE_FAILED
        callback_answer.show_alert = True
        return
    caption = f"📊 {view.period.label}" + (f"\n{view.filter_line}" if view.filter_line else "")
    await callback_message(callback).answer_photo(BufferedInputFile(image, filename="hisobot.png"), caption=caption)


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
    view = await _view(session, user, clock, callback.data.split(":", 1)[1], 0, 0)
    if view is None:
        callback_answer.text = texts.STALE_BUTTON
        return
    message = callback_message(callback)
    if not await _send_csv(message, session, user, view.period, view.report_filter, clock()):
        await message.answer(f"📄 {view.period.label}: {texts.REPORT_EMPTY}")


def create_router() -> Router:
    router = Router(name="reports")
    message, callback = router.message, router.callback_query
    key = r"[\w-]+:\d+:\d+"

    message.register(cmd_report, Command("report"))
    message.register(cmd_stat, Command("stat"))
    message.register(cmd_export, Command("export"))

    callback.register(on_view, F.data.regexp(rf"^rpv:{key}:\d+$"))
    callback.register(on_pick_period, F.data.regexp(rf"^rpp:{key}$"))
    callback.register(on_pick_card, F.data.regexp(rf"^rpc:{key}$"))
    callback.register(on_pick_category, F.data.regexp(rf"^rpg:{key}$"))
    callback.register(on_report_csv, F.data.regexp(rf"^rpx:{key}$"))
    callback.register(on_report_picture, F.data.regexp(rf"^rpi:{key}$"))
    callback.register(on_export, F.data.regexp(r"^ex:[\w-]+$"))
    return router
