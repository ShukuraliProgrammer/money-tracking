"""Inline klaviaturalar."""

from __future__ import annotations

from dataclasses import dataclass

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot import texts
from app.models import Card, Category
from app.utils.dates import month_label


def _button(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


# Telegram bir qatordagi tugmalarga teng joy beradi va sig‘magan yozuvni «K…k» qilib qisqartiradi.
# Shuning uchun yonma-yon faqat qisqa yozuvli tugmalar qo‘yiladi (telefon ekranida tekshirilgan chegara).
PAIR_LIMIT = 14


def _fit_rows(buttons: list[InlineKeyboardButton]) -> list[list[InlineKeyboardButton]]:
    """Qisqa yozuvli tugmalarni ikkitadan, uzunlarini alohida qatorga joylaydi."""
    rows: list[list[InlineKeyboardButton]] = []
    for button in buttons:
        fits = len(button.text) <= PAIR_LIMIT
        if fits and rows and len(rows[-1]) == 1 and len(rows[-1][0].text) <= PAIR_LIMIT:
            rows[-1].append(button)
        else:
            rows.append([button])
    return rows


def _cancel_row() -> list[InlineKeyboardButton]:
    return [_button(texts.BTN_CANCEL, "tx:cancel")]


# --- Tranzaksiya oqimi -------------------------------------------------------- #


def draft_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button(texts.BTN_EDIT, "tx:edit"), *_cancel_row()],
            [_button(texts.BTN_OWN_TRANSFER, "tx:own")],
        ]
    )


def transfer_choice(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button(texts.BTN_TRANSFER_YES, f"{prefix}:yes")],
            [_button(texts.BTN_TRANSFER_NO, f"{prefix}:no")],
        ]
    )


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
    fields = [
        _button(texts.BTN_EDIT_AMOUNT, "tx:ed:amount"),
        _button(texts.BTN_EDIT_MERCHANT, "tx:ed:merchant"),
        _button(texts.BTN_EDIT_DATE, "tx:ed:date"),
        _button(flip, "tx:ed:type"),
    ]
    return InlineKeyboardMarkup(inline_keyboard=[*_fit_rows(fields), [_button(texts.BTN_BACK, "tx:ed:back")]])


