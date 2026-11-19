import csv
import io
from datetime import datetime
from decimal import Decimal

from app.schemas import NoteAnalysis
from app.services import transaction_service as ts
from app.services.export_service import CSV_COLUMNS, build_csv, export_filename
from tests.conftest import TZ, category_named, make_parsed


def read_rows(data: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))


async def make_tx(session, user, **overrides):
    note = overrides.pop("note", "Kamolonda ovqatlandik 3 kishi")
    card = await ts.find_card_by_last4(session, user.id, "1234") or await ts.add_card(
        session, user.id, name="Asosiy", last4="1234", network="Uzcard"
    )
    food = await category_named(session, user.id, "Ovqatlanish")
    return await ts.create_transaction(session, user, make_parsed(**overrides), note, food.id, card.id, NoteAnalysis())


async def test_csv_has_expected_columns_and_values(session, user):
    tx = await make_tx(session, user)
    data = build_csv([tx], TZ)
    assert data.startswith(b"\xef\xbb\xbf")  # Excel o'zbekcha harflarni to'g'ri ochishi uchun BOM
    rows = read_rows(data)
    assert list(rows[0].keys()) == list(CSV_COLUMNS)
    assert rows[0] == {
        "date": "2026-11-19 10:15",
        "type": "expense",
        "amount": "250000",
        "currency": "UZS",
        "merchant": "KAMOLON",
        "category": "Ovqatlanish",
        "user_note": "Kamolonda ovqatlandik 3 kishi",
        "card_last4": "1234",
        "source": "cardxabar",
    }


async def test_csv_keeps_cents_and_handles_missing_relations(session, user):
    parsed = make_parsed(amount=Decimal("12.50"), currency="USD", merchant=None)
    tx = await ts.create_transaction(session, user, parsed, None, None, None, NoteAnalysis())
    row = read_rows(build_csv([tx], TZ))[0]
    assert row["amount"] == "12.50"
    assert row["merchant"] == "" and row["category"] == "" and row["card_last4"] == "" and row["user_note"] == ""


async def test_csv_neutralizes_spreadsheet_formulas(session, user):
    tx = await make_tx(session, user, merchant="=HYPERLINK(1)", note="+SUM(A1)")
    row = read_rows(build_csv([tx], TZ))[0]
    assert row["merchant"] == "'=HYPERLINK(1)"
    assert row["user_note"] == "'+SUM(A1)"


def test_csv_without_transactions_has_only_header():
    assert build_csv([], TZ).decode("utf-8-sig").strip() == ",".join(CSV_COLUMNS)


def test_export_filename_is_safe_ascii():
    assert export_filename("Noyabr 2026", datetime(2026, 11, 19, tzinfo=TZ)) == "moneytrack_noyabr_2026_20261119.csv"
