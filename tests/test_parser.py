from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.schemas import LLMTransaction
from app.services.llm import LLMError
from app.services.parser import RuleBasedParser, TransactionParser
from tests import samples

TZ = ZoneInfo("Asia/Tashkent")
NOW = datetime(2026, 11, 19, 15, 30, tzinfo=TZ)


def rule_parse(text: str, source_hint: str | None = None):
    return RuleBasedParser().parse(text, TZ, NOW, source_hint=source_hint)


def test_humo_expense_is_fully_parsed():
    parsed = rule_parse(samples.HUMO_EXPENSE)
    assert parsed.transaction_type == "expense"
    assert parsed.amount == Decimal("54000")
    assert parsed.currency == "UZS"
    assert parsed.merchant == "YANDEX GO"
    assert parsed.card_last4 == "1234"
    assert parsed.card_network == "Humo"
    assert parsed.occurred_at == datetime(2026, 11, 19, 12, 1, tzinfo=TZ)
    assert parsed.source == "humo"
    assert parsed.missing_fields == []
    assert parsed.confidence >= 0.9


def test_humo_income_reads_plus_amount_not_balance():
    parsed = rule_parse(samples.HUMO_INCOME)
    assert parsed.transaction_type == "income"
    assert parsed.amount == Decimal("1000000")
    assert parsed.card_last4 == "6157"
    assert parsed.card_network == "Humo"
    assert parsed.source == "humo"


def test_cardxabar_expense_ignores_balance_line():
    parsed = rule_parse(samples.CARDXABAR_EXPENSE)
    assert parsed.transaction_type == "expense"
    assert parsed.amount == Decimal("250000")
    assert parsed.merchant == "KAMOLON OSH MARKAZI"
    assert parsed.card_last4 == "1234"
    assert parsed.occurred_at == datetime(2026, 11, 19, 10, 15, tzinfo=TZ)
    assert parsed.source == "cardxabar"


def test_cardxabar_network_is_unknown_without_evidence():
    assert rule_parse(samples.CARDXABAR_EXPENSE).card_network == "Unknown"


def test_forward_origin_hint_sets_source_and_network():
    parsed = rule_parse(samples.CARDXABAR_EXPENSE, source_hint="cardxabar")
    assert parsed.source == "cardxabar"
    assert parsed.card_network == "Uzcard"


def test_bank_sms_in_usd():
    parsed = rule_parse(samples.BANK_SMS_USD)
    assert parsed.transaction_type == "expense"
    assert parsed.amount == Decimal("12.50")
    assert parsed.currency == "USD"
    assert parsed.card_last4 == "4321"
    assert parsed.merchant == "AMAZON.COM"
    assert parsed.source == "bank_sms"


def test_bank_sms_in_uzbek_ignores_balance():
    parsed = rule_parse(samples.BANK_SMS_UZ)
    assert parsed.transaction_type == "expense"
    assert parsed.amount == Decimal("150000")
    assert parsed.currency == "UZS"
    assert parsed.card_last4 == "4321"
    assert parsed.occurred_at == datetime(2026, 11, 19, 10, 15, tzinfo=TZ)


def test_bank_sms_in_cyrillic():
    parsed = rule_parse(samples.BANK_SMS_RU)
    assert parsed.transaction_type == "expense"
    assert parsed.amount == Decimal("150000")
    assert parsed.currency == "UZS"
    assert parsed.card_last4 == "1234"


def test_visa_keyword_sets_network():
    parsed = rule_parse("VISA *4321 Purchase 12.50 USD AMAZON 2026-11-19 10:15")
    assert parsed.card_network == "Visa"
    assert parsed.amount == Decimal("12.50")
    assert parsed.transaction_type == "expense"


def test_manual_text_does_not_invent_type_or_date():
    parsed = rule_parse(samples.MANUAL_FOOD)
    assert parsed.amount == Decimal("250000")
    assert parsed.currency == "UZS"
    assert parsed.transaction_type is None
    assert parsed.occurred_at is None
    assert parsed.source == "manual"
    assert "transaction_type" in parsed.missing_fields
    assert "occurred_at" in parsed.missing_fields


