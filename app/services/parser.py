"""Xabarni tranzaksiya qoralamasiga aylantirish.

Tartib (B variant): avval qoidalar (regex). CardXabar, HUMO va bank SMS kabi
ma’lum formatlar LLM’siz o‘qiladi. Qoidalar yetarli bo‘lmasa va LLM sozlangan
bo‘lsa, yetishmagan maydonlar LLM’dan so‘raladi.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from app.schemas import LLMTransaction, ParsedTransaction
from app.services.llm import ImageInput, LLMError
from app.utils.dates import find_datetime, relative_day_offset
from app.utils.money import AmountMatch, find_amounts, format_amount
from app.utils.validators import CardHint, mask_card_numbers, unify_apostrophes

logger = logging.getLogger(__name__)

_FLAGS = re.IGNORECASE

_BALANCE = re.compile(
    r"💰|💵|balans|balance|баланс|ostatok|остаток|dostupn|доступн|qoldi[qg']|mavjud|available", _FLAGS
)
_EXPENSE = re.compile(
    r"🔴|💸|oplat|pokupk|platezh|platej|spisan|xarid|to'lov|tolov|to'ladi|chiqim|yechil|yechib"
    r"|debet|debit|purchase|payment|spending|spent|withdraw|снят|оплат|покупк|списан|платеж|платёж"
    r"|расход|sotib\s+ol|berdim|sarfla",
    _FLAGS,
)
_INCOME = re.compile(
    r"🟢|🎉|popolnen|zachisl|postupl|kirim|tushdi|tushum|keldi|qabul\s+qilin|credit|received|income"
    r"|refund|vozvrat|пополнен|зачисл|поступл|возврат|maosh|polucheno|получен|qaytardi|daromad",
    _FLAGS,
)
_COUNT_WORD = re.compile(r"\s*(?:kishi|nafar|odam|ta|dona|marta|kun|soat|km|%|человек|шт)(?![a-zа-яё])", _FLAGS)
_MERCHANT_LABEL = re.compile(
    r"(?:merchant|joy|mesto|место|terminal|torgovets|savdo\s+nuqtasi)\s*[:\-]\s*([^\n]+)", _FLAGS
)
# Chek va kvitansiyalardagi «qabul qiluvchi ismi» qatori (belgi va qiymat orasida ikki nuqta bo‘lmasligi mumkin).
_RECEIVER_LABEL = re.compile(
    r"(?:receiver\s+name|recipient\s+name|имя\s+получателя|qabul\s+qiluvchi(?:ning)?\s+ismi|oluvchi(?:ning)?\s+ismi)"
    r"\s*[:\-]?[ \t]*([^\n]+)",
    _FLAGS,
)
_CARD_MASK = re.compile(r"\*{4}\d{4}")
_CARD_WORD = re.compile(r"karta|card|карт", _FLAGS)
_NETWORK_WORDS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"humo", _FLAGS), "Humo"),
    (re.compile(r"uzcard", _FLAGS), "Uzcard"),
    (re.compile(r"visa", _FLAGS), "Visa"),
    (re.compile(r"master\s?card", _FLAGS), "Mastercard"),
)
_STRUCTURE_MARKS = ("💳", "📍", "🕓", "➖", "➕")
_HINT_NETWORK = {"cardxabar": "Uzcard", "humo": "Humo"}
_MONTH_WORD = re.compile(
    r"yanvar|fevral|mart|aprel|\bmay\b|iyun|iyul|avgust|sentabr|sentyabr|oktabr|oktyabr|noyabr|dekabr"
    r"|январ|феврал|март|апрел|\bма[йя]\b|июн|июл|август|сентябр|октябр|ноябр|декабр"
    r"|\b(?:jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b",
    _FLAGS,
)
_DATE_DIGITS = re.compile(r"\d{1,2}:\d{2}|\d{1,2}[./-]\d{1,2}")


def _blank(text: str, start: int, end: int) -> str:
    return text[:start] + " " * (end - start) + text[end:]


def mentions_date(text: str) -> bool:
    """Matnda sana, vaqt yoki «kecha»/«bugun» kabi so‘z bormi."""
    return bool(_DATE_DIGITS.search(text) or _MONTH_WORD.search(text) or relative_day_offset(text) is not None)


class RuleBasedParser:
    """LLM’siz, faqat qoidalar asosida ishlaydigan parser."""

    def parse(self, text: str, tz: ZoneInfo, now: datetime, source_hint: str | None = None) -> ParsedTransaction:
        masked, hints = mask_card_numbers(text.strip())
        work = unify_apostrophes(masked)

        date_match = find_datetime(work, tz)
        occurred_at = date_match.value if date_match else None
        if occurred_at is None:
            offset = relative_day_offset(work)
            if offset is not None:
                occurred_at = now.astimezone(tz) - timedelta(days=offset)

        # Sana va karta raqamidagi raqamlar summa deb o‘qilmasligi uchun ularni bo‘shliq bilan almashtiramiz.
        numbers_only = _blank(work, date_match.start, date_match.end) if date_match else work
        for mask in _CARD_MASK.finditer(numbers_only):
            numbers_only = _blank(numbers_only, mask.start(), mask.end())
        amount = self._choose_amount(numbers_only)

        card_line = self._card_line(work)
        source = self._detect_source(work, card_line, hints, amount, source_hint)
        parsed = ParsedTransaction(
            transaction_type=self._detect_type(work, amount),
            amount=amount.amount if amount else None,
            currency=(amount.currency if amount and amount.currency else "UZS"),
            merchant=self._detect_merchant(work),
            card_last4=hints[0].last4 if hints else None,
            card_network=self._detect_network(work, card_line, hints, source_hint),
            occurred_at=occurred_at,
            source=source,
            raw_text=masked,
        )
        parsed.refresh_missing_fields()
        parsed.confidence = self._confidence(parsed)
        parsed.explanation = describe(parsed)
        return parsed

    @staticmethod
    def _choose_amount(text: str) -> AmountMatch | None:
        candidates: list[AmountMatch] = []
        previous_end = 0
        for match in find_amounts(text):
            line_start = text.rfind("\n", 0, match.start) + 1
            context = text[max(previous_end, line_start) : match.start]
            previous_end = match.end
            if _BALANCE.search(context):
                continue
            candidates.append(match)
        if not candidates:
            return None

        for wanted in (lambda m: m.sign is not None, lambda m: m.currency is not None, lambda m: m.has_multiplier):
            chosen = next((m for m in candidates if wanted(m)), None)
            if chosen:
                return chosen
        plain = [m for m in candidates if not _COUNT_WORD.match(text, m.end)] or candidates
        return max(plain, key=lambda m: m.amount)

    @staticmethod
    def _detect_type(text: str, amount: AmountMatch | None) -> str | None:
        if amount and amount.sign:
            return "income" if amount.sign == "+" else "expense"
        expense, income = _EXPENSE.search(text), _INCOME.search(text)
        if expense and income:
            return "expense" if expense.start() < income.start() else "income"
        if expense:
            return "expense"
        if income:
            return "income"
        return None

    @staticmethod
    def _detect_merchant(text: str) -> str | None:
        raw: str | None = None
        for line in text.splitlines():
            if "📍" in line:
                raw = line.split("📍", 1)[1]
                break
        if raw is None:
            label = _MERCHANT_LABEL.search(text)
            if label:
                raw = re.split(r"\.\s|\.$|;", label.group(1), maxsplit=1)[0]
        if raw is None:
            receiver = _RECEIVER_LABEL.search(text)
            if receiver:
                raw = receiver.group(1)
        if raw is None:
            return None
        cleaned = re.sub(r"\s+", " ", raw).strip(" .,;:->")
        return cleaned[:64] or None

    @staticmethod
    def _card_line(text: str) -> str:
        for line in text.splitlines():
            if "💳" in line or _CARD_MASK.search(line):
                return line
        return ""

    @staticmethod
    def _detect_network(text: str, card_line: str, hints: list[CardHint], source_hint: str | None) -> str:
        # Bir qatorli SMS’da karta qatori butun matn bo‘ladi, shuning uchun faqat ko‘p qatorli xabarda ishonamiz.
        if card_line and "\n" in text:
            for pattern, network in _NETWORK_WORDS:
                if pattern.search(card_line):
                    return network
        if hints and hints[0].network != "Unknown":
            return hints[0].network
        if source_hint in _HINT_NETWORK:
            return _HINT_NETWORK[source_hint]
        mentioned = {network for pattern, network in _NETWORK_WORDS if pattern.search(text)}
        return mentioned.pop() if len(mentioned) == 1 else "Unknown"

    @staticmethod
    def _detect_source(
        text: str, card_line: str, hints: list[CardHint], amount: AmountMatch | None, source_hint: str | None
    ) -> str:
        if source_hint in ("cardxabar", "humo", "bank_sms", "screenshot", "pdf"):
            return source_hint
        if sum(mark in text for mark in _STRUCTURE_MARKS) >= 2:
            return "humo" if re.search("humo", card_line, _FLAGS) else "cardxabar"
        if amount and (hints or _BALANCE.search(text) or _CARD_WORD.search(text)):
            return "bank_sms"
        return "manual"

    @staticmethod
    def _confidence(parsed: ParsedTransaction) -> float:
        score = 0.0
        score += 0.40 if parsed.amount is not None else 0.0
        score += 0.20 if parsed.transaction_type else 0.0
        score += 0.15 if parsed.occurred_at else 0.0
        score += 0.10 if parsed.card_last4 else 0.0
        score += 0.10 if parsed.merchant else 0.0
        score += 0.05 if parsed.source in ("cardxabar", "humo") else 0.0
        return round(min(score, 0.95), 2)


def describe(parsed: ParsedTransaction) -> str:
    """Nima aniqlanganini bir gap bilan o‘zbekcha tushuntiradi."""
    if parsed.amount is None:
        return "Xabardan summa aniqlanmadi."
    kind = {"expense": "chiqim", "income": "kirim"}.get(parsed.transaction_type or "", "tranzaksiya")
    parts = [f"{format_amount(parsed.amount, parsed.currency)} {kind}"]
    if parsed.merchant:
        parts.append(parsed.merchant)
    if parsed.card_last4:
        parts.append(f"karta ****{parsed.card_last4}")
    return "Xabardan " + ", ".join(parts) + " aniqlandi."


class TransactionLLM(Protocol):
    async def parse_transaction(
        self, text: str, tz_name: str, now: datetime, categories: list[str]
    ) -> LLMTransaction: ...


class TransactionParser:
    """Qoidalar + (kerak bo‘lsa) LLM. Bot shu sinfdan foydalanadi."""

    def __init__(self, llm: TransactionLLM | None) -> None:
        self._rules = RuleBasedParser()
        self._llm = llm

    async def parse(
        self,
        text: str,
        tz: ZoneInfo,
        now: datetime,
        source_hint: str | None = None,
        categories: list[str] | None = None,
    ) -> ParsedTransaction:
        rule = self._rules.parse(text, tz, now, source_hint=source_hint)
        if self._llm is None or self._is_sufficient(rule):
            return rule
        try:
            # LLM’ga faqat karta raqami yashirilgan matn yuboriladi.
            answer = await self._llm.parse_transaction(rule.raw_text, str(tz), now.astimezone(tz), categories or [])
        except LLMError as error:
            logger.warning("LLM parse failed, using rule-based result: %s", error)
            return rule
        return self._merge(rule, answer, tz)

    @property
    def supports_screenshots(self) -> bool:
        """Rasmni o‘qish uchun LLM sozlangan bo‘lishi kerak."""
        return self._llm is not None and hasattr(self._llm, "parse_screenshot")

    async def parse_screenshot(
        self, image: ImageInput, tz: ZoneInfo, now: datetime, categories: list[str] | None = None
    ) -> ParsedTransaction:
        """Screenshot’ni LLM o‘qiydi; natija matnli xabar bilan bir xil tekshiruvlardan o‘tadi."""
        if not self.supports_screenshots:
            raise LLMError("no LLM configured for screenshots")
        answer = await self._llm.parse_screenshot(image, str(tz), now.astimezone(tz), categories or [])
        # LLM ko‘chirib bergan matn ham qoidalardan o‘tadi: karta raqami yashiriladi, karta va sana
        # faqat shu matnda ko‘rinsa qabul qilinadi.
        rule = self._rules.parse(answer.visible_text or "", tz, now, source_hint="screenshot")
        return self._merge(rule, answer, tz)

    @staticmethod
    def _is_sufficient(parsed: ParsedTransaction) -> bool:
        core = parsed.transaction_type and parsed.amount is not None and parsed.occurred_at
        return bool(core and (parsed.merchant or parsed.source in ("cardxabar", "humo")))

    @staticmethod
    def _merge(rule: ParsedTransaction, answer: LLMTransaction, tz: ZoneInfo) -> ParsedTransaction:
        structured = rule.source in ("cardxabar", "humo")
        merged = rule.model_copy()

        if not (structured and rule.transaction_type):
            merged.transaction_type = answer.transaction_type or rule.transaction_type
        if answer.amount is not None:
            merged.amount = answer.amount
            merged.currency = answer.currency
        merged.merchant = answer.merchant or rule.merchant

        # LLM o‘ylab topgan karta raqami yoki sana qabul qilinmaydi: ular matnda bo‘lishi shart.
        if rule.card_last4 is None and answer.card_last4 and answer.card_last4 in rule.raw_text:
            merged.card_last4 = answer.card_last4
        if rule.card_network == "Unknown" and merged.card_last4:
            merged.card_network = answer.card_network
        if rule.occurred_at is None and answer.occurred_at and mentions_date(rule.raw_text):
            value = answer.occurred_at
            merged.occurred_at = value if value.tzinfo else value.replace(tzinfo=tz)

        merged.category_guess = answer.category_guess
        merged.confidence = answer.confidence
        merged.refresh_missing_fields()
        merged.explanation = answer.explanation or describe(merged)
        return merged
