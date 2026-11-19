"""Ma’lumotlarni Telegram xabari (HTML) ko‘rinishiga keltirish."""

from __future__ import annotations

from decimal import Decimal
from html import escape
from zoneinfo import ZoneInfo

from app.bot import texts
from app.models import Card, Category, Transaction, User
from app.schemas import ParsedTransaction
from app.services.report_service import CurrencyReport, Report, Stats, Totals
from app.services.transfers import Leg
from app.utils.dates import format_dt
from app.utils.money import format_amount, format_number

MESSAGE_LIMIT = 4000


def esc(value: str | None) -> str:
    return escape(value or "", quote=False)


def clip(text: str) -> str:
    """Telegram xabar uzunligi chegarasidan oshmasligi uchun."""
    return text if len(text) <= MESSAGE_LIMIT else text[: MESSAGE_LIMIT - 1].rstrip() + "…"


def signed(amount: Decimal, positive: bool) -> str:
    return f"{'+' if positive else '−'}{format_number(amount)}"


def bold(text: str) -> str:
    return f"<b>{text}</b>"


def money(amount: Decimal, currency: str) -> str:
    """Summa xabarda ko‘zga tashlanishi uchun qalin yoziladi: <b>250 000 UZS</b>."""
    return bold(format_amount(amount, currency))


def card_title(card: Card) -> str:
    return f"{card.name} ****{card.card_last4}"


# --- Tranzaksiya ------------------------------------------------------------- #


def draft_summary(draft: ParsedTransaction, tz: ZoneInfo) -> str:
    """Aniqlangan maydonlar. Aniqlanmagan joy yoki karta uchun bo‘sh qator chiqarilmaydi."""
    income = draft.transaction_type == "income"
    lines = [texts.HEAD_INCOME if income else texts.HEAD_EXPENSE]
    if draft.amount is not None:
        lines.append(f"Summa: {money(draft.amount, draft.currency)}")
    if draft.merchant:
        lines.append(f"{'Kimdan' if income else 'Joy'}: {esc(draft.merchant)}")
    if draft.card_last4:
        lines.append(f"Karta: ****{draft.card_last4}")
    if draft.occurred_at:
        lines.append(f"Vaqt: {format_dt(draft.occurred_at, tz)}")
    return "\n".join(lines)


def transaction_line(transaction: Transaction, tz: ZoneInfo) -> str:
    """Bitta tranzaksiyaning qisqa ko‘rinishi."""
    income = transaction.transaction_type == "income"
    icon = "💰" if income else "💸"
    parts = [f"{icon} {money(transaction.amount, transaction.currency)}"]
    if transaction.merchant:
        parts.append(esc(transaction.merchant))
    return " — ".join(parts) + f" ({format_dt(transaction.occurred_at, tz)})"


def saved_summary(transaction: Transaction) -> str:
    """Qisqa tasdiq: summa va joy, pastida tur va karta."""
    income = transaction.transaction_type == "income"
    head = f"{texts.SAVED_HEAD} {'💰' if income else '💸'} {money(transaction.amount, transaction.currency)}"
    if transaction.merchant:
        head += f" — {esc(transaction.merchant)}"
    details = []
    if transaction.category:
        details.append(f"{transaction.category.emoji} {esc(transaction.category.name)}")
    details.append(esc(card_title(transaction.card)) if transaction.card else texts.BTN_NO_CARD)
    return f"{head}\n{' · '.join(details)}"


def transfer_route(sent: Leg, received: Leg) -> str:
    """«****1234 → ****5678, 1 000 000 UZS» (+ komissiya, agar farq bo‘lsa)."""
    cards = " → ".join(f"****{leg.card_last4}" if leg.card_last4 else "—" for leg in (sent, received))
    text = f"{cards}, {money(received.amount, received.currency)}"
    if sent.amount > received.amount:
        text += texts.TRANSFER_FEE.format(fee=format_amount(sent.amount - received.amount, sent.currency))
    return text


# --- Kartalar, turlar, sozlamalar -------------------------------------------- #


