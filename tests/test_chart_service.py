"""Avtomatik hisobot rasmi."""

import io
from datetime import datetime
from decimal import Decimal

from PIL import Image

from app.models import Card, Category, Transaction
from app.services.chart_service import BAR_COLOR, IMAGE_WIDTH, bar_lengths, render_report_image, top_rows
from app.services.report_service import summarize
from tests.conftest import TZ

WHEN = datetime(2026, 11, 19, 10, 15, tzinfo=TZ)
_ids = iter(range(1, 10_000))


def tx(amount, category=None, kind="expense", emoji="🏷") -> Transaction:
    item = Transaction(
        id=next(_ids), user_id=1, transaction_type=kind, amount=Decimal(str(amount)), currency="UZS",
        merchant="JOY", occurred_at=WHEN, tags=[], recurring_period="none", source="manual",
    )  # fmt: skip
    item.card = Card(id=1, user_id=1, name="Asosiy", card_last4="1234", card_network="Humo")
    item.category = Category(id=1, user_id=1, name=category, emoji=emoji) if category else None
    return item


def uzs_report(transactions):
    return summarize(transactions).currencies[0]


def open_image(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGB")


def bar_widths(image: Image.Image) -> list[int]:
    """Rasmdagi har bir ustunning piksel uzunligi, yuqoridan pastga."""
    pixels = image.load()
    widths, previous = [], 0
    for y in range(image.height):
        count = sum(1 for x in range(image.width) if pixels[x, y] == BAR_COLOR)
        if count and not previous:
            widths.append(count)
        elif count and widths:
            widths[-1] = max(widths[-1], count)
        previous = count
    return widths


# --- Ma'lumotni tayyorlash ---------------------------------------------------- #


def test_top_rows_are_expenses_by_category_largest_first_without_emoji():
    report = uzs_report([tx(350000, "Ovqatlanish", emoji="🍽"), tx(900000, "Narsa sotib olish", emoji="🛍"), tx(50000)])
    rows = top_rows(report)
    assert [(row.label, row.amount) for row in rows] == [
        ("Narsa sotib olish", Decimal("900000")),
        ("Ovqatlanish", Decimal("350000")),
        ("Tursiz", Decimal("50000")),
    ]


def test_top_rows_skip_categories_without_expense():
    report = uzs_report([tx(12000000, "Maosh", kind="income"), tx(1000, "Ovqatlanish")])
    assert [row.label for row in top_rows(report)] == ["Ovqatlanish"]


def test_top_rows_fold_the_tail_into_one_row():
    report = uzs_report([tx(1000 * (n + 1), f"Tur {n}") for n in range(10)])
    rows = top_rows(report, limit=6)
    assert len(rows) == 6
    assert rows[-1].label == "Qolganlari"
    assert rows[-1].amount == Decimal("15000")  # eng kichik 5 ta: 1000+2000+3000+4000+5000
    assert sum(row.amount for row in rows) == Decimal("55000")


def test_bar_lengths_are_proportional_to_the_largest():
    assert bar_lengths([Decimal("900"), Decimal("450"), Decimal("90")], 600) == [600, 300, 60]


def test_bar_lengths_keep_tiny_values_visible_and_zero_empty():
    assert bar_lengths([Decimal("1000000"), Decimal("1"), Decimal("0")], 600) == [600, 4, 0]


def test_bar_lengths_for_no_data():
    assert bar_lengths([], 600) == []


# --- Rasm ------------------------------------------------------------------------- #


def test_image_is_png_of_fixed_width():
    data = render_report_image("Haftalik hisobot", "09.11 – 15.11.2026", uzs_report([tx(1000, "Ovqatlanish")]))
    assert data.startswith(b"\x89PNG")
    assert open_image(data).width == IMAGE_WIDTH


def test_image_draws_one_bar_per_category_in_proportion():
    report = uzs_report([tx(900000, "Narsa sotib olish"), tx(300000, "Ovqatlanish"), tx(12000000, "Maosh", kind="income")])
    widths = bar_widths(open_image(render_report_image("Oylik hisobot", "Noyabr 2026", report)))
    assert len(widths) == 2
    assert abs(widths[0] / widths[1] - 3) < 0.1


def test_image_without_expenses_has_no_bars():
    report = uzs_report([tx(12000000, "Maosh", kind="income")])
    assert bar_widths(open_image(render_report_image("Oylik hisobot", "Noyabr 2026", report))) == []


def test_image_grows_with_number_of_categories():
    short = open_image(render_report_image("H", "D", uzs_report([tx(1000, "A")])))
    tall = open_image(render_report_image("H", "D", uzs_report([tx(1000 + n, f"Tur {n}") for n in range(6)])))
    assert tall.height > short.height


def test_image_handles_cyrillic_long_names_and_other_currencies():
    report = uzs_report([tx(5000, "Жуда узун кириллча тур номи, сиғмайдиган даражада узун " * 2), tx(700, "O‘yin-kulgi")])
    data = render_report_image("Oylik hisobot", "Noyabr 2026", report, other_currencies=["USD", "EUR"])
    assert open_image(data).width == IMAGE_WIDTH
