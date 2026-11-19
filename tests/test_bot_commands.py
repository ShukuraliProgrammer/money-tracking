"""Kartalar, turlar, hisobot, eksport va sozlamalar buyruqlari."""

from datetime import datetime

import pytest
from sqlalchemy import func, select

from app.models import Card, Category, Transaction, User
from tests import samples
from tests.bot_harness import BotHarness
from tests.conftest import TZ

NOW = datetime(2026, 11, 19, 15, 30, tzinfo=TZ)

OCTOBER_EXPENSE = samples.CARDXABAR_EXPENSE.replace("19.11.26", "15.10.26").replace("250 000.00", "700 000.00")


@pytest.fixture
def bot(session_factory):
    return BotHarness(session_factory, NOW)


async def count(session_factory, model) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(model))


async def record(bot, text, note, category, card):
    await bot.send(text)
    await bot.send(note)
    await bot.click(category)
    await bot.click(card)
    assert "Saqlandi" in bot.last_text()


async def add_two_cards(bot):
    for name, last4, network in (("Asosiy Humo", "1234", "Humo"), ("Uzcard ish", "5678", "Uzcard")):
        await bot.send("/addcard")
        await bot.send(name)
        await bot.send(last4)
        await bot.click(network)
        await bot.click("O‘tkazib yuborish")
        await bot.click("UZS")


@pytest.fixture
async def seeded(bot):
    await add_two_cards(bot)
    await record(bot, samples.HUMO_EXPENSE, "Taksi — uyga qaytish", "P2P", "1234")
    await record(bot, samples.HUMO_INCOME.replace("*6157", "*1234").replace("03.06.2026", "05.11.2026"), "Maosh keldi", "Maosh", "1234")
    await record(bot, samples.CARDXABAR_EXPENSE.replace("***1234", "***5678"), "Kamolonda ovqatlandik 3 kishi", "Ovqatlanish", "5678")
    await record(bot, OCTOBER_EXPENSE.replace("***1234", "***5678"), "Oktabr xaridi", "Narsa sotib olish", "5678")
    return bot


# --- Kartalar -------------------------------------------------------------------- #


async def test_cards_empty_state(bot):
    await bot.send("/cards")
    assert "Hali karta qo‘shilmagan" in bot.last_text()
    assert any("Karta qo‘shish" in b for b in bot.buttons())


async def test_addcard_flow_creates_card_and_lists_it(bot, session_factory):
    await bot.send("/addcard")
    assert "nom" in bot.last_text().lower()
    await bot.send("Visa sayohat")
    assert "oxirgi 4" in bot.last_text()
    await bot.send("4321")
    await bot.click("Visa")
    await bot.send("Kapitalbank")
    await bot.click("USD")
    assert "Karta qo‘shildi" in bot.last_text()

    await bot.send("/cards")
    listing = bot.last_text()
    assert "Visa sayohat" in listing and "****4321" in listing and "Kapitalbank" in listing and "USD" in listing


async def test_addcard_refuses_full_card_number(bot, session_factory):
    await bot.send("/addcard")
    await bot.send("Asosiy")
    await bot.send("8600123456789012")
    assert "To‘liq karta raqamini yubormang" in bot.last_text()
    assert await count(session_factory, Card) == 0


async def test_addcard_rejects_duplicate(bot):
    await add_two_cards(bot)
    await bot.send("/addcard")
    await bot.send("Yana Humo")
    await bot.send("1234")
    await bot.click("Humo")
    await bot.click("O‘tkazib yuborish")
    await bot.click("UZS")
    assert "allaqachon qo‘shilgan" in bot.last_text()


async def test_card_can_be_deactivated_and_is_hidden_from_flow(bot):
    await add_two_cards(bot)
    await bot.send("/cards")
    await bot.click("⏸ Asosiy Humo")
    assert "nofaol" in bot.last_text()
    await bot.send(samples.HUMO_EXPENSE.replace("*1234", "*0000"))
    await bot.send("Taksi")
    await bot.click("P2P")
    assert not any("Asosiy Humo" in b for b in bot.buttons())
    assert any("Uzcard ish" in b for b in bot.buttons())


async def test_card_delete_needs_confirmation(bot, session_factory):
    await add_two_cards(bot)
    await bot.send("/cards")
    await bot.click("🗑 Asosiy Humo")
    assert await count(session_factory, Card) == 2
    await bot.click("Ha")
    assert await count(session_factory, Card) == 1


# --- Turlar ----------------------------------------------------------------------- #


async def test_categories_lists_defaults(bot):
    await bot.send("/categories")
    for name in ("P2P", "Ovqatlanish", "Narsa sotib olish", "Qarz berish", "Qarz olish", "Investitsiya", "Uyga to‘lov"):
        assert name in bot.last_text()


