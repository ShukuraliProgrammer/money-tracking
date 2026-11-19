import logging

from app.utils.logging import RedactingFormatter, redact


def test_redact_hides_bot_token():
    text = redact("Bot 123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw started")
    assert "AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw" not in text
    assert "[TOKEN]" in text


def test_redact_hides_api_keys():
    text = redact("key=sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789")
    assert "abcdefghijklmnop" not in text


def test_redact_masks_card_numbers():
    assert redact("card 8600 1234 5678 9012 charged") == "card ****9012 charged"


def test_formatter_redacts_message_arguments_and_tracebacks():
    formatter = RedactingFormatter("%(levelname)s %(message)s")
    try:
        raise ValueError("failed for card 8600123456789012")
    except ValueError:
        import sys

        record = logging.LogRecord("t", logging.ERROR, __file__, 1, "token %s", ("123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw",), sys.exc_info())
    output = formatter.format(record)
    assert "8600123456789012" not in output
    assert "AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw" not in output
    assert "ValueError" in output
