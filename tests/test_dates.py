from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.utils.dates import (
    find_datetime,
    format_dt,
    month_label,
    parse_user_datetime,
    period_range,
)

TZ = ZoneInfo("Asia/Tashkent")
NOW = datetime(2026, 11, 19, 15, 30, tzinfo=TZ)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("🕓 12:01 19.11.2026", datetime(2026, 11, 19, 12, 1, tzinfo=TZ)),
        ("🕓 19.11.26 10:15", datetime(2026, 11, 19, 10, 15, tzinfo=TZ)),
        ("19.11.2026 10:15:42", datetime(2026, 11, 19, 10, 15, 42, tzinfo=TZ)),
        ("2026-11-19 10:15", datetime(2026, 11, 19, 10, 15, tzinfo=TZ)),
        ("2026-11-19T10:15:00", datetime(2026, 11, 19, 10, 15, tzinfo=TZ)),
        ("19/11/2026, 10:15", datetime(2026, 11, 19, 10, 15, tzinfo=TZ)),
    ],
)
def test_find_datetime_reads_notification_formats(text, expected):
    match = find_datetime(text, TZ)
    assert match is not None
    assert match.value == expected
    assert match.has_time is True


def test_find_datetime_reads_date_without_time():
    match = find_datetime("sana 19.11.2026 da", TZ)
    assert match.value == datetime(2026, 11, 19, 0, 0, tzinfo=TZ)
    assert match.has_time is False


def test_find_datetime_returns_none_when_no_date():
    assert find_datetime("Kamolonda 250 ming so'm", TZ) is None


def test_find_datetime_ignores_impossible_dates():
    assert find_datetime("45.13.2026 10:15", TZ) is None


def test_find_datetime_reports_span_of_matched_text():
    text = "xarid 19.11.2026 10:15 KORZINKA"
    match = find_datetime(text, TZ)
    assert text[match.start : match.end] == "19.11.2026 10:15"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("19.11.2026 10:15", datetime(2026, 11, 19, 10, 15, tzinfo=TZ)),
        ("18.11 09:00", datetime(2026, 11, 18, 9, 0, tzinfo=TZ)),
        ("10:15", datetime(2026, 11, 19, 10, 15, tzinfo=TZ)),
        ("kecha 21:40", datetime(2026, 11, 18, 21, 40, tzinfo=TZ)),
        ("kecha", datetime(2026, 11, 18, 15, 30, tzinfo=TZ)),
        ("bugun", NOW),
        ("hozir", NOW),
    ],
)
def test_parse_user_datetime(text, expected):
    assert parse_user_datetime(text, TZ, NOW) == expected


def test_parse_user_datetime_rejects_garbage():
    assert parse_user_datetime("bilmayman", TZ, NOW) is None


def test_format_dt_uses_user_timezone():
    utc_value = datetime(2026, 11, 19, 5, 15, tzinfo=ZoneInfo("UTC"))
    assert format_dt(utc_value, TZ) == "19.11.2026 10:15"


def test_period_range_today():
    period = period_range("d", TZ, NOW)
    assert period.start == datetime(2026, 11, 19, 0, 0, tzinfo=TZ)
    assert period.end == datetime(2026, 11, 20, 0, 0, tzinfo=TZ)


def test_period_range_week_starts_on_monday():
    period = period_range("w", TZ, NOW)  # 19.11.2026 is Thursday
    assert period.start == datetime(2026, 11, 16, 0, 0, tzinfo=TZ)
    assert period.end == datetime(2026, 11, 23, 0, 0, tzinfo=TZ)


def test_period_range_this_month():
    period = period_range("m", TZ, NOW)
    assert period.start == datetime(2026, 11, 1, tzinfo=TZ)
    assert period.end == datetime(2026, 12, 1, tzinfo=TZ)
    assert period.label == "Noyabr 2026"


def test_period_range_previous_month_crosses_year():
    period = period_range("pm", TZ, datetime(2027, 1, 5, tzinfo=TZ))
    assert period.start == datetime(2026, 12, 1, tzinfo=TZ)
    assert period.end == datetime(2027, 1, 1, tzinfo=TZ)
    assert period.label == "Dekabr 2026"


def test_period_range_explicit_month():
    period = period_range("2026-02", TZ, NOW)
    assert period.start == datetime(2026, 2, 1, tzinfo=TZ)
    assert period.end == datetime(2026, 3, 1, tzinfo=TZ)


def test_period_range_last_30_days():
    period = period_range("30", TZ, NOW)
    assert period.start == datetime(2026, 10, 21, 0, 0, tzinfo=TZ)
    assert period.end == datetime(2026, 11, 20, 0, 0, tzinfo=TZ)


def test_period_range_all_time_has_no_start():
    period = period_range("all", TZ, NOW)
    assert period.start is None


def test_period_range_rejects_unknown_code():
    with pytest.raises(ValueError):
        period_range("nonsense", TZ, NOW)


def test_month_label():
    assert month_label(2026, 11) == "Noyabr 2026"