def test_income_keyword_in_manual_text():
    parsed = rule_parse("Maosh keldi 12 mln")
    assert parsed.transaction_type == "income"
    assert parsed.amount == Decimal("12000000")


def test_people_count_is_not_mistaken_for_amount():
    parsed = rule_parse("Kamolonda ovqatlandik 3 kishi 250 ming")
    assert parsed.amount == Decimal("250000")


def test_relative_day_word_sets_date():
    parsed = rule_parse("kecha taksi 25 ming")
    assert parsed.occurred_at == NOW - timedelta(days=1)
    assert parsed.amount == Decimal("25000")


def test_date_digits_are_not_mistaken_for_amount():
    parsed = rule_parse("19.11.2026 10:15 xarid 45000")
    assert parsed.amount == Decimal("45000")
    assert parsed.transaction_type == "expense"


def test_text_without_amount_reports_it_missing():
    parsed = rule_parse("salom, qalaysan")
    assert parsed.amount is None
    assert "amount" in parsed.missing_fields
    assert parsed.confidence < 0.5


def test_full_card_number_never_survives_in_raw_text():
    parsed = rule_parse("8600123456789012 kartadan xarid 50 000 so'm")
    assert "8600123456789012" not in parsed.raw_text
    assert "****9012" in parsed.raw_text
    assert parsed.card_last4 == "9012"
    assert parsed.card_network == "Uzcard"


def test_explanation_is_in_uzbek_and_mentions_amount():
    parsed = rule_parse(samples.HUMO_EXPENSE)
    assert "54 000 UZS" in parsed.explanation


# --- TransactionParser: qoidalar yetmasa LLM’ga murojaat qiladi ---


