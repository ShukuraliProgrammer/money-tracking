from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.schemas import NoteAnalysis
from app.services import transaction_service as ts
from tests.conftest import TZ, category_named, make_parsed


async def test_new_user_gets_defaults(user):
    assert user.timezone == "Asia/Tashkent"
    assert user.preferred_currency == "UZS"
    assert user.language == "uz"
    assert user.notifications_enabled is True


async def test_get_or_create_user_is_idempotent(session, user):
    again = await ts.get_or_create_user(session, telegram_user_id=1001, username="ali", first_name="Ali")
    assert again.id == user.id


async def test_new_user_gets_default_categories(session, user):
    names = [c.name for c in await ts.list_categories(session, user.id)]
    assert names == [
        "P2P", "Ovqatlanish", "Narsa sotib olish", "Qarz berish", "Qarz olish",
        "Investitsiya", "Uyga to‘lov", "Maosh", "Boshqa",
    ]  # fmt: skip


async def test_add_category(session, user):
    category = await ts.add_category(session, user.id, "Transport", "🚕")
    assert category.is_default is False
    assert "Transport" in [c.name for c in await ts.list_categories(session, user.id)]


async def test_add_category_rejects_duplicate_name_ignoring_case(session, user):
    with pytest.raises(ts.DuplicateError):
        await ts.add_category(session, user.id, "ovqatlanish")


@pytest.mark.parametrize("name", ["", "   ", "x" * 33])
async def test_add_category_rejects_bad_names(session, user, name):
    with pytest.raises(ts.InvalidInputError):
        await ts.add_category(session, user.id, name)


async def test_delete_category_only_for_owner(session, user, other_user):
    category = await ts.add_category(session, user.id, "Transport")
    assert await ts.delete_category(session, other_user.id, category.id) is False
    assert await ts.delete_category(session, user.id, category.id) is True


async def test_add_card_stores_only_last4(session, user):
    card = await ts.add_card(session, user.id, name="Asosiy Uzcard", last4="1234", network="Uzcard")
    assert card.card_last4 == "1234"
    assert card.currency == "UZS"
    assert card.is_active is True


@pytest.mark.parametrize("last4", ["123", "12345", "abcd", "8600123456789012"])
async def test_add_card_rejects_anything_but_four_digits(session, user, last4):
    with pytest.raises(ts.InvalidInputError):
        await ts.add_card(session, user.id, name="Karta", last4=last4, network="Uzcard")


async def test_add_card_rejects_duplicate(session, user):
    await ts.add_card(session, user.id, name="Asosiy", last4="1234", network="Uzcard")
    with pytest.raises(ts.DuplicateError):
        await ts.add_card(session, user.id, name="Boshqa nom", last4="1234", network="Uzcard")


async def test_find_card_by_last4_is_per_user(session, user, other_user):
    await ts.add_card(session, user.id, name="Asosiy", last4="1234", network="Uzcard")
    assert (await ts.find_card_by_last4(session, user.id, "1234")).name == "Asosiy"
    assert await ts.find_card_by_last4(session, other_user.id, "1234") is None


async def test_toggle_card_active(session, user):
    card = await ts.add_card(session, user.id, name="Asosiy", last4="1234", network="Uzcard")
    assert await ts.toggle_card_active(session, user.id, card.id) is False
    assert await ts.list_cards(session, user.id, only_active=True) == []
    assert await ts.toggle_card_active(session, user.id, card.id) is True


async def test_create_transaction_saves_all_fields(session, user):
    card = await ts.add_card(session, user.id, name="Asosiy", last4="1234", network="Uzcard")
    food = await category_named(session, user.id, "Ovqatlanish")
    analysis = NoteAnalysis(tags=["tushlik"], people_count=3, is_shared_expense=True, summary="3 kishi ovqatlandi")

    tx = await ts.create_transaction(
        session, user, make_parsed(), note="Kamolonda ovqatlandik 3 kishi",
        category_id=food.id, card_id=card.id, analysis=analysis,
    )  # fmt: skip

    assert tx.id is not None
    assert tx.amount == Decimal("250000")
    assert tx.transaction_type == "expense"
    assert tx.user_note == "Kamolonda ovqatlandik 3 kishi"
    assert tx.category.name == "Ovqatlanish"
    assert tx.card.card_last4 == "1234"
    assert tx.tags == ["tushlik"]
    assert tx.people_count == 3
    assert tx.is_shared_expense is True
    assert tx.recurring_period == "none"
    assert tx.ai_summary == "3 kishi ovqatlandi"
    assert tx.occurred_at == datetime(2026, 11, 19, 10, 15, tzinfo=TZ)
    assert tx.source == "cardxabar"


async def test_sensitive_text_is_encrypted_at_rest(session, user):
    await ts.create_transaction(
        session, user, make_parsed(raw_text="MAXFIY-ASL-XABAR"), note="MAXFIY-IZOH",
        category_id=None, card_id=None, analysis=NoteAnalysis(summary="MAXFIY-XULOSA"),
    )  # fmt: skip
    row = (await session.execute(text("SELECT raw_text, user_note, ai_summary FROM transactions"))).one()
    assert "MAXFIY" not in "".join(row)
    assert all(value.startswith("gAAAA") for value in row)


async def test_create_transaction_rejects_foreign_card_and_category(session, user, other_user):
    foreign_card = await ts.add_card(session, other_user.id, name="Begona", last4="9999", network="Humo")
    foreign_category = await category_named(session, other_user.id, "Ovqatlanish")
    with pytest.raises(ts.InvalidInputError):
        await ts.create_transaction(session, user, make_parsed(), "izoh", None, foreign_card.id, NoteAnalysis())
    with pytest.raises(ts.InvalidInputError):
        await ts.create_transaction(session, user, make_parsed(), "izoh", foreign_category.id, None, NoteAnalysis())


