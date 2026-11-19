"""Bot xabarlarining ko'rinishi: har qatorda bitta gap, bo'limlar orasida bo'sh qator."""

import re

import pytest

from app.bot import texts

MESSAGES = {
    name: value
    for name, value in vars(texts).items()
    if name.isupper() and isinstance(value, str) and not name.startswith(("BTN_", "MARK_"))
}

TWO_SENTENCES_ON_ONE_LINE = re.compile(r"[.!?]\s+\S")


@pytest.mark.parametrize("name", sorted(MESSAGES))
def test_each_line_holds_one_sentence(name):
    for line in MESSAGES[name].splitlines():
        assert not TWO_SENTENCES_ON_ONE_LINE.search(line.strip()), f"{name}: {line!r}"


@pytest.mark.parametrize("name", sorted(name for name, value in MESSAGES.items() if "asalan" in value))
def test_examples_stand_in_their_own_paragraph(name):
    assert "\n\nMasalan" in MESSAGES[name], name


@pytest.mark.parametrize("name", sorted(MESSAGES))
def test_messages_have_no_stray_whitespace(name):
    value = MESSAGES[name]
    assert value == value.strip() or name == "TRANSFER_FEE"
    assert "\n\n\n" not in value
    assert not any(line != line.rstrip() for line in value.splitlines())


def test_help_groups_commands_under_headings():
    blocks = texts.HELP.split("\n\n")
    assert len(blocks) >= 5
    assert any(block.startswith("<b>Hisobotlar</b>\n📊 /report") for block in blocks)
    assert blocks[-1].startswith("🔒")


def test_settings_lists_each_value_on_its_own_line():
    text = texts.SETTINGS.format(timezone="Asia/Tashkent", currency="UZS")
    title, values, reports = text.split("\n\n")
    assert title == "⚙️ <b>Sozlamalar</b>"
    assert values.splitlines() == ["🕓 Vaqt zonasi: Asia/Tashkent", "💱 Valyuta: UZS"]
    assert reports.splitlines()[0] == "🔔 <b>Avtomatik hisobotlar</b>"
    assert len(reports.splitlines()) == 4


def test_questions_are_separated_from_the_details_above_them():
    for text in (texts.DUPLICATE_WARNING, texts.DELETE_CONFIRM, texts.TRANSFER_SUSPECTED_SAVED, texts.WIPE_CONFIRM):
        assert text.split("\n\n")[-1].endswith("?"), text


# Xabar ichida ishlatiladigan bo'laklar (o'zi alohida xabar emas).
FRAGMENTS = {
    "TRANSFER_FEE", "INACTIVE", "ALL_CARDS", "ALL_CATEGORIES", "UNKNOWN_CARD", "UNKNOWN_CATEGORY",
    "WEEKLY_HEADING", "DAILY_HEADING", "MONTHLY_HEADING", "REPORT_HEADING", "DAILY_MORE",
}  # fmt: skip


@pytest.mark.parametrize("name", sorted(set(MESSAGES) - FRAGMENTS))
def test_every_message_starts_with_an_emoji(name):
    first = MESSAGES[name][0]
    assert ord(first) > 0x2000 and not first.isalpha(), f"{name}: {MESSAGES[name][:30]!r}"


def test_each_help_command_has_its_own_emoji():
    command_lines = [line for line in texts.HELP.splitlines() if "/" in line and " — " in line]
    assert len(command_lines) == 10
    assert all(not line.startswith("/") for line in command_lines)
