"""Pydantic sxemalari: parser natijasi va LLM javoblari."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.utils.money import normalize_currency
from app.utils.validators import is_valid_last4

TransactionType = Literal["income", "expense"]
CardNetwork = Literal["Uzcard", "Humo", "Visa", "Mastercard", "Unknown"]
Source = Literal["cardxabar", "humo", "bank_sms", "manual", "screenshot"]
RecurringPeriod = Literal["none", "daily", "weekly", "monthly", "yearly"]

CARD_NETWORKS: tuple[str, ...] = ("Uzcard", "Humo", "Visa", "Mastercard", "Unknown")
RECURRING_PERIODS: tuple[str, ...] = ("none", "daily", "weekly", "monthly", "yearly")
REQUIRED_FIELDS: tuple[str, ...] = ("amount", "transaction_type", "occurred_at", "merchant", "card_last4")


class ParsedTransaction(BaseModel):
    """Xabardan ajratib olingan tranzaksiya qoralamasi (hali bazaga yozilmagan)."""

    transaction_type: TransactionType | None = None
    amount: Decimal | None = None
    currency: str = "UZS"
    merchant: str | None = None
    card_last4: str | None = None
    card_network: CardNetwork = "Unknown"
    occurred_at: datetime | None = None
    category_guess: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    missing_fields: list[str] = Field(default_factory=list)
    explanation: str | None = None
    source: Source = "manual"
    raw_text: str = ""

    def refresh_missing_fields(self) -> None:
        self.missing_fields = [name for name in REQUIRED_FIELDS if getattr(self, name) is None]


def _clean_currency(value: Any) -> str:
    if isinstance(value, str):
        known = normalize_currency(value)
        if known:
            return known
        if len(value.strip()) == 3 and value.strip().isalpha():
            return value.strip().upper()
    return "UZS"


class LLMTransaction(BaseModel):
    """LLM qaytargan JSON. Yaroqsiz qiymatlar xato bermasdan ``None``ga aylantiriladi."""

    transaction_type: TransactionType | None = None
    amount: Decimal | None = None
    currency: str = "UZS"
    merchant: str | None = None
    card_last4: str | None = None
    card_network: CardNetwork = "Unknown"
    occurred_at: datetime | None = None
    category_guess: str | None = None
    confidence: float = 0.5
    missing_fields: list[str] = Field(default_factory=list)
    explanation: str | None = None

    @field_validator("amount", mode="before")
    @classmethod
    def _positive_amount(cls, value: Any) -> Decimal | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            amount = Decimal(str(value))
        except InvalidOperation:
            return None
        return amount if amount.is_finite() and amount > 0 else None

    @field_validator("currency", mode="before")
    @classmethod
    def _currency(cls, value: Any) -> str:
        return _clean_currency(value)

    @field_validator("merchant", "category_guess", "explanation", mode="before")
    @classmethod
    def _blank_to_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("card_last4", mode="before")
    @classmethod
    def _last4(cls, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        digits = value.strip().lstrip("*• ")
        return digits if is_valid_last4(digits) else None

    @field_validator("card_network", mode="before")
    @classmethod
    def _network(cls, value: Any) -> str:
        if isinstance(value, str):
            for network in CARD_NETWORKS:
                if network.lower() == value.strip().lower():
                    return network
        return "Unknown"

    @field_validator("occurred_at", mode="before")
    @classmethod
    def _occurred_at(cls, value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.strip())
            except ValueError:
                return None
        return None

    @field_validator("confidence", mode="before")
    @classmethod
    def _confidence(cls, value: Any) -> float:
        try:
            return min(1.0, max(0.0, float(value)))
        except (TypeError, ValueError):
            return 0.5

    @field_validator("missing_fields", mode="before")
    @classmethod
    def _missing(cls, value: Any) -> list[str]:
        return [str(item) for item in value] if isinstance(value, list) else []


class LLMNoteAnalysis(BaseModel):
    """Foydalanuvchi izohi bo‘yicha LLM taklifi."""

    category_guess: str | None = None
    tags: list[str] = Field(default_factory=list)
    people_count: int | None = None
    is_shared_expense: bool = False
    is_recurring: bool = False
    recurring_period: RecurringPeriod = "none"
    summary: str | None = None

    @field_validator("category_guess", "summary", mode="before")
    @classmethod
    def _blank_to_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("tags", mode="before")
    @classmethod
    def _tags(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        cleaned = [str(item).strip().lstrip("#").lower()[:24] for item in value]
        return list(dict.fromkeys(tag for tag in cleaned if tag))[:5]

    @field_validator("people_count", mode="before")
    @classmethod
    def _people(cls, value: Any) -> int | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return int(value) if 1 <= value <= 1000 else None

    @field_validator("recurring_period", mode="before")
    @classmethod
    def _period(cls, value: Any) -> str:
        return value if value in RECURRING_PERIODS else "none"


class NoteAnalysis(BaseModel):
    """Izoh tahlilining yakuniy natijasi (qoidalar + ixtiyoriy LLM)."""

    category_guess: str | None = None
    tags: list[str] = Field(default_factory=list)
    people_count: int | None = None
    is_shared_expense: bool = False
    is_recurring: bool = False
    recurring_period: RecurringPeriod = "none"
    summary: str | None = None