def category_choice(categories: list[Category], suggested_id: int | None) -> InlineKeyboardMarkup:
    choices = [
        _button(f"{'⭐ ' if category.id == suggested_id else ''}{category.emoji} {category.name}", f"tx:cat:{category.id}")
        for category in categories
    ]
    rows = [*_fit_rows(choices), [_button(texts.BTN_NEW_CATEGORY, "tx:cat:new")], _cancel_row()]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def card_choice(cards: list[Card]) -> InlineKeyboardMarkup:
    rows = [[_button(f"💳 {card.name} ****{card.card_last4}", f"tx:card:{card.id}")] for card in cards]
    rows.append([_button(texts.BTN_NEW_CARD, "tx:card:new"), _button(texts.BTN_NO_CARD, "tx:card:none")])
    rows.append(_cancel_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def delete_confirm(transaction_id: int) -> InlineKeyboardMarkup:
    choices = [_button(texts.BTN_DELETE_YES, f"del:yes:{transaction_id}"), _button(texts.BTN_NO, "del:no")]
    return InlineKeyboardMarkup(inline_keyboard=_fit_rows(choices))


# --- Kartalar ------------------------------------------------------------------ #


def cards_menu(cards: list[Card]) -> InlineKeyboardMarkup:
    rows = []
    for card in cards:
        toggle = "⏸" if card.is_active else "▶️"
        rows += _fit_rows(
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
    removable = [
        _button(f"🗑 {category.name}", f"cat:del:{category.id}") for category in categories if not category.is_default
    ]
    return InlineKeyboardMarkup(inline_keyboard=[*_fit_rows(removable), [_button(texts.BTN_NEW_CATEGORY, "cat:add")]])


# --- Hisobot ----------------------------------------------------------------------- #


@dataclass(frozen=True)
class ReportKey:
    """Hisobotning joriy ko‘rinishi: davr va filtrlar (tugmalarda ham shu ko‘rinadi)."""

    period: str
    period_label: str
    card_id: int = 0
    card_label: str = texts.ALL_CARDS
    category_id: int = 0
    category_label: str = f"🏷 {texts.ALL_CATEGORIES}"

    @property
    def data(self) -> str:
        return f"{self.period}:{self.card_id}:{self.category_id}"


def _short(text: str, limit: int = 24) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _back(key: ReportKey) -> list[InlineKeyboardButton]:
    return [_button(texts.BTN_BACK, f"rpv:{key.data}:0")]


def report_summary_actions(key: ReportKey, count: int) -> InlineKeyboardMarkup:
    """Hisobot ostidagi tugmalar: ro‘yxat, rasm, CSV va uchta filtr (joriy qiymati bilan)."""
    rows = []
    if count:
        rows.append([_button(texts.BTN_TRANSACTIONS.format(count=count), f"rpv:{key.data}:1")])
        rows.append([_button(texts.BTN_PICTURE, f"rpi:{key.data}"), _button(texts.BTN_CSV, f"rpx:{key.data}")])
    rows.append([_button(f"📅 {key.period_label}", f"rpp:{key.data}")])
    rows += _fit_rows(
        [
            _button(_short(f"💳 {key.card_label}"), f"rpc:{key.data}"),
            _button(_short(key.category_label), f"rpg:{key.data}"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def report_periods(key: ReportKey, months: list[tuple[int, int]]) -> InlineKeyboardMarkup:
    """``months`` — joriy oydan boshlab, eng yangisi birinchi. Karta va tur filtri saqlanadi."""

    def pick(label: str, code: str) -> InlineKeyboardButton:
        return _button(label, f"rpv:{code}:{key.card_id}:{key.category_id}:0")

    builder = InlineKeyboardBuilder()
    builder.row(pick(texts.BTN_TODAY, "d"), pick(texts.BTN_WEEK, "w"))
    builder.row(pick(texts.BTN_THIS_MONTH.format(label=month_label(*months[0])), "m"))
    if len(months) > 1:
        builder.row(pick(texts.BTN_PREV_MONTH.format(label=month_label(*months[1])), "pm"))
    older = [pick(month_label(year, month), f"{year:04d}-{month:02d}") for year, month in months[2:8]]
    for index in range(0, len(older), 2):
        builder.row(*older[index : index + 2])
    builder.row(pick(texts.BTN_ALL_TIME, "all"))
    builder.row(*_back(key))
    return builder.as_markup()


def report_cards(key: ReportKey, cards: list[Card]) -> InlineKeyboardMarkup:
    def pick(label: str, card_id: int) -> list[InlineKeyboardButton]:
        return [_button(label, f"rpv:{key.period}:{card_id}:{key.category_id}:0")]

    rows = [pick(f"💳 {texts.ALL_CARDS}", 0)]
    rows += [pick(f"{card.name} ****{card.card_last4}", card.id) for card in cards]
    rows.append(_back(key))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def report_categories(key: ReportKey, categories: list[Category]) -> InlineKeyboardMarkup:
    def pick(label: str, category_id: int) -> InlineKeyboardButton:
        return _button(label, f"rpv:{key.period}:{key.card_id}:{category_id}:0")

    choices = [pick(f"{category.emoji} {category.name}", category.id) for category in categories]
    rows = [[pick(f"🏷 {texts.ALL_CATEGORIES}", 0)], *_fit_rows(choices), _back(key)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def report_list_actions(key: ReportKey, page: int, pages: int) -> InlineKeyboardMarkup:
    navigation = []
    if page > 1:
        navigation.append(_button("◀️", f"rpv:{key.data}:{page - 1}"))
    if page < pages:
        navigation.append(_button("▶️", f"rpv:{key.data}:{page + 1}"))
    rows = [navigation] if navigation else []
    rows.append([_button(texts.BTN_SUMMARY, f"rpv:{key.data}:0"), _button(texts.BTN_CSV, f"rpx:{key.data}")])
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
    def mark(enabled: bool) -> str:
        return texts.MARK_ON if enabled else texts.MARK_OFF

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button(texts.BTN_TIMEZONE, "set:tz"), _button(texts.BTN_CURRENCY, "set:cur")],
            # Har biri alohida qatorda: uchtasi yonma-yon sig‘may, yozuvi qisqarib qolar edi.
            [_button(texts.BTN_DAILY.format(mark=mark(daily_enabled)), "set:daily")],
            [_button(texts.BTN_WEEKLY.format(mark=mark(weekly_enabled)), "set:weekly")],
            [_button(texts.BTN_NOTIFICATIONS.format(mark=mark(monthly_enabled)), "set:notif")],
            [_button(texts.BTN_WIPE, "set:wipe")],
        ]
    )


TIMEZONES = ("Asia/Tashkent", "Asia/Samarkand", "Asia/Almaty", "Europe/Moscow", "Europe/Istanbul", "Asia/Dubai")


def timezone_choice() -> InlineKeyboardMarkup:
    zones = [_button(name, f"set:tz:{name}") for name in TIMEZONES]
    return InlineKeyboardMarkup(inline_keyboard=[*_fit_rows(zones), [_button(texts.BTN_BACK, "set:menu")]])


def wipe_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_button(texts.BTN_WIPE_YES, "set:wipe:yes")], [_button(texts.BTN_NO, "set:menu")]]
    )
