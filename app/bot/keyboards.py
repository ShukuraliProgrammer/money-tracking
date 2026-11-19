"""Inline klaviaturalar."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot import texts
from app.models import Card, Category
from app.utils.dates import month_label


def _button(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _cancel_row() -> list[InlineKeyboardButton]:
    return [_button(texts.BTN_CANCEL, "tx:cancel")]


# --- Tranzaksiya oqimi -------------------------------------------------------- #


def draft_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_button(texts.BTN_EDIT, "tx:edit"), *_cancel_row()]])


def cancel_only() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[_cancel_row()])


def type_choice() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button(texts.BTN_EXPENSE, "tx:type:expense"), _button(texts.BTN_INCOME, "tx:type:income")],
            _cancel_row(),
        ]
    )


def date_choice() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button(texts.BTN_NOW, "tx:date:now"), _button(texts.BTN_YESTERDAY, "tx:date:yesterday")],
            _cancel_row(),
        ]
    )


def duplicate_choice() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_button(texts.BTN_SAVE_ANYWAY, "tx:dup:save")], [_button(texts.BTN_DROP, "tx:cancel")]]
    )


def edit_menu(is_income: bool) -> InlineKeyboardMarkup:
    flip = texts.BTN_TO_EXPENSE if is_income else texts.BTN_TO_INCOME
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button(texts.BTN_EDIT_AMOUNT, "tx:ed:amount"), _button(texts.BTN_EDIT_MERCHANT, "tx:ed:merchant")],
            [_button(texts.BTN_EDIT_DATE, "tx:ed:date"), _button(flip, "tx:ed:type")],
            [_button(texts.BTN_BACK, "tx:ed:back")],
        ]
    )


def category_choice(categories: list[Category], suggested_id: int | None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        star = "⭐ " if category.id == suggested_id else ""
        builder.add(_button(f"{star}{category.emoji} {category.name}", f"tx:cat:{category.id}"))
    builder.adjust(2)
    builder.row(_button(texts.BTN_NEW_CATEGORY, "tx:cat:new"))
    builder.row(*_cancel_row())
    return builder.as_markup()


def card_choice(cards: list[Card], matching_id: int | None) -> InlineKeyboardMarkup:
    rows = []
    for card in cards:
        mark = "✓ " if card.id == matching_id else ""
        rows.append([_button(f"💳 {mark}{card.name} ****{card.card_last4}", f"tx:card:{card.id}")])
    rows.append([_button(texts.BTN_NEW_CARD, "tx:card:new"), _button(texts.BTN_NO_CARD, "tx:card:none")])
    rows.append(_cancel_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def delete_confirm(transaction_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button(texts.BTN_DELETE_YES, f"del:yes:{transaction_id}"), _button(texts.BTN_NO, "del:no")]
        ]
    )


# --- Kartalar ------------------------------------------------------------------ #


def cards_menu(cards: list[Card]) -> InlineKeyboardMarkup:
    rows = []
    for card in cards:
        toggle = "⏸" if card.is_active else "▶️"
        rows.append(
            [
                _button(f"{toggle} {card.name}", f"card:toggle:{card.id}"),
                _button(f"🗑 {card.name}", f"card:del:{card.id}"),
            ]
        )
    rows.append([_button(texts.BTN_ADD_CARD, "card:add")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def card_delete_confirm(card_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_button(texts.BTN_YES, f"card:delok:{card_id}"), _button(texts.BTN_NO, "card:list")]]
    )


def network_choice() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button("Uzcard", "card:net:Uzcard"), _button("Humo", "card:net:Humo")],
            [_button("Visa", "card:net:Visa"), _button("Mastercard", "card:net:Mastercard")],
            [_button(texts.BTN_OTHER_NETWORK, "card:net:Unknown")],
        ]
    )


def skip_bank() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_button(texts.BTN_SKIP, "card:bank:skip")]])


def currency_choice(prefix: str) -> InlineKeyboardMarkup:
    codes = ("UZS", "USD", "EUR", "RUB")
    return InlineKeyboardMarkup(inline_keyboard=[[_button(code, f"{prefix}:{code}") for code in codes]])


# --- Turlar ---------------------------------------------------------------------- #


def categories_menu(categories: list[Category]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        if not category.is_default:
            builder.add(_button(f"🗑 {category.name}", f"cat:del:{category.id}"))
    builder.adjust(2)
    builder.row(_button(texts.BTN_NEW_CATEGORY, "cat:add"))
    return builder.as_markup()


# --- Hisobot ----------------------------------------------------------------------- #


def report_periods(months: list[tuple[int, int]]) -> InlineKeyboardMarkup:
    """``months`` — joriy oydan boshlab, eng yangisi birinchi."""
    builder = InlineKeyboardBuilder()
    builder.row(_button(texts.BTN_TODAY, "rpp:d"), _button(texts.BTN_WEEK, "rpp:w"))
    builder.row(_button(texts.BTN_THIS_MONTH.format(label=month_label(*months[0])), "rpp:m"))
    if len(months) > 1:
        builder.row(_button(texts.BTN_PREV_MONTH.format(label=month_label(*months[1])), "rpp:pm"))
    older = [_button(month_label(year, month), f"rpp:{year:04d}-{month:02d}") for year, month in months[2:8]]
    for index in range(0, len(older), 2):
        builder.row(*older[index : index + 2])
    builder.row(_button(texts.BTN_ALL_TIME, "rpp:all"))
    return builder.as_markup()


def report_cards(period: str, cards: list[Card]) -> InlineKeyboardMarkup:
    rows = [[_button(f"💳 {texts.ALL_CARDS}", f"rpc:{period}:0")]]
    rows += [[_button(f"{card.name} ****{card.card_last4}", f"rpc:{period}:{card.id}")] for card in cards]
    rows.append([_button(texts.BTN_PERIOD, "rp:start")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def report_categories(period: str, card_id: int, categories: list[Category]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.add(_button(f"{category.emoji} {category.name}", f"rpv:{period}:{card_id}:{category.id}:0"))
    builder.adjust(2)
    markup = builder.as_markup()
    markup.inline_keyboard.insert(0, [_button(f"🏷 {texts.ALL_CATEGORIES}", f"rpv:{period}:{card_id}:0:0")])
    markup.inline_keyboard.append([_button(texts.BTN_BACK, f"rpp:{period}")])
    return markup


def report_summary_actions(period: str, card_id: int, category_id: int, count: int) -> InlineKeyboardMarkup:
    key = f"{period}:{card_id}:{category_id}"
    rows = []
    if count:
        rows.append([_button(texts.BTN_TRANSACTIONS.format(count=count), f"rpv:{key}:1")])
        rows.append([_button(texts.BTN_PICTURE, f"rpi:{key}"), _button(texts.BTN_CSV, f"rpx:{key}")])
    rows.append([_button(texts.BTN_FILTER, f"rpp:{period}"), _button(texts.BTN_PERIOD, "rp:start")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def report_list_actions(period: str, card_id: int, category_id: int, page: int, pages: int) -> InlineKeyboardMarkup:
    key = f"{period}:{card_id}:{category_id}"
    navigation = []
    if page > 1:
        navigation.append(_button("◀️", f"rpv:{key}:{page - 1}"))
    if page < pages:
        navigation.append(_button("▶️", f"rpv:{key}:{page + 1}"))
    rows = [navigation] if navigation else []
    rows.append([_button(texts.BTN_SUMMARY, f"rpv:{key}:0"), _button(texts.BTN_CSV, f"rpx:{key}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def export_periods() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button(texts.BTN_EXPORT_THIS_MONTH, "ex:m"), _button(texts.BTN_EXPORT_PREV_MONTH, "ex:pm")],
            [_button(texts.BTN_LAST_30, "ex:30"), _button(texts.BTN_ALL_TIME, "ex:all")],
        ]
    )


# --- Sozlamalar ---------------------------------------------------------------------- #


def settings_menu(daily_enabled: bool, weekly_enabled: bool, monthly_enabled: bool) -> InlineKeyboardMarkup:
    daily = texts.ON if daily_enabled else texts.OFF
    weekly = texts.ON if weekly_enabled else texts.OFF
    monthly = texts.ON if monthly_enabled else texts.OFF
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button(texts.BTN_TIMEZONE, "set:tz"), _button(texts.BTN_CURRENCY, "set:cur")],
            [_button(texts.BTN_DAILY.format(state=daily), "set:daily")],
            [_button(texts.BTN_WEEKLY.format(state=weekly), "set:weekly")],
            [_button(texts.BTN_NOTIFICATIONS.format(state=monthly), "set:notif")],
            [_button(texts.BTN_WIPE, "set:wipe")],
        ]
    )


TIMEZONES = ("Asia/Tashkent", "Asia/Samarkand", "Asia/Almaty", "Europe/Moscow", "Europe/Istanbul", "Asia/Dubai")


def timezone_choice() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for name in TIMEZONES:
        builder.add(_button(name, f"set:tz:{name}"))
    builder.adjust(2)
    builder.row(_button(texts.BTN_BACK, "set:menu"))
    return builder.as_markup()


def wipe_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_button(texts.BTN_WIPE_YES, "set:wipe:yes")], [_button(texts.BTN_NO, "set:menu")]]
    )
