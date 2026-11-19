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