async def test_category_can_be_added_and_deleted(bot, session_factory):
    await bot.send("/categories")
    await bot.click("Yangi tur")
    await bot.send("🚕 Transport")
    assert "Transport" in bot.last_text()
    assert await count(session_factory, Category) == 10
    await bot.click("🗑 Transport")
    assert await count(session_factory, Category) == 9


async def test_duplicate_category_gets_friendly_error(bot):
    await bot.send("/categories")
    await bot.click("Yangi tur")
    await bot.send("ovqatlanish")
    assert "allaqachon bor" in bot.last_text()


# --- Hisobot ----------------------------------------------------------------------- #


async def test_report_asks_period_then_card_then_category(seeded):
    await seeded.send("/report")
    assert {"Bugun", "Bu hafta"} <= {b for b in seeded.buttons()}
    assert any("Bu oy" in b for b in seeded.buttons())
    assert any("Oktabr 2026" in b for b in seeded.buttons())
    await seeded.click("Bu oy")
    assert any("Hamma kartalar" in b for b in seeded.buttons())
    assert any("Asosiy Humo" in b for b in seeded.buttons())
    await seeded.click("Hamma kartalar")
    assert any("Hamma turlar" in b for b in seeded.buttons())
    assert any("Ovqatlanish" in b for b in seeded.buttons())


async def test_monthly_report_covers_all_cards(seeded):
    await seeded.send("/report")
    await seeded.click("Bu oy")
    await seeded.click("Hamma kartalar")
    await seeded.click("Hamma turlar")
    report = seeded.last_text()
    assert "Noyabr 2026" in report
    assert "Kirim: <b>1 000 000 UZS</b>" in report
    assert "Chiqim: <b>304 000 UZS</b>" in report
    assert "Farq: <b>+696 000 UZS</b>" in report
    assert "Asosiy Humo ****1234" in report and "Uzcard ish ****5678" in report
    assert "Ovqatlanish" in report and "P2P" in report and "Maosh" in report
    assert "KAMOLON OSH MARKAZI" in report
    assert "700 000" not in report  # oktabr kirmaydi


async def test_report_filtered_by_card(seeded):
    await seeded.send("/report")
    await seeded.click("Bu oy")
    await seeded.click("Uzcard ish")
    await seeded.click("Hamma turlar")
    report = seeded.last_text()
    assert "Chiqim: <b>250 000 UZS</b>" in report
    assert "Kirim: <b>0 UZS</b>" in report
    assert "Uzcard ish ****5678" in report
    assert "YANDEX GO" not in report


async def test_report_filtered_by_category(seeded):
    await seeded.send("/report")
    await seeded.click("Bu oy")
    await seeded.click("Hamma kartalar")
    await seeded.click("Ovqatlanish")
    report = seeded.last_text()
    assert "Chiqim: <b>250 000 UZS</b>" in report
    assert "YANDEX GO" not in report


async def test_previous_month_report(seeded):
    await seeded.send("/report")
    await seeded.click("O‘tgan oy")
    await seeded.click("Hamma kartalar")
    await seeded.click("Hamma turlar")
    assert "Oktabr 2026" in seeded.last_text()
    assert "Chiqim: <b>700 000 UZS</b>" in seeded.last_text()


async def test_transaction_list_shows_every_label(seeded):
    await seeded.send("/report")
    await seeded.click("Bu oy")
    await seeded.click("Hamma kartalar")
    await seeded.click("Hamma turlar")
    await seeded.click("Tranzaksiyalar")
    listing = seeded.last_text()
    for label in ("Taksi — uyga qaytish", "Maosh keldi", "Kamolonda ovqatlandik 3 kishi"):
        assert label in listing
    assert "Oktabr xaridi" not in listing
    assert "****1234" in listing and "****5678" in listing


async def test_transaction_list_is_paginated(bot):
    for minute in range(12):
        text = samples.HUMO_EXPENSE.replace("12:01", f"12:{minute:02d}")
        await record(bot, text, f"izoh-{minute:02d}", "P2P", "Kartasiz")
    await bot.send("/report")
    await bot.click("Bu oy")
    await bot.click("Hamma kartalar")
    await bot.click("Hamma turlar")
    await bot.click("Tranzaksiyalar")
    assert "1/2" in bot.last_text()
    assert "izoh-11" in bot.last_text() and "izoh-01" not in bot.last_text()
    await bot.click("▶")
    assert "2/2" in bot.last_text()
    assert "izoh-01" in bot.last_text() and "izoh-00" in bot.last_text()


