"""Foydalanuvchi, karta, kategoriya va tranzaksiyalar bilan ishlash.

Har bir so‘rov ``user_id`` bo‘yicha filtrlanadi: foydalanuvchi faqat o‘z
ma’lumotlarini ko‘radi va o‘zgartiradi.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card, Category, MerchantRule, Transaction, User
from app.schemas import CARD_NETWORKS, NoteAnalysis, ParsedTransaction
from app.utils.validators import is_valid_last4, normalize_merchant, normalize_text

DEFAULT_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("P2P", "🔁"),
    ("Ovqatlanish", "🍽"),
    ("Narsa sotib olish", "🛍"),
    ("Qarz berish", "📤"),
    ("Qarz olish", "📥"),
    ("Investitsiya", "📈"),
    ("Uyga to‘lov", "🏠"),
    ("Maosh", "💼"),
    ("Boshqa", "📦"),
)

MAX_CATEGORIES = 40
MAX_CARDS = 20


class ServiceError(Exception):
    """Foydalanuvchiga tushuntirib beriladigan xato."""


class InvalidInputError(ServiceError):
    pass


class DuplicateError(ServiceError):
    pass


# --------------------------------------------------------------------------- #
# Foydalanuvchi
# --------------------------------------------------------------------------- #


async def get_or_create_user(
    session: AsyncSession,
    telegram_user_id: int,
    username: str | None = None,
    first_name: str | None = None,
    timezone: str = "Asia/Tashkent",
    currency: str = "UZS",
) -> User:
    user = await session.scalar(select(User).where(User.telegram_user_id == telegram_user_id))
    if user is not None:
        return user

    user = User(
        telegram_user_id=telegram_user_id,
        username=username,
        first_name=first_name,
        timezone=timezone,
        preferred_currency=currency,
    )
    session.add(user)
    await session.flush()
    session.add_all(
        Category(user_id=user.id, name=name, emoji=emoji, is_default=True) for name, emoji in DEFAULT_CATEGORIES
    )
    await session.commit()
    return user


async def update_user(
    session: AsyncSession,
    user: User,
    *,
    timezone: str | None = None,
    preferred_currency: str | None = None,
    notifications_enabled: bool | None = None,
    last_report_month: str | None = None,
    weekly_report_enabled: bool | None = None,
    last_weekly_report: str | None = None,
    daily_report_enabled: bool | None = None,
    last_daily_report: str | None = None,
) -> User:
    if timezone is not None:
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise InvalidInputError("Bunday vaqt zonasi topilmadi") from error
        user.timezone = timezone
    if preferred_currency is not None:
        code = preferred_currency.strip().upper()
        if len(code) != 3 or not code.isalpha():
            raise InvalidInputError("Valyuta kodi 3 ta harfdan iborat bo‘lishi kerak")
        user.preferred_currency = code
    if notifications_enabled is not None:
        user.notifications_enabled = notifications_enabled
    if last_report_month is not None:
        user.last_report_month = last_report_month
    if weekly_report_enabled is not None:
        user.weekly_report_enabled = weekly_report_enabled
    if last_weekly_report is not None:
        user.last_weekly_report = last_weekly_report
    if daily_report_enabled is not None:
        user.daily_report_enabled = daily_report_enabled
    if last_daily_report is not None:
        user.last_daily_report = last_daily_report
    await session.commit()
    return user


async def delete_user_data(session: AsyncSession, user_id: int) -> None:
    """Foydalanuvchining barcha ma’lumotlarini butunlay o‘chiradi."""
    await session.execute(delete(Transaction).where(Transaction.user_id == user_id))
    await session.execute(delete(MerchantRule).where(MerchantRule.user_id == user_id))
    await session.execute(delete(Card).where(Card.user_id == user_id))
    await session.execute(delete(Category).where(Category.user_id == user_id))
    await session.execute(delete(User).where(User.id == user_id))
    await session.commit()
    session.expunge_all()


# --------------------------------------------------------------------------- #
# Kategoriyalar (turlar)
# --------------------------------------------------------------------------- #


async def list_categories(session: AsyncSession, user_id: int) -> list[Category]:
    result = await session.scalars(select(Category).where(Category.user_id == user_id).order_by(Category.id))
    return list(result)


async def get_category(session: AsyncSession, user_id: int, category_id: int) -> Category | None:
    return await session.scalar(select(Category).where(Category.id == category_id, Category.user_id == user_id))


async def add_category(session: AsyncSession, user_id: int, name: str, emoji: str = "🏷") -> Category:
    name = " ".join(name.split())
    if not 1 <= len(name) <= 32:
        raise InvalidInputError("Tur nomi 1 dan 32 belgigacha bo‘lishi kerak")
    existing = await list_categories(session, user_id)
    if len(existing) >= MAX_CATEGORIES:
        raise InvalidInputError(f"Turlar soni {MAX_CATEGORIES} tadan oshmasligi kerak")
    if any(normalize_text(category.name) == normalize_text(name) for category in existing):
        raise DuplicateError("Bunday tur allaqachon bor")
    category = Category(user_id=user_id, name=name, emoji=emoji[:8] or "🏷", is_default=False)
    session.add(category)
    await session.commit()
    return category


async def delete_category(session: AsyncSession, user_id: int, category_id: int) -> bool:
    category = await get_category(session, user_id, category_id)
    if category is None:
        return False
    await session.execute(delete(MerchantRule).where(MerchantRule.category_id == category_id))
    await session.delete(category)
    await session.commit()
    return True


async def suggest_category(
    session: AsyncSession, user_id: int, merchant: str | None, guess_name: str | None
) -> Category | None:
    """Avval foydalanuvchining shu merchant uchun oldingi tanlovi, keyin taxmin qilingan nom."""
    if merchant:
        normalized = normalize_merchant(merchant)
        if normalized:
            category = await session.scalar(
                select(Category)
                .join(MerchantRule, MerchantRule.category_id == Category.id)
                .where(
                    MerchantRule.user_id == user_id,
                    MerchantRule.merchant_normalized == normalized,
                    Category.user_id == user_id,
                )
            )
            if category is not None:
                return category
    if guess_name:
        wanted = normalize_text(guess_name.strip())
        for category in await list_categories(session, user_id):
            if normalize_text(category.name) == wanted:
                return category
    return None


async def _remember_merchant(session: AsyncSession, user_id: int, merchant: str, category_id: int) -> None:
    normalized = normalize_merchant(merchant)[:128]
    if not normalized:
        return
    rule = await session.scalar(
        select(MerchantRule).where(MerchantRule.user_id == user_id, MerchantRule.merchant_normalized == normalized)
    )
    if rule is None:
        session.add(MerchantRule(user_id=user_id, merchant_normalized=normalized, category_id=category_id))
    else:
        rule.category_id = category_id


# --------------------------------------------------------------------------- #
# Kartalar
# --------------------------------------------------------------------------- #


async def list_cards(session: AsyncSession, user_id: int, only_active: bool = False) -> list[Card]:
    query = select(Card).where(Card.user_id == user_id).order_by(Card.id)
    if only_active:
        query = query.where(Card.is_active.is_(True))
    return list(await session.scalars(query))


async def get_card(session: AsyncSession, user_id: int, card_id: int) -> Card | None:
    return await session.scalar(select(Card).where(Card.id == card_id, Card.user_id == user_id))


async def find_card_by_last4(session: AsyncSession, user_id: int, last4: str) -> Card | None:
    return await session.scalar(
        select(Card)
        .where(Card.user_id == user_id, Card.card_last4 == last4)
        .order_by(Card.is_active.desc(), Card.id)
        .limit(1)
    )


async def add_card(
    session: AsyncSession,
    user_id: int,
    name: str,
    last4: str,
    network: str = "Unknown",
    bank_name: str | None = None,
    currency: str = "UZS",
) -> Card:
    name = " ".join(name.split())
    if not 1 <= len(name) <= 64:
        raise InvalidInputError("Karta nomi 1 dan 64 belgigacha bo‘lishi kerak")
    if not is_valid_last4(last4):
        raise InvalidInputError("Kartaning faqat oxirgi 4 ta raqamini yozing")
    if network not in CARD_NETWORKS:
        network = "Unknown"
    cards = await list_cards(session, user_id)
    if len(cards) >= MAX_CARDS:
        raise InvalidInputError(f"Kartalar soni {MAX_CARDS} tadan oshmasligi kerak")
    if any(card.card_last4 == last4 and card.card_network == network for card in cards):
        raise DuplicateError("Bu karta allaqachon qo‘shilgan")
    card = Card(
        user_id=user_id,
        name=name,
        card_last4=last4,
        card_network=network,
        bank_name=(" ".join(bank_name.split())[:64] or None) if bank_name else None,
        currency=currency.upper()[:3] or "UZS",
    )
    session.add(card)
    await session.commit()
    return card


async def toggle_card_active(session: AsyncSession, user_id: int, card_id: int) -> bool | None:
    """Kartani faol/nofaol qiladi. Yangi holatni qaytaradi; karta topilmasa ``None``."""
    card = await get_card(session, user_id, card_id)
    if card is None:
        return None
    card.is_active = not card.is_active
    await session.commit()
    return card.is_active


async def delete_card(session: AsyncSession, user_id: int, card_id: int) -> bool:
    """Kartani o‘chiradi. Uning tranzaksiyalari saqlanib qoladi (kartasiz bo‘lib)."""
    card = await get_card(session, user_id, card_id)
    if card is None:
        return False
    await session.delete(card)
    await session.commit()
    return True


# --------------------------------------------------------------------------- #
# Tranzaksiyalar
# --------------------------------------------------------------------------- #


async def find_duplicate(session: AsyncSession, user_id: int, parsed: ParsedTransaction) -> Transaction | None:
    """Xuddi shu summa, tur va vaqtdagi tranzaksiya avval saqlanganmi."""
    if parsed.amount is None or parsed.occurred_at is None or parsed.transaction_type is None:
        return None
    return await session.scalar(
        select(Transaction)
        .where(
            Transaction.user_id == user_id,
            Transaction.transaction_type == parsed.transaction_type,
            Transaction.amount == parsed.amount,
            Transaction.currency == parsed.currency,
            Transaction.occurred_at == parsed.occurred_at,
        )
        .limit(1)
    )


async def create_transaction(
    session: AsyncSession,
    user: User,
    parsed: ParsedTransaction,
    note: str | None,
    category_id: int | None,
    card_id: int | None,
    analysis: NoteAnalysis,
) -> Transaction:
    if parsed.amount is None or parsed.amount <= 0:
        raise InvalidInputError("Summa aniqlanmagan")
    if parsed.transaction_type is None:
        raise InvalidInputError("Kirim yoki chiqim ekani aniqlanmagan")
    if parsed.occurred_at is None:
        raise InvalidInputError("Sana aniqlanmagan")

    category = None
    if category_id is not None:
        category = await get_category(session, user.id, category_id)
        if category is None:
            raise InvalidInputError("Tur topilmadi")
    card = None
    if card_id is not None:
        card = await get_card(session, user.id, card_id)
        if card is None:
            raise InvalidInputError("Karta topilmadi")

    transaction = Transaction(
        user_id=user.id,
        transaction_type=parsed.transaction_type,
        amount=parsed.amount,
        currency=parsed.currency,
        merchant=parsed.merchant[:128] if parsed.merchant else None,
        user_note=note,
        ai_summary=analysis.summary or parsed.explanation,
        tags=list(analysis.tags),
        people_count=analysis.people_count,
        is_shared_expense=analysis.is_shared_expense,
        is_recurring=analysis.is_recurring,
        recurring_period=analysis.recurring_period,
        occurred_at=parsed.occurred_at,
        raw_text=parsed.raw_text or None,
        source=parsed.source,
        confidence=parsed.confidence,
    )
    transaction.card = card
    transaction.category = category
    session.add(transaction)
    if category is not None and parsed.merchant:
        await _remember_merchant(session, user.id, parsed.merchant, category.id)
    await session.commit()
    return transaction


async def get_last_transaction(session: AsyncSession, user_id: int) -> Transaction | None:
    return await session.scalar(
        select(Transaction).where(Transaction.user_id == user_id).order_by(Transaction.id.desc()).limit(1)
    )


async def delete_transaction(session: AsyncSession, user_id: int, transaction_id: int) -> bool:
    result = await session.execute(
        delete(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user_id)
    )
    await session.commit()
    return result.rowcount > 0