def cards_list(cards: list[Card]) -> str:
    if not cards:
        return texts.CARDS_EMPTY
    lines = [texts.CARDS_HEAD]
    for index, card in enumerate(cards, start=1):
        details = [f"{card.card_network} ****{card.card_last4}", card.currency]
        if card.bank_name:
            details.append(esc(card.bank_name))
        line = f"{index}. {esc(card.name)} — " + " · ".join(details)
        if not card.is_active:
            line += f" ({texts.INACTIVE})"
        lines.append(line)
    return "\n".join(lines)


def categories_list(categories: list[Category]) -> str:
    return "\n".join([texts.CATEGORIES_HEAD, *(f"{category.emoji} {esc(category.name)}" for category in categories)])


def settings_text(user: User) -> str:
    return texts.SETTINGS.format(timezone=esc(user.timezone), currency=esc(user.preferred_currency))


# --- Hisobot -------------------------------------------------------------------- #


def _plain_flow(totals: Totals) -> str:
    parts = []
    if totals.income:
        parts.append(signed(totals.income, True))
    if totals.expense:
        parts.append(signed(totals.expense, False))
    return " / ".join(parts) or "0"


def _flow(totals: Totals) -> str:
    return bold(_plain_flow(totals))


def _label(transaction: Transaction, limit: int = 60) -> str:
    """Tranzaksiyaning nomi: foydalanuvchi yozgan izoh, u bo‘lmasa joy nomi."""
    text = transaction.user_note or transaction.merchant or "—"
    return esc(text if len(text) <= limit else text[: limit - 1] + "…")


def _day(transaction: Transaction, tz: ZoneInfo) -> str:
    return transaction.occurred_at.astimezone(tz).strftime("%d.%m")


def _currency_block(report: CurrencyReport, tz: ZoneInfo) -> list[str]:
    currency, totals = report.currency, report.totals
    lines = [
        f"<b>{currency}</b>",
        f"💰 Kirim: {money(totals.income, currency)}",
        f"💸 Chiqim: {money(totals.expense, currency)}",
        f"⚖️ Farq: {bold(f'{signed(abs(totals.net), totals.net >= 0)} {currency}')}",
    ]
    # Bitta qatorli taqsimot yig‘indini takrorlaydi, shuning uchun ko‘rsatilmaydi.
    if len(report.by_card) > 1:
        lines += ["", "💳 <b>Kartalar bo‘yicha:</b>"]
        lines += [f"• {esc(item.label)}: {_flow(item.totals)}" for item in report.by_card]
    if len(report.by_category) > 1:
        lines += ["", "🏷 <b>Turlar bo‘yicha:</b>"]
        lines += [
            f"• {esc(item.label)}: {_flow(item.totals)} ({item.totals.count} ta)" for item in report.by_category[:15]
        ]
    if report.top_expenses:
        lines += ["", "🔝 <b>Eng katta xarajatlar:</b>"]
        for index, transaction in enumerate(report.top_expenses, start=1):
            lines.append(
                f"{index}. {money(transaction.amount, currency)} — {_label(transaction)} ({_day(transaction, tz)})"
            )
    if report.top_merchants:
        lines += ["", "🏪 <b>Eng ko‘p ishlatilgan joylar:</b>"]
        lines += [
            f"• {esc(stat.merchant)} — {stat.count} marta, {money(stat.expense, currency)}"
            for stat in report.top_merchants
        ]
    return lines


def report_text(title: str, filter_line: str, report: Report, tz: ZoneInfo) -> str:
    lines = [f"📊 <b>{esc(title)}</b>", *([esc(filter_line)] if filter_line else []), ""]
    if report.count == 0:
        lines.append(texts.REPORT_EMPTY)
        return "\n".join(lines)
    for currency_report in report.currencies:
        lines += _currency_block(currency_report, tz)
        lines.append("")
    return clip("\n".join(lines).rstrip())


def transactions_page(
    title: str, filter_line: str, transactions: list[Transaction], page: int, pages: int, tz: ZoneInfo
) -> str:
    head = f"🧾 <b>{esc(title)}</b> — tranzaksiyalar ({page}/{pages})"
    lines = [head, *([esc(filter_line)] if filter_line else []), ""]
    for transaction in transactions:
        lines += [*_transaction_block(transaction, tz, "%d.%m %H:%M"), ""]
    return clip("\n".join(lines).rstrip())