async def test_report_csv_respects_filters(seeded):
    await seeded.send("/report")
    await seeded.click("Bu oy")
    await seeded.click("Uzcard ish")
    await seeded.click("Hamma turlar")
    await seeded.click("CSV")
    (document,) = seeded.documents()
    content = document.document.data.decode("utf-8-sig")
    assert "Kamolonda ovqatlandik 3 kishi" in content
    assert "Taksi" not in content
    assert document.document.filename.endswith(".csv")


async def test_empty_report(bot):
    await bot.send("/report")
    await bot.click("Bugun")
    await bot.click("Hamma kartalar")
    await bot.click("Hamma turlar")
    assert "tranzaksiya yo‘q" in bot.last_text()


async def test_report_never_shows_other_users_data(seeded):
    stranger = seeded.as_user(2002)
    await stranger.send("/report")
    await stranger.click("Bu oy")
    assert not any("Asosiy Humo" in b for b in stranger.buttons())
    await stranger.click("Hamma kartalar")
    await stranger.click("Hamma turlar")
    assert "tranzaksiya yo‘q" in stranger.last_text()


async def test_report_with_foreign_card_id_shows_nothing(seeded, session_factory):
    async with session_factory() as session:
        foreign_card_id = await session.scalar(select(Card.id).limit(1))
    stranger = seeded.as_user(2002)
    await stranger.send("/start")
    await stranger.click_data(f"rpv:m:{foreign_card_id}:0:0")
    assert "tranzaksiya yo‘q" in stranger.last_text()


# --- Statistika va eksport ----------------------------------------------------------- #


async def test_stat_shows_last_30_days_and_trend(seeded):
    await seeded.send("/stat")
    text = seeded.last_text()
    assert "Oxirgi 30 kun" in text
    assert "Ovqatlanish" in text and "KAMOLON OSH MARKAZI" in text
    assert "Oktabr 2026" in text and "Noyabr 2026" in text


async def test_export_sends_csv_for_chosen_period(seeded):
    await seeded.send("/export")
    await seeded.click("Hamma vaqt")
    (document,) = seeded.documents()
    content = document.document.data.decode("utf-8-sig")
    assert content.splitlines()[0] == "date,type,amount,currency,merchant,category,user_note,card_last4,source"
    assert len(content.strip().splitlines()) == 5
    assert "Oktabr xaridi" in content


async def test_export_with_no_data(bot):
    await bot.send("/export")
    await bot.click("Bu oy")
    assert bot.documents() == []
    assert "tranzaksiya yo‘q" in bot.last_text()


# --- Sozlamalar ------------------------------------------------------------------------ #


async def test_settings_shows_current_values(bot):
    await bot.send("/settings")
    text = bot.last_text()
    assert "Asia/Tashkent" in text and "UZS" in text and "O‘zbek" in text


async def test_settings_change_currency_timezone_and_notifications(bot, session_factory):
    await bot.send("/settings")
    await bot.click("Valyuta")
    await bot.click("USD")
    await bot.click("Vaqt zonasi")
    await bot.send("Asia/Samarkand")
    await bot.click("Oylik hisobot")
    async with session_factory() as session:
        user = await session.scalar(select(User))
    assert (user.preferred_currency, user.timezone, user.notifications_enabled) == ("USD", "Asia/Samarkand", False)


async def test_settings_rejects_unknown_timezone(bot):
    await bot.send("/settings")
    await bot.click("Vaqt zonasi")
    await bot.send("Mars/Olympus")
    assert "topilmadi" in bot.last_text()


async def test_user_can_delete_all_their_data(seeded, session_factory):
    await seeded.send("/settings")
    await seeded.click("o‘chirish")
    assert await count(session_factory, Transaction) == 4  # tasdiqlashsiz o'chmaydi
    await seeded.click("Ha")
    assert "o‘chirildi" in seeded.last_text()
    assert await count(session_factory, Transaction) == 0
    assert await count(session_factory, Card) == 0
    assert await count(session_factory, User) == 0


async def test_user_can_start_again_after_deleting_data(seeded, session_factory):
    await seeded.send("/settings")
    await seeded.click("o‘chirish")
    await seeded.click("Ha")
    await seeded.send("/start")
    assert await count(session_factory, User) == 1
    assert await count(session_factory, Category) == 9


async def test_stat_amounts_are_bold(seeded):
    await seeded.send("/stat")
    text = seeded.last_text()
    assert "💰 <b>+1 000 000</b>" in text and "💸 <b>−304 000</b>" in text
    assert "Ovqatlanish — <b>250 000</b>" in text
    assert "Noyabr 2026: <b>+1 000 000 / −304 000 UZS</b>" in text
