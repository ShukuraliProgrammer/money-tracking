"""Ma’lumotlar bazasi jadvallari."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.database import Base
from app.utils.crypto import get_cipher


class UTCDateTime(TypeDecorator[datetime]):
    """Vaqtni bazada UTC’da saqlaydi va har doim vaqt zonali qiymat qaytaradi.

    SQLite vaqt zonasini saqlamaydi, shuning uchun solishtirishlar to‘g‘ri
    ishlashi uchun hamma qiymat UTC’ga keltiriladi.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Vaqt zonasiz datetime saqlab bo‘lmaydi")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        return value.replace(tzinfo=UTC) if value is not None else None


class EncryptedText(TypeDecorator[str]):
    """Matnni bazaga shifrlangan (Fernet) holda yozadi."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Any) -> str | None:
        return get_cipher().encrypt(value) if value is not None else None

    def process_result_value(self, value: str | None, dialect: Any) -> str | None:
        return get_cipher().decrypt(value) if value is not None else None


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    language: Mapped[str] = mapped_column(String(8), default="uz")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Tashkent")
    preferred_currency: Mapped[str] = mapped_column(String(3), default="UZS")
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Oylik hisobot oxirgi marta qaysi oy uchun yuborilgani ("2026-10").
    last_report_month: Mapped[str | None] = mapped_column(String(7))
    weekly_report_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    # Haftalik hisobot oxirgi marta qaysi hafta uchun yuborilgani (o‘sha haftaning dushanbasi, "2026-11-09").
    last_weekly_report: Mapped[str | None] = mapped_column(String(10))
    daily_report_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    # Kunlik hisobot oxirgi marta qaysi kun uchun yuborilgani ("2026-11-19").
    last_daily_report: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    @property
    def tz(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            return ZoneInfo("Asia/Tashkent")


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    bank_name: Mapped[str | None] = mapped_column(String(64))
    # Faqat oxirgi 4 raqam. To‘liq karta raqami hech qachon saqlanmaydi.
    card_last4: Mapped[str] = mapped_column(String(4))
    card_network: Mapped[str] = mapped_column(String(16), default="Unknown")
    currency: Mapped[str] = mapped_column(String(3), default="UZS")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_categories_user_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(32))
    emoji: Mapped[str] = mapped_column(String(8), default="🏷")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (Index("ix_transactions_user_occurred", "user_id", "occurred_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    card_id: Mapped[int | None] = mapped_column(ForeignKey("cards.id", ondelete="SET NULL"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    transaction_type: Mapped[str] = mapped_column(String(8))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="UZS")
    merchant: Mapped[str | None] = mapped_column(String(128))
    user_note: Mapped[str | None] = mapped_column(EncryptedText)
    ai_summary: Mapped[str | None] = mapped_column(EncryptedText)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    people_count: Mapped[int | None] = mapped_column(Integer)
    is_shared_expense: Mapped[bool] = mapped_column(Boolean, default=False)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurring_period: Mapped[str] = mapped_column(String(8), default="none")
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    raw_text: Mapped[str | None] = mapped_column(EncryptedText)
    source: Mapped[str] = mapped_column(String(16), default="manual")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    card: Mapped[Card | None] = relationship(lazy="joined")
    category: Mapped[Category | None] = relationship(lazy="joined")


class MerchantRule(Base):
    """Foydalanuvchi merchant uchun oxirgi tanlagan kategoriya (keyingi safar taklif qilinadi)."""

    __tablename__ = "merchant_rules"
    __table_args__ = (UniqueConstraint("user_id", "merchant_normalized", name="uq_merchant_rules_user_merchant"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    merchant_normalized: Mapped[str] = mapped_column(String(128))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
