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
    await bot.click(card)


# --- /start ---------------------------------------------------------------- #


async def test_start_greets_and_creates_profile(bot, session_factory):
    await bot.send("/start")
    assert "forward qiling yoki matnini yuboring" in bot.last_text()
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
    assert "Chiqim aniqlandi" in reply
    assert "54 000 UZS" in reply
    assert "YANDEX GO" in reply
    assert "****1234" in reply
    assert "19.11.2026 12:01" in reply
    assert "Nima uchun qilindi?" in reply
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


async def test_after_type_bot_asks_card_and_marks_matching_one(bot, session_factory):
    await add_card(session_factory, last4="1234", name="Asosiy Humo")
    await add_card(session_factory, last4="5678", name="Uzcard ish", network="Uzcard")
    await bot.send(samples.HUMO_EXPENSE)
    await bot.send("Taksi — uyga qaytish")
    await bot.click("P2P")
    assert "Qaysi kartadan" in bot.last_text()
    matching = next(b for b in bot.buttons() if "1234" in b)
    other = next(b for b in bot.buttons() if "5678" in b)
    assert "✓" in matching and "✓" not in other
    assert any("Yangi karta" in b for b in bot.buttons())


async def test_full_flow_saves_transaction_with_label_type_and_card(bot, session_factory):
    await add_card(session_factory, last4="1234", name="Asosiy Humo")
    await bot.send(samples.HUMO_EXPENSE)
    await bot.send("Taksi — uyga qaytish")
    await bot.click("P2P")
    await bot.click("1234")

    reply = bot.last_text()
    assert "Saqlandi" in reply
    assert "54 000 UZS" in reply and "YANDEX GO" in reply
    assert "P2P" in reply
    assert "Taksi — uyga qaytish" in reply
    assert "Asosiy Humo ****1234" in reply

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
    assert "Kirim aniqlandi" in bot.last_text()
    await bot.send("Akam qarzini qaytardi")
    await bot.click("P2P")
    assert "Qaysi kartaga" in bot.last_text()


async def test_note_details_are_extracted_and_shown(bot, session_factory):
    await bot.send(samples.CARDXABAR_EXPENSE)
    await bot.send("Kamolonda ovqatlandik 3 kishi")
    await bot.click("Ovqatlanish")
    await bot.click("Kartasiz")
    assert "Kishi soni: 3" in bot.last_text()
    (tx,) = await transactions(session_factory)
    assert tx.people_count == 3
    assert tx.is_shared_expense is True
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
    assert "Kirim aniqlandi" in bot.last_text()


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


async def test_photo_without_ai_key_asks_for_text_instead(bot):
    await bot.send_photo()
    assert "matnini" in bot.last_text()


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
    assert "Kirim aniqlandi" in bot.last_text() and "Nima uchun qilindi?" in bot.last_text()
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
    assert "Chiqim aniqlandi" in reply and "54 000 UZS" in reply and "YANDEX GO" in reply
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
