"""Suhbat oqimi testlari: foydalanuvchi xabar yuboradi, bot uchta savol beradi va saqlaydi."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.models import Card, Transaction, User
from app.schemas import LLMNoteAnalysis, LLMTransaction
from app.services import transaction_service as ts
from tests import samples
from tests.bot_harness import BotHarness
from tests.conftest import TZ

NOW = datetime(2026, 11, 19, 15, 30, tzinfo=TZ)


@pytest.fixture
def bot(session_factory):
    return BotHarness(session_factory, NOW)


async def db_user(session_factory, telegram_id=1001) -> User:
    async with session_factory() as session:
        return await session.scalar(select(User).where(User.telegram_user_id == telegram_id))


async def transactions(session_factory, telegram_id=1001) -> list[Transaction]:
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.telegram_user_id == telegram_id))
        return list(await session.scalars(select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.id)))


async def add_card(session_factory, last4="1234", name="Asosiy Humo", network="Humo", telegram_id=1001) -> Card:
    async with session_factory() as session:
        user = await ts.get_or_create_user(session, telegram_id, "ali", "Ali")
        return await ts.add_card(session, user.id, name=name, last4=last4, network=network)


async def save_humo_expense(bot, note="Taksi — uyga qaytish", category="P2P", card="Kartasiz", text=samples.HUMO_EXPENSE):
    await bot.send(text)
    await bot.send(note)
    await bot.click(category)
    if "Saqlandi" not in bot.last_text():  # karta xabardan aniqlangan bo'lsa, so'ralmaydi
        await bot.click(card)


# --- /start ---------------------------------------------------------------- #


async def test_start_greets_briefly_and_creates_profile(bot, session_factory):
    await bot.send("/start")
    greeting, description, commands, warning = bot.last_text().split("\n\n")  # bo'limlar orasida bo'sh qator
    assert greeting == "👋 Salom, Ali!"
    assert "forward qiling yoki matnini yuboring" in description
    assert commands.splitlines() == ["📊 Hisobot: /report", "❓ Yordam: /help"]
    assert warning.startswith("🔒")
    user = await db_user(session_factory)
    assert user.timezone == "Asia/Tashkent"
    assert user.preferred_currency == "UZS"


async def test_help_lists_commands(bot):
    await bot.send("/help")
    for command in ("/add", "/cards", "/addcard", "/report", "/stat", "/categories", "/export", "/delete", "/settings"):
        assert command in bot.last_text()


async def test_bot_ignores_group_chats(bot):
    assert await bot.send("/start", chat_type="group") == []


# --- Asosiy oqim: uch savol -------------------------------------------------- #


async def test_pasted_notification_is_summarized_and_asks_why(bot):
    await bot.send(samples.HUMO_EXPENSE)
    reply = bot.last_text()
    # Karta botlaridagi kabi: har qator emoji bilan boshlanadi, ortiqcha so'z yo'q.
    assert reply.splitlines() == [
        "💸 <b>Chiqim</b>",
        "➖ <b>54 000 UZS</b>",
        "📍 YANDEX GO",
        "💳 ****1234",
        "🕓 19.11.2026 12:01",
        "",
        "📝 Nima uchun qilindi?",
    ]
    assert any("Tahrirlash" in b for b in bot.buttons())
    assert any("Bekor qilish" in b for b in bot.buttons())


async def test_after_note_bot_asks_type_with_users_categories(bot):
    await bot.send(samples.HUMO_EXPENSE)
    await bot.send("Taksi — uyga qaytish")
    assert "Qaysi turga kiradi?" in bot.last_text()
    labels = " | ".join(bot.buttons())
    for name in ("P2P", "Ovqatlanish", "Narsa sotib olish", "Qarz berish", "Qarz olish", "Investitsiya", "Uyga to‘lov"):
        assert name in labels
    assert "Yangi tur" in labels


async def test_card_question_is_skipped_when_message_names_a_known_card(bot, session_factory):
    await add_card(session_factory, last4="1234", name="Asosiy Humo")
    await add_card(session_factory, last4="5678", name="Uzcard ish", network="Uzcard")
    await bot.send(samples.HUMO_EXPENSE)
    await bot.send("Taksi — uyga qaytish")
    await bot.click("P2P")
    assert "Saqlandi" in bot.last_text()
    assert "Qaysi kartadan" not in bot.all_text()
    (tx,) = await transactions(session_factory)
    assert tx.card.name == "Asosiy Humo"


async def test_card_is_asked_when_message_card_is_unknown(bot, session_factory):
    await add_card(session_factory, last4="5678", name="Uzcard ish", network="Uzcard")
    await bot.send(samples.HUMO_EXPENSE)
    await bot.send("Taksi")
    await bot.click("P2P")
    assert bot.last_text() == "💳 Qaysi kartadan qilindi?"
    assert any("Uzcard ish ****5678" in b for b in bot.buttons())
    assert any("Yangi karta" in b for b in bot.buttons())


async def test_inactive_card_is_not_chosen_automatically(bot, session_factory):
    card = await add_card(session_factory, last4="1234", name="Asosiy Humo")
    async with session_factory() as session:
        await ts.toggle_card_active(session, card.user_id, card.id)
    await bot.send(samples.HUMO_EXPENSE)
    await bot.send("Taksi")
    await bot.click("P2P")
    assert "Qaysi kartadan" in bot.last_text()


async def test_full_flow_saves_transaction_with_label_type_and_card(bot, session_factory):
    await add_card(session_factory, last4="1234", name="Asosiy Humo")
    await bot.send(samples.HUMO_EXPENSE)
    await bot.send("Taksi — uyga qaytish")
    await bot.click("P2P")

    reply = bot.last_text()
    assert "Saqlandi" in reply
    assert "54 000 UZS" in reply and "YANDEX GO" in reply
    assert "P2P" in reply
    assert "Asosiy Humo ****1234" in reply
    # Qisqa tasdiq: foydalanuvchi hozirgina yozgan izoh va sana takrorlanmaydi.
    assert "Taksi — uyga qaytish" not in reply and "19.11.2026" not in reply
    assert len(reply.splitlines()) == 2

    (tx,) = await transactions(session_factory)
    assert tx.amount == Decimal("54000")
    assert tx.transaction_type == "expense"
    assert tx.user_note == "Taksi — uyga qaytish"
    assert tx.category.name == "P2P"
    assert tx.card.card_last4 == "1234"
    assert tx.source == "humo"
    assert tx.occurred_at == datetime(2026, 11, 19, 12, 1, tzinfo=TZ)
    assert "****1234" in tx.raw_text


async def test_income_message_uses_income_wording(bot):
    await bot.send(samples.HUMO_INCOME)
    assert bot.last_text().splitlines()[:3] == ["💰 <b>Kirim</b>", "➕ <b>1 000 000 UZS</b>", "👤 P2P HUMO UZCARD"]
    await bot.send("Akam qarzini qaytardi")
    await bot.click("P2P")
    assert "Qaysi kartaga" in bot.last_text()


async def test_note_details_are_stored_but_not_repeated_in_the_reply(bot, session_factory):
    await bot.send(samples.CARDXABAR_EXPENSE)
    await bot.send("Kamolonda ovqatlandik 3 kishi #tushlik")
    await bot.click("Ovqatlanish")
    await bot.click("Kartasiz")
    assert "Kishi soni" not in bot.last_text() and "#tushlik" not in bot.last_text()
    assert "Kartasiz" in bot.last_text()
    (tx,) = await transactions(session_factory)
    assert tx.people_count == 3
    assert tx.is_shared_expense is True
    assert tx.tags == ["tushlik"]
    assert tx.card is None


async def test_new_card_can_be_created_inside_the_flow(bot, session_factory):
    await bot.send(samples.HUMO_EXPENSE)
    await bot.send("Taksi")
    await bot.click("P2P")
    await bot.click("Yangi karta")
    assert "****1234" in bot.last_text()
    await bot.send("Asosiy Humo")
    assert "Saqlandi" in bot.last_text()
    (tx,) = await transactions(session_factory)
    assert (tx.card.name, tx.card.card_last4, tx.card.card_network) == ("Asosiy Humo", "1234", "Humo")


async def test_new_card_without_digits_in_message_asks_last4_and_refuses_full_number(bot, session_factory):
    await bot.send("Kamolonda xarid 250 ming so'm 19.11.2026 10:15")
    await bot.send("Tushlik")
    await bot.click("Ovqatlanish")
    await bot.click("Yangi karta")
    assert "oxirgi 4" in bot.last_text()
    await bot.send("8600 1234 5678 9012")
    assert "To‘liq karta raqamini yubormang" in bot.last_text()
    await bot.send("9012")
    await bot.send("Asosiy Uzcard")
    assert "Saqlandi" in bot.last_text()
    (tx,) = await transactions(session_factory)
    assert tx.card.card_last4 == "9012"
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Card)) == 1


async def test_new_category_can_be_created_inside_the_flow(bot, session_factory):
    await bot.send(samples.HUMO_EXPENSE)
    await bot.send("Taksi")
    await bot.click("Yangi tur")
    await bot.send("🚕 Transport")
    assert "Qaysi kartadan" in bot.last_text()
    await bot.click("Kartasiz")
    (tx,) = await transactions(session_factory)
    assert (tx.category.name, tx.category.emoji) == ("Transport", "🚕")


# --- Yetishmagan ma'lumotni so'rash ----------------------------------------- #


async def test_manual_text_asks_type_then_date_before_summary(bot, session_factory):
    await bot.send(samples.MANUAL_FOOD)
    assert "kirimmi yoki chiqimmi" in bot.last_text()
    await bot.click("Chiqim")
    assert "qachon" in bot.last_text().lower()
    await bot.click("Hozir")
    assert "Nima uchun qilindi?" in bot.last_text()
    assert "250 000 UZS" in bot.last_text()
    await bot.send("Do'stlar bilan tushlik")
    await bot.click("Ovqatlanish")
    await bot.click("Kartasiz")
    (tx,) = await transactions(session_factory)
    assert tx.occurred_at == NOW
    assert tx.source == "manual"


async def test_date_can_be_typed(bot, session_factory):
    await bot.send("Kamolonda xarid 250 ming")
    await bot.send("18.11.2026 20:30")
    assert "18.11.2026 20:30" in bot.last_text()


async def test_unreadable_date_gets_friendly_error(bot):
    await bot.send("Kamolonda xarid 250 ming")
    await bot.send("bilmadim")
    assert "Sanani tushunmadim" in bot.last_text()


async def test_future_date_is_rejected(bot):
    await bot.send("Kamolonda xarid 250 ming")
    await bot.send("25.12.2027 10:00")
    assert "kelajakda" in bot.last_text()


async def test_forwarded_message_without_date_uses_original_message_time(bot, session_factory):
    original_time = NOW - timedelta(hours=3)
    await bot.send("➖ 54.000,00 UZS\n📍 YANDEX GO\n💳 HUMOCARD *1234", forward_from="HUMOcardbot", forward_date=original_time)
    assert "Nima uchun qilindi?" in bot.last_text()
    assert "19.11.2026 12:30" in bot.last_text()


async def test_forward_from_cardxabar_sets_source_and_network(bot, session_factory):
    await bot.send(samples.CARDXABAR_EXPENSE, forward_from="CardXabarBot")
    await bot.send("Tushlik")
    await bot.click("Ovqatlanish")
    await bot.click("Yangi karta")
    await bot.send("Asosiy Uzcard")
    (tx,) = await transactions(session_factory)
    assert tx.source == "cardxabar"
    assert tx.card.card_network == "Uzcard"


async def test_missing_amount_is_asked(bot):
    await bot.send("Kamolonda xarid qildim 19.11.2026 10:15")
    assert "Summani" in bot.last_text()
    await bot.send("yigirma")
    assert "Summani tushunmadim" in bot.last_text()
    await bot.send("250 ming")
    assert "250 000 UZS" in bot.last_text()
    assert "Nima uchun qilindi?" in bot.last_text()


async def test_unrelated_text_gets_a_hint_and_starts_nothing(bot, session_factory):
    await bot.send("salom, qalaysan")
    assert "tushunmadim" in bot.last_text().lower()
    await bot.send(samples.HUMO_EXPENSE)
    assert "Nima uchun qilindi?" in bot.last_text()


# --- Tahrirlash, bekor qilish, takror ------------------------------------------ #


async def test_cancel_button_discards_draft(bot, session_factory):
    await bot.send(samples.HUMO_EXPENSE)
    await bot.click("Bekor qilish")
    assert "Bekor qilindi" in bot.last_text()
    await bot.send(samples.HUMO_EXPENSE)
    assert "Nima uchun qilindi?" in bot.last_text()
    assert await transactions(session_factory) == []


async def test_edit_amount(bot):
    await bot.send(samples.HUMO_EXPENSE)
    await bot.click("Tahrirlash")
    await bot.click("Summa")
    await bot.send("60 000")
    assert "60 000 UZS" in bot.last_text()
    assert "Nima uchun qilindi?" in bot.last_text()


async def test_edit_flips_type(bot):
    await bot.send(samples.HUMO_EXPENSE)
    await bot.click("Tahrirlash")
    await bot.click("Kirim")
    assert "<b>Kirim</b>" in bot.last_text()


async def test_edit_merchant(bot):
    await bot.send(samples.HUMO_EXPENSE)
    await bot.click("Tahrirlash")
    await bot.click("Joy")
    await bot.send("Yandex Taxi")
    assert "Yandex Taxi" in bot.last_text()


async def test_duplicate_is_warned_and_can_be_saved_anyway(bot, session_factory):
    await save_humo_expense(bot)
    await bot.send(samples.HUMO_EXPENSE)
    assert "allaqachon saqlangan" in bot.last_text()
    await bot.click("saqlash")
    assert "Nima uchun qilindi?" in bot.last_text()
    await bot.send("Ikkinchi marta")
    await bot.click("P2P")
    await bot.click("Kartasiz")
    assert len(await transactions(session_factory)) == 2


async def test_duplicate_can_be_dropped(bot, session_factory):
    await save_humo_expense(bot)
    await bot.send(samples.HUMO_EXPENSE)
    await bot.click("Yo‘q")
    assert "Bekor qilindi" in bot.last_text()
    assert len(await transactions(session_factory)) == 1


async def test_second_notification_while_first_is_pending_is_not_taken_as_note(bot, session_factory):
    await bot.send(samples.HUMO_EXPENSE)
    await bot.send(samples.CARDXABAR_EXPENSE)
    assert "Avval" in bot.last_text()
    await bot.send("Taksi")
    assert "Qaysi turga kiradi?" in bot.last_text()


async def test_typing_instead_of_pressing_button_gets_a_reminder(bot):
    await bot.send(samples.HUMO_EXPENSE)
    await bot.send("Taksi")
    await bot.send("ovqat")
    assert "tugmalardan birini" in bot.last_text()


async def test_stale_button_is_rejected(bot, session_factory):
    await bot.send(samples.HUMO_EXPENSE)
    await bot.click("Bekor qilish")
    await bot.click_data("tx:card:none")
    assert await transactions(session_factory) == []


# --- O'rganish ----------------------------------------------------------------- #


async def test_merchant_category_is_suggested_next_time(bot):
    await save_humo_expense(bot, category="Boshqa")
    later = samples.HUMO_EXPENSE.replace("12:01", "13:45")
    await bot.send(later)
    await bot.send("Yana taksi")
    starred = [b for b in bot.buttons() if "⭐" in b]
    assert len(starred) == 1 and "Boshqa" in starred[0]


async def test_note_keywords_suggest_category(bot):
    await bot.send(samples.CARDXABAR_EXPENSE)
    await bot.send("Do'stimga qarz berdim")
    starred = [b for b in bot.buttons() if "⭐" in b]
    assert len(starred) == 1 and "Qarz berish" in starred[0]
    assert bot.last_text() == "🏷 Qaysi turga kiradi?"  # ⭐ belgisi uchun alohida izoh yo'q


# --- Xavfsizlik ---------------------------------------------------------------- #


async def test_otp_message_is_refused_and_not_processed(bot, session_factory):
    await bot.send("Tasdiqlash kodi: 123456. Hech kimga aytmang!")
    assert "SMS kod" in bot.last_text()
    await bot.send(samples.HUMO_EXPENSE)
    assert "Nima uchun qilindi?" in bot.last_text()


async def test_full_card_number_in_message_is_masked_everywhere(bot, session_factory):
    await bot.send("8600123456789012 kartadan xarid 50 000 so'm 19.11.2026 10:15")
    assert "8600123456789012" not in bot.all_text()
    assert "****9012" in bot.all_text()
    await bot.send("Xarid")
    await bot.click("Boshqa")
    await bot.click("Kartasiz")
    (tx,) = await transactions(session_factory)
    assert "8600123456789012" not in tx.raw_text


async def test_users_do_not_see_each_others_cards(bot, session_factory):
    await add_card(session_factory, last4="1234", name="Alining kartasi")
    stranger = bot.as_user(2002)
    await stranger.send(samples.HUMO_EXPENSE)
    await stranger.send("Taksi")
    await stranger.click("P2P")
    assert not any("Alining kartasi" in b for b in stranger.buttons())


async def test_user_cannot_attach_another_users_card(bot, session_factory):
    foreign = await add_card(session_factory, last4="9999", name="Begona", telegram_id=2002)
    await bot.send(samples.HUMO_EXPENSE)
    await bot.send("Taksi")
    await bot.click("P2P")
    await bot.click_data(f"tx:card:{foreign.id}")
    assert await transactions(session_factory) == []


async def test_photo_without_ai_key_says_so_and_asks_for_text(bot):
    await bot.send_photo()
    assert "AI kaliti sozlanmagan" in bot.last_text() and "matnini" in bot.last_text()


async def test_image_sent_as_file_is_treated_like_a_photo(bot):
    await bot.send_file("IMG_0012.png", "image/png")
    assert "AI kaliti sozlanmagan" in bot.last_text()


async def test_image_file_without_declared_type_is_recognized_by_its_name(bot):
    await bot.send_file("IMG_0012.JPG")
    assert "AI kaliti sozlanmagan" in bot.last_text()


async def test_unsupported_file_gets_a_reply_listing_what_is_accepted(bot):
    await bot.send_file("arxiv.zip", "application/zip")
    reply = bot.last_text().lower()
    assert "faqat matnli" not in reply  # rasm va PDF ham qabul qilinadi, eski javob chalg'itardi
    assert "matn" in reply and "rasm" in reply and "pdf" in reply


async def test_database_error_gets_friendly_message(bot, monkeypatch):
    async def broken(*args, **kwargs):
        raise OperationalError("INSERT", {}, Exception("disk I/O error"))

    monkeypatch.setattr(ts, "create_transaction", broken)
    await bot.send(samples.HUMO_EXPENSE)
    await bot.send("Taksi")
    await bot.click("P2P")
    await bot.click("Kartasiz")
    assert "Vaqtincha xatolik" in bot.last_text()


# --- /add va /delete -------------------------------------------------------------- #


async def test_add_command_prompts_then_parses_next_message(bot):
    await bot.send("/add")
    assert "yozing" in bot.last_text()
    await bot.send("Korzinkadan xarid 180 ming 19.11.2026 09:00")
    assert "180 000 UZS" in bot.last_text()


async def test_command_interrupts_pending_draft(bot, session_factory):
    await bot.send(samples.HUMO_EXPENSE)
    await bot.send("/cards")
    await bot.send(samples.HUMO_EXPENSE)
    assert "Nima uchun qilindi?" in bot.last_text()


async def test_delete_removes_last_transaction_after_confirmation(bot, session_factory):
    await save_humo_expense(bot)
    await bot.send("/delete")
    assert "54 000 UZS" in bot.last_text()
    await bot.click("Ha")
    assert "O‘chirildi" in bot.last_text()
    assert await transactions(session_factory) == []


async def test_delete_with_nothing_saved(bot):
    await bot.send("/delete")
    assert "Hali tranzaksiya yo‘q" in bot.last_text()


# --- LLM zaxirasi ----------------------------------------------------------------- #


class FakeLLM:
    def __init__(self):
        self.parse_calls = 0

    async def parse_transaction(self, text, tz_name, now, categories):
        self.parse_calls += 1
        return LLMTransaction(
            transaction_type="expense", amount=250000, currency="UZS", merchant="Kamolon",
            category_guess="Ovqatlanish", confidence=0.86, explanation="250 000 UZS chiqim, Kamolon.",
        )  # fmt: skip

    async def analyze_note(self, note, merchant, transaction_type, categories):
        return LLMNoteAnalysis(category_guess="Ovqatlanish", tags=["tushlik"], people_count=3, is_shared_expense=True)


async def test_llm_fills_gaps_for_free_text_only(session_factory):
    llm = FakeLLM()
    bot = BotHarness(session_factory, NOW, llm=llm)
    await bot.send(samples.HUMO_EXPENSE)
    assert llm.parse_calls == 0  # ma'lum format: LLM chaqirilmaydi
    await bot.click("Bekor qilish")

    await bot.send(samples.MANUAL_FOOD)
    assert llm.parse_calls == 1
    assert "qachon" in bot.last_text().lower()  # tur LLM'dan olindi, sana so'raladi
    await bot.click("Hozir")
    assert "Kamolon" in bot.last_text()
    await bot.send("Kamolonda ovqatlandik 3 kishi")
    starred = [b for b in bot.buttons() if "⭐" in b]
    assert len(starred) == 1 and "Ovqatlanish" in starred[0]


# --- O'z kartalar orasidagi o'tkazma ------------------------------------------------ #


async def test_summary_offers_own_transfer_button_that_records_nothing(bot, session_factory):
    await bot.send(samples.TRANSFER_OUT)
    assert any("O‘z kartamga o‘tkazma" in b for b in bot.buttons())
    await bot.click("O‘z kartamga o‘tkazma")
    assert "yozilmadi" in bot.last_text()
    assert await transactions(session_factory) == []
    await bot.send(samples.HUMO_EXPENSE)  # holat tozalangan: keyingi xabar yangi tranzaksiya
    assert "Nima uchun qilindi?" in bot.last_text()


async def test_second_side_arriving_while_first_is_pending_is_recognized(bot, session_factory):
    await bot.send(samples.TRANSFER_OUT)
    await bot.send(samples.TRANSFER_IN)
    prompt = bot.last_text()
    assert "o‘tkazmaga o‘xshaydi" in prompt
    assert "****1234 → ****5678" in prompt and "1 000 000 UZS" in prompt
    await bot.click("Ha, yozilmasin")
    assert "yozilmadi" in bot.last_text()
    assert await transactions(session_factory) == []
    await bot.send(samples.HUMO_EXPENSE)
    assert "Nima uchun qilindi?" in bot.last_text()


async def test_sides_can_arrive_in_either_order(bot, session_factory):
    await bot.send(samples.TRANSFER_IN)
    await bot.send(samples.TRANSFER_OUT)
    assert "****1234 → ****5678" in bot.last_text()


async def test_declining_pending_pair_keeps_first_transaction_in_progress(bot, session_factory):
    await bot.send(samples.TRANSFER_OUT)
    await bot.send(samples.TRANSFER_IN)
    await bot.click("Yo‘q")
    assert "Avval" in bot.last_text()
    await bot.send("Akamga o‘tkazdim")
    await bot.click("P2P")
    await bot.click("Kartasiz")
    (tx,) = await transactions(session_factory)
    assert tx.transaction_type == "expense" and tx.user_note == "Akamga o‘tkazdim"


async def test_second_side_matching_a_saved_transaction_removes_both(bot, session_factory):
    await add_card(session_factory, last4="1234", name="Asosiy Humo")
    await save_humo_expense(bot, note="O‘tkazma", card="1234", text=samples.TRANSFER_OUT)
    assert len(await transactions(session_factory)) == 1
    await bot.send(samples.TRANSFER_IN)
    prompt = bot.last_text()
    assert "o‘tkazmaga o‘xshaydi" in prompt and "****1234 → ****5678" in prompt
    assert "Avval saqlangan" in prompt
    await bot.click("Ha, yozilmasin")
    assert "yozilmadi" in bot.last_text()
    assert await transactions(session_factory) == []


async def test_declining_saved_pair_continues_as_a_normal_transaction(bot, session_factory):
    await save_humo_expense(bot, note="Akamga", text=samples.TRANSFER_OUT)
    await bot.send(samples.TRANSFER_IN)
    await bot.click("Yo‘q")
    assert "<b>Kirim</b>" in bot.last_text() and "Nima uchun qilindi?" in bot.last_text()
    await bot.send("Do‘stim qaytardi")
    await bot.click("P2P")
    await bot.click("Kartasiz")
    assert len(await transactions(session_factory)) == 2


async def test_transfer_fee_is_shown_but_nothing_is_recorded(bot, session_factory):
    await bot.send(samples.TRANSFER_OUT.replace("1.000.000,00", "1.010.000,00"))
    await bot.send(samples.TRANSFER_IN)
    prompt = bot.last_text()
    assert "komissiya" in prompt.lower() and "10 000 UZS" in prompt
    await bot.click("Ha, yozilmasin")
    assert await transactions(session_factory) == []


async def test_unrelated_income_is_not_mistaken_for_a_transfer(bot, session_factory):
    await save_humo_expense(bot, note="O‘tkazma", text=samples.TRANSFER_OUT)
    await bot.send(samples.TRANSFER_IN.replace("1.000.000,00", "750.000,00"))
    assert "o‘tkazmaga o‘xshaydi" not in bot.last_text()
    assert "Nima uchun qilindi?" in bot.last_text()


async def test_old_transfer_button_cannot_discard_a_newer_draft(bot, session_factory):
    await bot.send(samples.TRANSFER_OUT)
    await bot.send(samples.TRANSFER_IN)
    stale_prompt = bot.last_with_keyboard()
    await bot.click("Yo‘q")
    await bot.click("Bekor qilish")
    await bot.send(samples.HUMO_EXPENSE)
    await bot.click_data("tx:trp:yes", stale_prompt)
    await bot.send("Taksi")
    assert "Qaysi turga kiradi?" in bot.last_text()  # yangi qoralama joyida


async def test_both_sides_forwarded_at_once_are_handled_in_order(bot, session_factory):
    import asyncio

    await asyncio.gather(bot.send(samples.TRANSFER_OUT), bot.send(samples.TRANSFER_IN))
    assert "o‘tkazmaga o‘xshaydi" in bot.last_text()
    await bot.click("Ha, yozilmasin")
    assert await transactions(session_factory) == []


# --- Screenshot (rasm) ---------------------------------------------------------------- #


class VisionLLM(FakeLLM):
    def __init__(self, visible_text=None, error=None, **fields):
        super().__init__()
        self.images = []
        self.error = error
        self.fields = {
            "transaction_type": "expense", "amount": 54000, "currency": "UZS", "merchant": "YANDEX GO",
            "card_last4": "1234", "card_network": "Humo", "occurred_at": "2026-11-19T12:01:00+05:00",
            "confidence": 0.9, "visible_text": visible_text or samples.HUMO_EXPENSE,
        } | fields  # fmt: skip

    async def parse_screenshot(self, image, tz_name, now, categories):
        self.images.append(image)
        if self.error:
            raise self.error
        return LLMTransaction.model_validate(self.fields)


async def test_screenshot_goes_through_the_same_three_questions(session_factory):
    llm = VisionLLM()
    bot = BotHarness(session_factory, NOW, llm=llm)
    await bot.send_photo()
    assert len(llm.images) == 1 and llm.images[0].data  # rasm yuklab olinib AI'ga berildi
    reply = bot.last_text()
    assert "<b>Chiqim</b>" in reply and "54 000 UZS" in reply and "YANDEX GO" in reply
    assert "Nima uchun qilindi?" in reply
    await bot.send("Taksi")
    await bot.click("P2P")
    await bot.click("Kartasiz")
    (tx,) = await transactions(session_factory)
    assert tx.source == "screenshot"
    assert tx.amount == Decimal("54000")
    assert tx.occurred_at == datetime(2026, 11, 19, 12, 1, tzinfo=TZ)


async def test_unreadable_screenshot_gets_friendly_message(session_factory):
    from app.services.llm import LLMError

    bot = BotHarness(session_factory, NOW, llm=VisionLLM(error=LLMError("timeout")))
    await bot.send_photo()
    assert "o‘qib bo‘lmadi" in bot.last_text()
    await bot.send(samples.HUMO_EXPENSE)
    assert "Nima uchun qilindi?" in bot.last_text()


async def test_screenshot_without_a_transaction_starts_nothing(session_factory):
    bot = BotHarness(session_factory, NOW, llm=VisionLLM(visible_text="Salom", amount=None, transaction_type=None, card_last4=None))
    await bot.send_photo()
    assert "tranzaksiya" in bot.last_text() and "Nima uchun" not in bot.last_text()


async def test_screenshot_of_sms_code_is_refused(session_factory):
    bot = BotHarness(session_factory, NOW, llm=VisionLLM(visible_text="Tasdiqlash kodi: 123456. Hech kimga aytmang"))
    await bot.send_photo()
    assert "SMS kod" in bot.last_text()
    assert await transactions(session_factory) == []


async def test_screenshot_missing_amount_is_asked(session_factory):
    bot = BotHarness(session_factory, NOW, llm=VisionLLM(amount=None, visible_text="💳 HUMOCARD *1234 Oplata 19.11.2026 12:01"))
    await bot.send_photo()
    assert "Summani" in bot.last_text()


async def test_photo_while_another_transaction_is_pending_is_not_processed(session_factory):
    llm = VisionLLM()
    bot = BotHarness(session_factory, NOW, llm=llm)
    await bot.send(samples.CARDXABAR_EXPENSE)
    await bot.send_photo()
    assert llm.images == []
    assert "Avval" in bot.last_text()


# --- Sodda xabarlar ------------------------------------------------------------------- #


async def test_summary_shows_only_known_fields(bot):
    await bot.send("Kamolonda xarid 250 ming 19.11.2026 10:15")
    summary = bot.last_text()
    assert summary.splitlines()[:3] == ["💸 <b>Chiqim</b>", "➖ <b>250 000 UZS</b>", "🕓 19.11.2026 10:15"]
    assert "📍" not in summary and "💳" not in summary  # aniqlanmagan joy va karta uchun qator chiqmaydi


async def test_image_file_in_another_format_is_converted_before_reading(session_factory):
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 120, 200)).save(buffer, format="BMP")
    llm = VisionLLM()
    bot = BotHarness(session_factory, NOW, llm=llm)
    await bot.send_file("chek.bmp", "image/bmp", data=buffer.getvalue())
    assert llm.images[0].media_type == "image/jpeg"
    assert "Nima uchun qilindi?" in bot.last_text()


async def test_unreadable_image_file_asks_to_send_it_as_a_photo(session_factory):
    llm = VisionLLM()
    bot = BotHarness(session_factory, NOW, llm=llm)
    await bot.send_file("IMG_0012.HEIC", "image/heic", data=b"heic-bytes-pillow-cannot-read")
    assert llm.images == []
    assert "rasm sifatida" in bot.last_text()


# --- PDF chek ------------------------------------------------------------------------- #

from tests.pdf_samples import RECEIPT_LINES, make_pdf, make_scanned_pdf  # noqa: E402

RECEIPT_NAME = "986017******9298_19.11.2026_14.00.22_uzum.pdf"


async def test_pdf_receipt_is_read_without_any_ai_key(bot, session_factory):
    await bot.send_file(RECEIPT_NAME, "application/pdf", data=make_pdf(RECEIPT_LINES))
    assert "kirimmi yoki chiqimmi" in bot.last_text()  # chekda yo'nalish yozilmagan, bot so'raydi
    await bot.click("Chiqim")
    summary = bot.last_text()
    assert "150 000 UZS" in summary and "ALIYEV VALI" in summary
    assert "****9298" in summary and "19.11.2026 14:00" in summary
    await bot.send("Akamga o‘tkazdim")
    await bot.click("P2P")
    await bot.click("Kartasiz")
    (tx,) = await transactions(session_factory)
    assert tx.source == "pdf"
    assert tx.amount == Decimal("150000")
    assert "986017" not in tx.raw_text


async def test_pdf_is_recognized_by_name_when_type_is_missing(bot):
    await bot.send_file("chek.PDF", None, data=make_pdf(RECEIPT_LINES))
    assert "kirimmi yoki chiqimmi" in bot.last_text()


async def test_pdf_after_add_command_works(bot):
    await bot.send("/add")
    await bot.send_file(RECEIPT_NAME, "application/pdf", data=make_pdf(RECEIPT_LINES))
    assert "kirimmi yoki chiqimmi" in bot.last_text()


async def test_scanned_pdf_asks_for_a_screenshot(bot):
    await bot.send_file("skaner.pdf", "application/pdf", data=make_scanned_pdf())
    assert "matn yo‘q" in bot.last_text() and "screenshot" in bot.last_text()


async def test_broken_pdf_gets_friendly_message(bot):
    await bot.send_file("chek.pdf", "application/pdf", data=b"not a pdf")
    assert "PDF faylni o‘qib bo‘lmadi" in bot.last_text()


async def test_pdf_without_a_transaction_starts_nothing(bot):
    await bot.send_file("xat.pdf", "application/pdf", data=make_pdf(["Hurmatli mijoz", "Tabriklaymiz"]))
    assert "tranzaksiyani topa olmadim" in bot.last_text()
    await bot.send(samples.HUMO_EXPENSE)
    assert "Nima uchun qilindi?" in bot.last_text()


async def test_long_pdf_statement_is_refused(bot):
    lines = [f"19.11.2026 12:{n % 60:02d} Payment {1000 + n} UZS MERCHANT NUMBER {n}" for n in range(120)]
    await bot.send_file("vypiska.pdf", "application/pdf", data=make_pdf(lines))
    assert "bitta chek" in bot.last_text().lower()


async def test_pdf_while_another_transaction_is_pending_is_not_processed(bot, session_factory):
    await bot.send(samples.CARDXABAR_EXPENSE)
    await bot.send_file(RECEIPT_NAME, "application/pdf", data=make_pdf(RECEIPT_LINES))
    assert "Avval" in bot.last_text()
    await bot.send("Tushlik")
    assert "Qaysi turga kiradi?" in bot.last_text()


async def test_pdf_with_sms_code_is_refused(bot, session_factory):
    await bot.send_file("kod.pdf", "application/pdf", data=make_pdf(["Tasdiqlash kodi: 123456", "Amount 5 000 UZS"]))
    assert "SMS kod" in bot.last_text()
    assert await transactions(session_factory) == []
