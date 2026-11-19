"""Summalar xabarlarda qalin (bold) bo'lib ajralib turishi kerak."""

from datetime import datetime
from decimal import Decimal

from app.bot import render
from app.models import Card, Category, Transaction
from app.services.report_service import summarize
from tests.conftest import TZ, make_parsed

WHEN = datetime(2026, 11, 19, 10, 15, tzinfo=TZ)


def make_tx(tx_id=1, kind="expense", amount="250000", merchant="KAMOLON", card=True, category=True) -> Transaction:
    tx = Transaction(
        id=tx_id, user_id=1, transaction_type=kind, amount=Decimal(amount), currency="UZS", merchant=merchant,
        user_note="Tushlik", occurred_at=WHEN, tags=[], recurring_period="none", source="manual",
    )  # fmt: skip
    tx.card = Card(id=1, user_id=1, name="Asosiy Humo", card_last4="1234", card_network="Humo") if card else None
    tx.category = Category(id=1, user_id=1, name="Ovqatlanish", emoji="🍽") if category else None
    return tx


def test_draft_summary_makes_amount_bold():
    assert "Summa: <b>250 000 UZS</b>" in render.draft_summary(make_parsed(), TZ)


def test_saved_summary_makes_amount_bold():
    assert "💸 <b>250 000 UZS</b> — KAMOLON" in render.saved_summary(make_tx())


def test_transaction_line_makes_amount_bold():
    assert "💸 <b>250 000 UZS</b> — KAMOLON" in render.transaction_line(make_tx(), TZ)


def test_report_totals_are_bold():
    report = summarize([make_tx(1), make_tx(2, kind="income", amount="1000000", merchant="ISH")])
    text = render.report_text("Noyabr 2026", "filtr", report, TZ)
    assert "💰 Kirim: <b>1 000 000 UZS</b>" in text
    assert "💸 Chiqim: <b>250 000 UZS</b>" in text
    assert "⚖️ Farq: <b>+750 000 UZS</b>" in text


def test_report_breakdowns_and_top_lists_have_bold_amounts():
    other = make_tx(3, amount="40000", merchant="KORZINKA")
    other.card = Card(id=2, user_id=1, name="Uzcard ish", card_last4="5678", card_network="Uzcard")
    other.category = Category(id=2, user_id=1, name="Boshqa", emoji="📦")
    report = summarize([make_tx(1), make_tx(2, kind="income", amount="1000000", merchant="ISH"), other])
    text = render.report_text("Noyabr 2026", "", report, TZ)
    assert "• Asosiy Humo ****1234: <b>+1 000 000 / −250 000</b>" in text
    assert "• 🍽 Ovqatlanish: <b>+1 000 000 / −250 000</b> (2 ta)" in text
    assert "1. <b>250 000 UZS</b> — KAMOLON (19.11)" in text
    assert "• KAMOLON — 1 marta, <b>250 000 UZS</b>" in text


def test_breakdown_with_a_single_row_is_left_out():
    # Bitta karta va bitta tur bo'lsa, taqsimot yig'indini takrorlaydi xolos.
    text = render.report_text("Noyabr 2026", "", summarize([make_tx(1), make_tx(2, amount="1000")]), TZ)
    assert "Kartalar bo‘yicha" not in text and "Turlar bo‘yicha" not in text
    assert "💸 Chiqim: <b>251 000 UZS</b>" in text


def test_report_without_filter_has_no_filter_line():
    text = render.report_text("Noyabr 2026", "", summarize([make_tx(1)]), TZ)
    assert text.splitlines()[:2] == ["📊 <b>Noyabr 2026</b>", ""]


def test_labels_and_merchants_stay_regular_weight():
    text = render.draft_summary(make_parsed(), TZ)
    assert "Joy: KAMOLON" in text
    assert "<b>KAMOLON" not in text
