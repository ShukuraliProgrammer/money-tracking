import pytest

from app.utils.validators import (
    contains_secret_code,
    is_valid_last4,
    mask_card_numbers,
    normalize_merchant,
    normalize_text,
)


def test_mask_card_numbers_hides_full_pan_and_keeps_last4():
    masked, hints = mask_card_numbers("Karta 8600 1234 5678 9012 dan to'lov")
    assert "8600 1234 5678" not in masked
    assert "****9012" in masked
    assert hints[0].last4 == "9012"
    assert hints[0].network == "Uzcard"


def test_mask_card_numbers_hides_contiguous_pan():
    masked, hints = mask_card_numbers("9860123456781234")
    assert masked == "****1234"
    assert hints[0].network == "Humo"


@pytest.mark.parametrize(
    ("pan", "network"),
    [
        ("4111111111111111", "Visa"),
        ("5500000000000004", "Mastercard"),
        ("5614681234567890", "Uzcard"),
        ("1234567890123456", "Unknown"),
    ],
)
def test_mask_card_numbers_detects_network_from_prefix(pan, network):
    _, hints = mask_card_numbers(pan)
    assert hints[0].network == network


def test_mask_card_numbers_normalizes_partially_masked_pan():
    masked, hints = mask_card_numbers("Karta 860012******1234")
    assert masked == "Karta ****1234"
    assert hints[0].last4 == "1234"
    assert hints[0].network == "Uzcard"


@pytest.mark.parametrize("text", ["💳 ***1234", "💳 HUMOCARD *1234", "Karta **** 1234", "•••• 1234"])
def test_mask_card_numbers_reads_short_masks(text):
    masked, hints = mask_card_numbers(text)
    assert hints[0].last4 == "1234"
    assert "****1234" in masked


def test_mask_card_numbers_leaves_amounts_alone():
    masked, hints = mask_card_numbers("➖ 1.234.567,00 UZS 19.11.2026 10:15")
    assert masked == "➖ 1.234.567,00 UZS 19.11.2026 10:15"
    assert hints == []


@pytest.mark.parametrize(
    "text",
    [
        "Tasdiqlash kodi: 123456",
        "Kod podtverzhdeniya 4821. Nikomu ne soobshayte!",
        "Код: 7741. Никому не сообщайте",
        "CVV 123",
        "PIN-kod 4455",
        "SMS kod 998877 hech kimga aytmang",
    ],
)
def test_contains_secret_code_detects_otp_like_messages(text):
    assert contains_secret_code(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "💸 Oplata\n➖ 54.000,00 UZS\n📍 YANDEX GO\n💳 HUMOCARD *1234",
        "Kamolonda 250 ming so'm ovqatlandik",
        "Pokupka: 12.50 USD. Karta *4321. Kod avtorizatsii 123456",
    ],
)
def test_contains_secret_code_ignores_normal_transactions(text):
    assert contains_secret_code(text) is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("KORZINKA", "korzinka"),
        ("Korzinka 24", "korzinka"),
        ("YANDEX GO, UZ", "yandex go"),
        ("  Kamolon   Osh-Markazi ", "kamolon osh markazi"),
        ("O‘zbegim", "o'zbegim"),
    ],
)
def test_normalize_merchant(raw, expected):
    assert normalize_merchant(raw) == expected


def test_normalize_text_unifies_apostrophes():
    assert normalize_text("SO‘M toʻlov") == "so'm to'lov"


@pytest.mark.parametrize(("value", "ok"), [("1234", True), ("12a4", False), ("123", False), ("12345", False)])
def test_is_valid_last4(value, ok):
    assert is_valid_last4(value) is ok


from app.utils.validators import contains_full_card_number, split_emoji  # noqa: E402


@pytest.mark.parametrize(
    ("text", "expected"),
    [("8600 1234 5678 9012", True), ("8600123456789012", True), ("💳 ***1234", False), ("250 000 UZS", False)],
)
def test_contains_full_card_number(text, expected):
    assert contains_full_card_number(text) is expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("🚕 Transport", ("🚕", "Transport")),
        ("Transport", ("🏷", "Transport")),
        ("  Uy va kommunal ", ("🏷", "Uy va kommunal")),
        ("-Chegirma", ("🏷", "-Chegirma")),
    ],
)
def test_split_emoji(raw, expected):
    assert split_emoji(raw) == expected