async def test_create_transaction_requires_amount_type_and_date(session, user):
    with pytest.raises(ts.InvalidInputError):
        await ts.create_transaction(session, user, make_parsed(amount=None), "izoh", None, None, NoteAnalysis())
    with pytest.raises(ts.InvalidInputError):
        await ts.create_transaction(session, user, make_parsed(occurred_at=None), "izoh", None, None, NoteAnalysis())
    with pytest.raises(ts.InvalidInputError):
        await ts.create_transaction(session, user, make_parsed(transaction_type=None), "izoh", None, None, NoteAnalysis())


async def test_duplicate_is_detected_for_same_user_only(session, user, other_user):
    await ts.create_transaction(session, user, make_parsed(), "izoh", None, None, NoteAnalysis())
    assert await ts.find_duplicate(session, user.id, make_parsed()) is not None
    assert await ts.find_duplicate(session, other_user.id, make_parsed()) is None
    assert await ts.find_duplicate(session, user.id, make_parsed(amount=Decimal("1"))) is None


async def test_merchant_rule_is_learned_and_suggested(session, user):
    food = await category_named(session, user.id, "Ovqatlanish")
    await ts.create_transaction(session, user, make_parsed(merchant="KAMOLON"), "tushlik", food.id, None, NoteAnalysis())
    suggestion = await ts.suggest_category(session, user.id, merchant="Kamolon 24, UZ", guess_name=None)
    assert suggestion.id == food.id


async def test_merchant_rule_follows_latest_choice(session, user):
    food = await category_named(session, user.id, "Ovqatlanish")
    other = await category_named(session, user.id, "Boshqa")
    await ts.create_transaction(session, user, make_parsed(), "a", food.id, None, NoteAnalysis())
    later = make_parsed(occurred_at=datetime(2026, 11, 20, 10, 15, tzinfo=TZ))
    await ts.create_transaction(session, user, later, "b", other.id, None, NoteAnalysis())
    assert (await ts.suggest_category(session, user.id, "KAMOLON", None)).id == other.id


async def test_suggest_category_falls_back_to_guess_name(session, user):
    suggestion = await ts.suggest_category(session, user.id, merchant="YANGI JOY", guess_name="ovqatlanish")
    assert suggestion.name == "Ovqatlanish"


async def test_suggest_category_returns_none_when_nothing_known(session, user):
    assert await ts.suggest_category(session, user.id, merchant=None, guess_name="Mavjud emas") is None


async def test_merchant_rules_are_not_shared_between_users(session, user, other_user):
    food = await category_named(session, user.id, "Ovqatlanish")
    await ts.create_transaction(session, user, make_parsed(), "a", food.id, None, NoteAnalysis())
    assert await ts.suggest_category(session, other_user.id, "KAMOLON", None) is None


async def test_delete_last_transaction_only_touches_own_data(session, user, other_user):
    tx = await ts.create_transaction(session, user, make_parsed(), "izoh", None, None, NoteAnalysis())
    assert await ts.get_last_transaction(session, other_user.id) is None
    assert await ts.delete_transaction(session, other_user.id, tx.id) is False
    assert (await ts.get_last_transaction(session, user.id)).id == tx.id
    assert await ts.delete_transaction(session, user.id, tx.id) is True
    assert await ts.get_last_transaction(session, user.id) is None


async def test_deleting_card_keeps_transactions(session, user):
    card = await ts.add_card(session, user.id, name="Asosiy", last4="1234", network="Uzcard")
    tx = await ts.create_transaction(session, user, make_parsed(), "izoh", None, card.id, NoteAnalysis())
    user_id = user.id
    assert await ts.delete_card(session, user_id, card.id) is True
    session.expire_all()  # bazadagi haqiqiy holatni qayta o'qish uchun
    kept = await ts.get_last_transaction(session, user_id)
    assert kept.id == tx.id
    assert kept.card is None


async def test_delete_user_data_removes_everything_for_that_user_only(session, user, other_user):
    card = await ts.add_card(session, user.id, name="Asosiy", last4="1234", network="Uzcard")
    food = await category_named(session, user.id, "Ovqatlanish")
    await ts.create_transaction(session, user, make_parsed(), "izoh", food.id, card.id, NoteAnalysis())
    await ts.create_transaction(session, other_user, make_parsed(), "izoh", None, None, NoteAnalysis())

    await ts.delete_user_data(session, user.id)

    for table in ("transactions", "cards", "categories", "merchant_rules"):
        count = (await session.execute(text(f"SELECT COUNT(*) FROM {table} WHERE user_id = :u"), {"u": user.id})).scalar()
        assert count == 0, table
    assert (await session.execute(text("SELECT COUNT(*) FROM users WHERE id = :u"), {"u": user.id})).scalar() == 0
    assert await ts.get_last_transaction(session, other_user.id) is not None


async def test_update_user_settings(session, user):
    await ts.update_user(session, user, timezone="Asia/Samarkand", preferred_currency="USD", notifications_enabled=False)
    assert user.timezone == "Asia/Samarkand"
    assert user.preferred_currency == "USD"
    assert user.notifications_enabled is False


async def test_update_user_rejects_unknown_timezone(session, user):
    with pytest.raises(ts.InvalidInputError):
        await ts.update_user(session, user, timezone="Mars/Olympus")
