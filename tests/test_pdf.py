"""PDF chekdan matn olish."""

from datetime import datetime
from decimal import Decimal

import pytest

from app.services.parser import RuleBasedParser
from app.utils.pdf import PdfError, extract_pdf_text
from tests.conftest import TZ
from tests.pdf_samples import RECEIPT_LINES, make_pdf, make_scanned_pdf

NOW = datetime(2026, 11, 19, 15, 30, tzinfo=TZ)


def test_text_is_extracted_line_by_line():
    text = extract_pdf_text(make_pdf(RECEIPT_LINES))
    assert text.splitlines() == RECEIPT_LINES


def test_scanned_pdf_has_no_text():
    assert extract_pdf_text(make_scanned_pdf()) == ""


def test_broken_file_raises():
    with pytest.raises(PdfError):
        extract_pdf_text(b"this is not a pdf")


def test_blank_lines_and_extra_spaces_are_removed():
    text = extract_pdf_text(make_pdf(["Amount    150 000.00   UZS", "", "   ", "Status Success"]))
    assert text.splitlines() == ["Amount 150 000.00 UZS", "Status Success"]


def test_receipt_text_is_understood_by_the_rules():
    parsed = RuleBasedParser().parse(extract_pdf_text(make_pdf(RECEIPT_LINES)), TZ, NOW, source_hint="pdf")
    assert parsed.source == "pdf"
    assert parsed.amount == Decimal("150000")
    assert parsed.currency == "UZS"
    assert parsed.occurred_at == datetime(2026, 11, 19, 14, 0, 22, tzinfo=TZ)
    assert parsed.card_last4 == "9298"  # jo'natuvchi karta (birinchi turgan)
    assert parsed.card_network == "Humo"
    assert parsed.merchant == "ALIYEV VALI"
    assert "986017" not in parsed.raw_text and "860012" not in parsed.raw_text


def test_receiver_card_line_is_not_taken_as_a_name():
    parsed = RuleBasedParser().parse("Receiver 860012******4321\nAmount 5 000 UZS", TZ, NOW, source_hint="pdf")
    assert parsed.merchant is None


# --- Uzum chekining haqiqiy tuzilishi: sarlavhalar ustuni, keyin qiymatlar ustuni ------- #

from tests.pdf_samples import uzum_receipt_lines  # noqa: E402


def parse_uzum(**kwargs):
    text = extract_pdf_text(make_pdf(uzum_receipt_lines(**kwargs)))
    return RuleBasedParser().parse(text, TZ, NOW, source_hint="pdf")


def test_column_receipt_amount_is_the_transfer_amount_not_a_zero_fee():
    parsed = parse_uzum()
    assert parsed.amount == Decimal("1000")
    assert parsed.currency == "UZS"


def test_column_receipt_reads_date_and_both_cards():
    parsed = parse_uzum()
    assert parsed.occurred_at == datetime(2026, 11, 19, 10, 28, 23, tzinfo=TZ)
    assert parsed.transfer is not None
    assert (parsed.transfer.sender_last4, parsed.transfer.sender_network) == ("3344", "Visa")
    assert (parsed.transfer.receiver_last4, parsed.transfer.receiver_network) == ("5566", "Humo")
    assert (parsed.transfer.sender_name, parsed.transfer.receiver_name) == ("TESTOV TEST", "TESTOV T")


def test_column_receipt_does_not_guess_direction():
    # «Received date» so'zi kirim degani emas: yo'nalish foydalanuvchining kartalariga qarab aniqlanadi.
    parsed = parse_uzum()
    assert parsed.transaction_type is None
    assert parsed.card_last4 == "3344" and parsed.card_network == "Visa"  # standart holatda jo'natuvchi
    assert parsed.merchant == "TESTOV T"  # «Transaction ID» emas, qabul qiluvchi ismi


def test_column_receipt_keeps_sender_and_receiver_amounts_apart():
    parsed = parse_uzum(sender_amount="1,005.00 UZS", receiver_amount="1,000.00 UZS", sender_fee="5.00 UZS")
    assert parsed.transfer.sender_amount == Decimal("1005")
    assert parsed.transfer.receiver_amount == Decimal("1000")
    assert parsed.amount == Decimal("1005")


def test_column_receipt_hides_full_card_numbers_and_keeps_source():
    parsed = parse_uzum()
    assert parsed.source == "pdf"
    assert "441122" not in parsed.raw_text and "986017" not in parsed.raw_text
    assert "****3344" in parsed.raw_text and "****5566" in parsed.raw_text


def test_inline_receipt_is_also_a_transfer():
    parsed = RuleBasedParser().parse(extract_pdf_text(make_pdf(RECEIPT_LINES)), TZ, NOW, source_hint="pdf")
    assert parsed.transfer.sender_last4 == "9298" and parsed.transfer.receiver_last4 == "4321"
    assert parsed.amount == Decimal("150000")
    assert parsed.merchant == "ALIYEV VALI"


def test_ordinary_message_is_not_a_transfer_receipt():
    from tests import samples

    assert RuleBasedParser().parse(samples.HUMO_EXPENSE, TZ, NOW).transfer is None
    assert RuleBasedParser().parse("Kamolonda 250 ming so'm ovqatlandik", TZ, NOW).transfer is None


def test_fee_is_never_taken_as_the_amount_in_plain_messages():
    parsed = RuleBasedParser().parse("Komissiya: 500 UZS. Summa: 50 000 UZS. 19.11.2026 10:15", TZ, NOW)
    assert parsed.amount == Decimal("50000")


def test_commission_amount_line_is_not_the_transfer_amount():
    # Ruscha chekda komissiya sarlavhasida ham «сумма» so'zi bor.
    lines = [
        "Отправитель: 986017******9298",
        "Сумма комиссии: 5.00 UZS",
        "Сумма: 150 000.00 UZS",
        "Получатель: 860012******4321",
    ]
    parsed = RuleBasedParser().parse("\n".join(lines), TZ, NOW, source_hint="pdf")
    assert parsed.amount == Decimal("150000")


async def test_transfer_receipt_is_never_sent_to_the_llm():
    from app.services.parser import TransactionParser

    class RecordingLLM:
        calls = 0

        async def parse_transaction(self, *args):
            RecordingLLM.calls += 1
            raise AssertionError("receipt must be read by rules only")

    text = extract_pdf_text(make_pdf(uzum_receipt_lines()))
    parsed = await TransactionParser(RecordingLLM()).parse(text, TZ, NOW, source_hint="pdf")
    assert RecordingLLM.calls == 0
    assert parsed.transaction_type is None and parsed.amount == Decimal("1000")
