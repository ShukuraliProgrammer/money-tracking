"""Foydalanuvchi izohini («Bu nima uchun edi?») tahlil qilish.

Qoidalar har doim ishlaydi. LLM sozlangan bo‘lsa, natija u bilan boyitiladi;
LLM ishlamasa, qoidalar natijasi qoladi.
"""

from __future__ import annotations

import logging
import re
from typing import Protocol

from app.schemas import LLMNoteAnalysis, NoteAnalysis
from app.services.llm import LLMError
from app.utils.validators import normalize_text

logger = logging.getLogger(__name__)

_PEOPLE = re.compile(r"(\d{1,3})\s*(?:kishi|nafar|odam|человек|чел\b|people|persons?)")
_HASHTAG = re.compile(r"#([^\W\d_][\w']{1,23})")

_RECURRING: tuple[tuple[str, str], ...] = (
    (r"har\s+kuni|kunlik|daily|ежедневн", "daily"),
    (r"har\s+hafta|haftalik|weekly|еженедельн", "weekly"),
    (r"har\s+oy|oylik\s+to'lov|ijara|abonent|obuna|kommunal|subscription|monthly|ежемесячн|аренд|подписк", "monthly"),
    (r"har\s+yil|yillik|yearly|annual|ежегодн", "yearly"),
)

# Kalit so‘z → standart tur nomi. Faqat foydalanuvchida shu nomli tur bo‘lsa taklif qilinadi.
_CATEGORY_KEYWORDS: tuple[tuple[str, str], ...] = (
    (r"qarz(?:ga)?\s+berdim|qarz\s+berish|одолжил|дал\s+в\s+долг", "Qarz berish"),
    (r"qarz(?:ga)?\s+oldim|qarz\s+olish|взял\s+в\s+долг|занял", "Qarz olish"),
    (r"maosh|oylik\s+keldi|oylik\s+tushdi|avans|ish\s+haqi|зарплат|аванс|salary", "Maosh"),
    (r"investitsiya|aksiya|obligatsiya|depozit|omonat|инвест|акци|депозит|invest", "Investitsiya"),
    (r"ijara|kvartira|kommunal|svet|gaz\b|elektr|uy\s+uchun|uyga|internet|аренд|коммунал|rent", "Uyga to‘lov"),
    (
        r"ovqat|tushlik|nonushta|kechki|kafe|restoran|choyxona|osh\b|burger|pizza|lavash|kofe"
        r"|обед|ужин|завтрак|кафе|ресторан|lunch|dinner|food",
        "Ovqatlanish",
    ),
    (r"p2p|o'tkazma|o'tkazdim|tashladim|tashlab\s+berdi|perevod|перевод|перевел|transfer", "P2P"),
    (r"sotib\s+oldim|kiyim|xarid|telefon|oyoq\s+kiyim|bozor|купил|покупк|одежд|bought", "Narsa sotib olish"),
)


def _match_category(guess: str | None, category_names: list[str]) -> str | None:
    if not guess:
        return None
    wanted = normalize_text(guess.strip())
    return next((name for name in category_names if normalize_text(name) == wanted), None)


def heuristic_analysis(note: str, merchant: str | None, category_names: list[str]) -> NoteAnalysis:
    text = normalize_text(f"{note} {merchant or ''}")
    note_text = normalize_text(note)

    people = _PEOPLE.search(note_text)
    people_count = int(people.group(1)) if people and int(people.group(1)) >= 1 else None

    period = next((name for pattern, name in _RECURRING if re.search(pattern, note_text)), "none")

    guess = next((name for pattern, name in _CATEGORY_KEYWORDS if re.search(pattern, text)), None)

    return NoteAnalysis(
        category_guess=_match_category(guess, category_names),
        tags=list(dict.fromkeys(_HASHTAG.findall(note_text)))[:5],
        people_count=people_count,
        is_shared_expense=bool(people_count and people_count > 1),
        is_recurring=period != "none",
        recurring_period=period,
    )


class NoteLLM(Protocol):
    async def analyze_note(
        self, note: str, merchant: str | None, transaction_type: str | None, categories: list[str]
    ) -> LLMNoteAnalysis: ...


class NoteAnalyzer:
    def __init__(self, llm: NoteLLM | None) -> None:
        self._llm = llm

    async def analyze(
        self, note: str, merchant: str | None, transaction_type: str | None, category_names: list[str]
    ) -> NoteAnalysis:
        fallback = heuristic_analysis(note, merchant, category_names)
        if self._llm is None:
            return fallback
        try:
            answer = await self._llm.analyze_note(note, merchant, transaction_type, category_names)
        except LLMError as error:
            logger.warning("LLM note analysis failed, using heuristics: %s", error)
            return fallback
        return NoteAnalysis(
            category_guess=_match_category(answer.category_guess, category_names) or fallback.category_guess,
            tags=answer.tags or fallback.tags,
            people_count=answer.people_count or fallback.people_count,
            is_shared_expense=answer.is_shared_expense or fallback.is_shared_expense,
            is_recurring=answer.is_recurring or fallback.is_recurring,
            recurring_period=answer.recurring_period if answer.is_recurring else fallback.recurring_period,
            summary=answer.summary,
        )
