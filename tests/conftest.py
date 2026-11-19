import os
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from cryptography.fernet import Fernet

# Sozlamalar import paytida o'qilishi mumkin, shuning uchun eng boshida o'rnatiladi.
os.environ["BOT_TOKEN"] = "123456789:TEST-TOKEN-NOT-REAL-000000000000000000"
os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["LLM_PROVIDER"] = "none"

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy.pool import NullPool, StaticPool  # noqa: E402

from app.database import Base, create_engine, create_session_factory  # noqa: E402
from app.schemas import ParsedTransaction  # noqa: E402
from app.services import transaction_service as ts  # noqa: E402

TZ = ZoneInfo("Asia/Tashkent")


# Standart holatda testlar xotiradagi SQLite'da ishlaydi. PostgreSQL'da tekshirish uchun:
#   TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/moneytrack_test pytest
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest_asyncio.fixture
async def engine():
    if TEST_DATABASE_URL:
        engine = create_engine(TEST_DATABASE_URL, poolclass=NullPool)
    else:
        engine = create_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def session_factory(engine):
    return create_session_factory(engine)


@pytest_asyncio.fixture
async def session(session_factory):
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def user(session):
    return await ts.get_or_create_user(session, telegram_user_id=1001, username="ali", first_name="Ali")


@pytest_asyncio.fixture
async def other_user(session):
    return await ts.get_or_create_user(session, telegram_user_id=2002, username="vali", first_name="Vali")


def make_parsed(**overrides) -> ParsedTransaction:
    base = {
        "transaction_type": "expense",
        "amount": Decimal("250000"),
        "currency": "UZS",
        "merchant": "KAMOLON",
        "card_last4": "1234",
        "card_network": "Uzcard",
        "occurred_at": datetime(2026, 11, 19, 10, 15, tzinfo=TZ),
        "source": "cardxabar",
        "raw_text": "🔴 Pokupka ➖ 250 000.00 UZS 💳 ****1234",
        "confidence": 0.95,
    }
    return ParsedTransaction(**(base | overrides))


async def category_named(session, user_id: int, name: str):
    return next(c for c in await ts.list_categories(session, user_id) if c.name == name)