class FakeLLM:
    def __init__(self, result: dict | None = None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.calls: list[str] = []

    async def parse_transaction(self, text, tz_name, now, categories):
        self.calls.append(text)
        if self.error:
            raise self.error
        return LLMTransaction.model_validate(self.result)


def llm_result(**overrides) -> dict:
    base = {
        "transaction_type": "expense",
        "amount": 250000,
        "currency": "UZS",
        "merchant": "Kamolon",
        "card_last4": None,
        "card_network": "Unknown",
        "occurred_at": None,
        "category_guess": "Ovqatlanish",
        "confidence": 0.86,
        "missing_fields": ["occurred_at"],
        "explanation": "250 000 UZS chiqim, Kamolon.",
    }
    return base | overrides


async def test_structured_message_does_not_call_llm():
    llm = FakeLLM(llm_result())
    parsed = await TransactionParser(llm).parse(samples.HUMO_EXPENSE, TZ, NOW)
    assert llm.calls == []
    assert parsed.amount == Decimal("54000")


async def test_free_text_uses_llm_to_fill_gaps():
    llm = FakeLLM(llm_result())
    parsed = await TransactionParser(llm).parse(samples.MANUAL_FOOD, TZ, NOW)
    assert len(llm.calls) == 1
    assert parsed.transaction_type == "expense"
    assert parsed.merchant == "Kamolon"
    assert parsed.category_guess == "Ovqatlanish"
    assert parsed.amount == Decimal("250000")
    assert parsed.confidence == pytest.approx(0.86)


async def test_llm_failure_falls_back_to_rules():
    llm = FakeLLM(error=LLMError("timeout"))
    parsed = await TransactionParser(llm).parse(samples.MANUAL_FOOD, TZ, NOW)
    assert parsed.amount == Decimal("250000")
    assert parsed.transaction_type is None


async def test_llm_date_is_dropped_when_text_has_no_date():
    llm = FakeLLM(llm_result(occurred_at="2026-11-19T15:30:00+05:00"))
    parsed = await TransactionParser(llm).parse(samples.MANUAL_FOOD, TZ, NOW)
    assert parsed.occurred_at is None
    assert "occurred_at" in parsed.missing_fields


async def test_llm_date_is_kept_when_text_mentions_one():
    llm = FakeLLM(llm_result(occurred_at="2026-11-17T20:00:00"))
    parsed = await TransactionParser(llm).parse("17-noyabr kechqurun 20:00 da Kamolonda 250 ming", TZ, NOW)
    assert parsed.occurred_at == datetime(2026, 11, 17, 20, 0, tzinfo=TZ)


async def test_llm_card_digits_are_dropped_when_absent_from_text():
    llm = FakeLLM(llm_result(card_last4="9999", card_network="Visa"))
    parsed = await TransactionParser(llm).parse(samples.MANUAL_FOOD, TZ, NOW)
    assert parsed.card_last4 is None


async def test_llm_receives_masked_text_only():
    llm = FakeLLM(llm_result())
    await TransactionParser(llm).parse("8600123456789012 kartamdan Kamolonga 250 ming", TZ, NOW)
    assert "8600123456789012" not in llm.calls[0]


async def test_parser_without_llm_returns_rule_result():
    parsed = await TransactionParser(None).parse(samples.MANUAL_FOOD, TZ, NOW)
    assert parsed.transaction_type is None
    assert parsed.amount == Decimal("250000")


def test_balance_written_before_the_amount_is_not_taken_as_amount():
    parsed = rule_parse("Balans: 1 000 000 UZS. Xarid 50 000 UZS, KORZINKA. 19.11.2026 10:15")
    assert parsed.amount == Decimal("50000")


def test_message_with_only_a_balance_has_no_amount():
    parsed = rule_parse("Karta *1234. Qoldiq: 2 345 000 so'm")
    assert parsed.amount is None


# --- Screenshot ------------------------------------------------------------------------ #

from app.services.llm import ImageInput  # noqa: E402

IMAGE = ImageInput(b"\xff\xd8fake", "image/jpeg")


class FakeVisionLLM(FakeLLM):
    async def parse_screenshot(self, image, tz_name, now, categories):
        self.calls.append(image)
        if self.error:
            raise self.error
        return LLMTransaction.model_validate(self.result)


def vision_result(**overrides) -> dict:
    base = llm_result(
        card_last4="1234", card_network="Humo", occurred_at="2026-11-19T12:01:00+05:00",
        visible_text="Oplata\n➖ 250.000,00 UZS\n📍 KAMOLON\n💳 HUMOCARD *1234\n🕓 12:01 19.11.2026",
    )  # fmt: skip
    return base | overrides


async def test_screenshot_is_parsed_through_llm_and_marked_as_screenshot():
    llm = FakeVisionLLM(vision_result())
    parsed = await TransactionParser(llm).parse_screenshot(IMAGE, TZ, NOW)
    assert llm.calls == [IMAGE]
    assert parsed.source == "screenshot"
    assert parsed.amount == Decimal("250000")
    assert parsed.transaction_type == "expense"
    assert parsed.card_last4 == "1234"
    assert parsed.occurred_at == datetime(2026, 11, 19, 12, 1, tzinfo=TZ)
    assert "KAMOLON" in parsed.raw_text


async def test_screenshot_text_never_keeps_full_card_number():
    llm = FakeVisionLLM(vision_result(visible_text="Karta 8600123456789012 Oplata 250 000 UZS 19.11.2026 12:01", card_last4="9012"))
    parsed = await TransactionParser(llm).parse_screenshot(IMAGE, TZ, NOW)
    assert "8600123456789012" not in parsed.raw_text
    assert parsed.card_last4 == "9012"


async def test_screenshot_card_and_date_must_be_visible_in_the_picture():
    llm = FakeVisionLLM(vision_result(visible_text="Kamolon 250 000 so'm", card_last4="7777"))
    parsed = await TransactionParser(llm).parse_screenshot(IMAGE, TZ, NOW)
    assert parsed.card_last4 is None
    assert parsed.occurred_at is None


async def test_screenshot_without_llm_is_not_supported():
    parser = TransactionParser(None)
    assert parser.supports_screenshots is False
    with pytest.raises(LLMError):
        await parser.parse_screenshot(IMAGE, TZ, NOW)


async def test_screenshot_llm_failure_is_reported():
    with pytest.raises(LLMError):
        await TransactionParser(FakeVisionLLM(error=LLMError("down"))).parse_screenshot(IMAGE, TZ, NOW)
