"""Sana va vaqtni o‘qish, ko‘rsatish hamda hisobot davrlarini hisoblash."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.utils.validators import normalize_text

UZ_MONTHS = (
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
)  # fmt: skip

_TIME = r"(\d{1,2}):(\d{2})(?::(\d{2}))?"
_DMY = r"(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2})"

_ISO_DATETIME = re.compile(rf"(?<!\d)(\d{{4}})-(\d{{2}})-(\d{{2}})[T ]{_TIME}")
_TIME_THEN_DATE = re.compile(rf"(?<!\d){_TIME},?\s+{_DMY}(?!\d)")
_DATE_THEN_TIME = re.compile(rf"(?<!\d){_DMY},?\s+{_TIME}(?!\d)")
_ISO_DATE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_DATE_ONLY = re.compile(r"(?<!\d)(\d{1,2})[./](\d{1,2})[./](\d{4}|\d{2})(?!\d)")


@dataclass(frozen=True)
class DateMatch:
    value: datetime
    has_time: bool
    start: int
    end: int


@dataclass(frozen=True)
class Period:
    start: datetime | None
    end: datetime
    label: str


def _build(tz: ZoneInfo, year: str, month: str, day: str, hour="0", minute="0", second=None) -> datetime | None:
    full_year = int(year) + 2000 if len(year) == 2 else int(year)
    try:
        return datetime(full_year, int(month), int(day), int(hour), int(minute), int(second or 0), tzinfo=tz)
    except ValueError:
        return None


def find_datetime(text: str, tz: ZoneInfo) -> DateMatch | None:
    """Matndagi birinchi sanani (va bo‘lsa vaqtni) topadi. Topilmasa ``None``."""
    candidates: list[DateMatch] = []
    for match in _ISO_DATETIME.finditer(text):
        year, month, day, hour, minute, second = match.groups()
        value = _build(tz, year, month, day, hour, minute, second)
        if value:
            candidates.append(DateMatch(value, True, match.start(), match.end()))
    for match in _TIME_THEN_DATE.finditer(text):
        hour, minute, second, day, month, year = match.groups()
        value = _build(tz, year, month, day, hour, minute, second)
        if value:
            candidates.append(DateMatch(value, True, match.start(), match.end()))
    for match in _DATE_THEN_TIME.finditer(text):
        day, month, year, hour, minute, second = match.groups()
        value = _build(tz, year, month, day, hour, minute, second)
        if value:
            candidates.append(DateMatch(value, True, match.start(), match.end()))
    if candidates:
        return min(candidates, key=lambda item: item.start)

    for match in _ISO_DATE.finditer(text):
        value = _build(tz, *match.groups())
        if value:
            return DateMatch(value, False, match.start(), match.end())
    for match in _DATE_ONLY.finditer(text):
        day, month, year = match.groups()
        value = _build(tz, year, month, day)
        if value:
            return DateMatch(value, False, match.start(), match.end())
    return None


_RELATIVE_DAYS = {
    "hozir": 0, "bugun": 0, "now": 0, "today": 0, "сегодня": 0, "сейчас": 0,
    "kecha": 1, "yesterday": 1, "вчера": 1,
}  # fmt: skip
_SHORT_DATE = re.compile(r"(?<!\d)(\d{1,2})[./](\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?(?![\d./])")
_TIME_ONLY = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)")


def relative_day_offset(text: str) -> int | None:
    """«kecha», «bugun» kabi so‘zlar bo‘lsa, necha kun oldinligini qaytaradi."""
    words = set(re.findall(r"[^\W\d_]+", normalize_text(text)))
    offsets = [offset for word, offset in _RELATIVE_DAYS.items() if word in words]
    return max(offsets) if offsets else None


def parse_user_datetime(text: str, tz: ZoneInfo, now: datetime) -> datetime | None:
    """Foydalanuvchi qo‘lda yozgan sanani o‘qiydi: «19.11.2026 10:15», «kecha 21:40», «10:15»."""
    now = now.astimezone(tz)
    found = find_datetime(text, tz)
    if found:
        return found.value

    offset = relative_day_offset(text)
    time_match = _TIME_ONLY.search(text)
    if offset is not None:
        base = now - timedelta(days=offset)
        if time_match:
            return _with_time(base, time_match.group(1), time_match.group(2))
        return base

    short = _SHORT_DATE.search(text)
    if short:
        day, month, hour, minute = short.groups()
        value = _build(tz, str(now.year), month, day, hour or "0", minute or "0")
        if value and value > now + timedelta(days=1):
            value = _build(tz, str(now.year - 1), month, day, hour or "0", minute or "0")
        return value

    if time_match:
        return _with_time(now, time_match.group(1), time_match.group(2))
    return None


def _with_time(base: datetime, hour: str, minute: str) -> datetime | None:
    try:
        return base.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
    except ValueError:
        return None


def format_dt(value: datetime, tz: ZoneInfo) -> str:
    """«19.11.2026 10:15» ko‘rinishida, foydalanuvchi vaqt zonasida."""
    return value.astimezone(tz).strftime("%d.%m.%Y %H:%M")


def month_label(year: int, month: int) -> str:
    return f"{UZ_MONTHS[month - 1]} {year}"


def _month_start(tz: ZoneInfo, year: int, month: int) -> datetime:
    return datetime(year, month, 1, tzinfo=tz)


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def previous_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def period_range(code: str, tz: ZoneInfo, now: datetime) -> Period:
    """Hisobot davri kodini (d, w, m, pm, 30, all, YYYY-MM) aniq vaqt oralig‘iga aylantiradi."""
    now = now.astimezone(tz)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)

    if code == "d":
        return Period(today, tomorrow, "Bugun")
    if code == "w":
        monday = today - timedelta(days=today.weekday())
        return Period(monday, monday + timedelta(days=7), "Bu hafta")
    if code == "30":
        return Period(today - timedelta(days=29), tomorrow, "Oxirgi 30 kun")
    if code == "all":
        return Period(None, tomorrow, "Hamma vaqt")

    if code == "m":
        year, month = now.year, now.month
    elif code == "pm":
        year, month = previous_month(now.year, now.month)
    elif re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", code):
        year, month = int(code[:4]), int(code[5:])
    else:
        raise ValueError(f"Unknown period code: {code!r}")
    return Period(_month_start(tz, year, month), _month_start(tz, *_next_month(year, month)), month_label(year, month))