def _transaction_block(transaction: Transaction, tz: ZoneInfo, time_format: str) -> list[str]:
    """Bitta tranzaksiya: vaqt va summa, tur · joy · karta, izoh."""
    income = transaction.transaction_type == "income"
    when = transaction.occurred_at.astimezone(tz).strftime(time_format)
    amount = f"{signed(transaction.amount, income)} {transaction.currency}"
    lines = [f"{when} · {'💰' if income else '💸'} <b>{amount}</b>"]
    details = []
    if transaction.category:
        details.append(f"{transaction.category.emoji} {esc(transaction.category.name)}")
    if transaction.merchant:
        details.append(esc(transaction.merchant))
    details.append(f"****{transaction.card.card_last4}" if transaction.card else texts.BTN_NO_CARD)
    lines.append(" · ".join(details))
    if transaction.user_note:
        note = transaction.user_note if len(transaction.user_note) <= 160 else transaction.user_note[:159] + "…"
        lines.append(f"📝 {esc(note)}")
    return lines


def daily_report_text(day_label: str, report: Report, transactions: list[Transaction], tz: ZoneInfo) -> str:
    """Kunlik hisobot: yig‘indilar va shu kungi tranzaksiyalar (eng yangisi birinchi)."""
    lines = [f"🗓 <b>{texts.DAILY_HEADING}</b> · {esc(day_label)}", ""]
    for currency_report in report.currencies:
        currency, totals = currency_report.currency, currency_report.totals
        if len(report.currencies) > 1:
            lines.append(f"<b>{currency}</b>")
        lines += [f"💰 Kirim: {money(totals.income, currency)}", f"💸 Chiqim: {money(totals.expense, currency)}", ""]
    for transaction in transactions:
        lines += [*_transaction_block(transaction, tz, "%H:%M"), ""]
    if report.count > len(transactions):
        lines.append(texts.DAILY_MORE.format(count=report.count - len(transactions)))
    return clip("\n".join(lines).rstrip())


def _bar(share: float) -> str:
    return "▇" * max(1, round(share * 10))


def stats_text(stats: Stats, tz: ZoneInfo) -> str:
    lines = [f"📈 <b>Statistika</b> — {texts.BTN_LAST_30}", ""]
    if stats.report.count == 0:
        lines += [texts.REPORT_EMPTY, ""]
    for report in stats.report.currencies:
        currency, totals = report.currency, report.totals
        lines.append(
            f"<b>{currency}</b>: 💰 {bold(signed(totals.income, True))} · 💸 {bold(signed(totals.expense, False))}"
        )
        spending = [item for item in report.by_category if item.totals.expense > 0]
        if spending:
            lines.append("🏷 Turlar bo‘yicha (chiqim):")
            for item in spending[:10]:
                share = float(item.totals.expense / totals.expense)
                lines.append(
                    f"• {esc(item.label)} — {bold(format_number(item.totals.expense))} ({share:.0%}) {_bar(share)}"
                )
        if report.top_expenses:
            lines.append("🔝 Eng katta xarajatlar:")
            lines += [
                f"{index}. {bold(format_number(item.amount))} — {_label(item)} ({_day(item, tz)})"
                for index, item in enumerate(report.top_expenses, start=1)
            ]
        if report.top_merchants:
            lines.append("🏪 Joylar bo‘yicha:")
            lines += [
                f"• {esc(stat.merchant)} — {stat.count} marta, {bold(format_number(stat.expense))}"
                for stat in report.top_merchants
            ]
        lines.append("")

    lines.append("📅 <b>Oylik trend:</b>")
    for month in stats.trend:
        if not month.totals:
            lines.append(f"{month.label}: —")
            continue
        flows = [bold(f"{_plain_flow(totals)} {currency}") for currency, totals in sorted(month.totals.items())]
        lines.append(f"{month.label}: " + "; ".join(flows))
    return clip("\n".join(lines))
