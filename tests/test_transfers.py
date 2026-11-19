"""O'z kartalar orasidagi o'tkazmaning ikki tomonini tanish."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.schemas import NoteAnalysis
from app.services import transaction_service as ts
from app.services.transfers import Leg, find_transfer_counterpart, is_transfer_pair
from tests.conftest import TZ, make_parsed

AT = datetime(2026, 11, 19, 12, 1, tzinfo=TZ)


def leg(kind="expense", amount="1000000", minutes=0, last4="1234", currency="UZS") -> Leg:
    return Leg(kind, Decimal(amount), currency, AT + timedelta(minutes=minutes), last4)


def test_same_amount_opposite_direction_different_cards_within_minutes_is_a_pair():
    assert is_transfer_pair(leg("expense"), leg("income", minutes=1, last4="5678")) is True


def test_order_of_the_two_sides_does_not_matter():
    assert is_transfer_pair(leg("income", last4="5678"), leg("expense", minutes=2)) is True


def test_small_sender_fee_is_still_a_pair():
    assert is_transfer_pair(leg("expense", amount="1010000"), leg("income", amount="1000000", last4="5678")) is True


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (leg("expense"), leg("expense", last4="5678")),  # ikkalasi ham chiqim
        (leg("expense"), leg("income", last4="1234")),  # bitta karta
        (leg("expense"), leg("income", last4="5678", minutes=11)),  # orasi uzoq
        (leg("expense"), leg("income", last4="5678", minutes=-11)),
        (leg("expense"), leg("income", last4="5678", currency="USD")),  # valyuta boshqa
        (leg("expense", amount="1100000"), leg("income", amount="1000000", last4="5678")),  # farq komissiyadan katta
        (leg("expense", amount="990000"), leg("income", amount="1000000", last4="5678")),  # tushgani ko'proq
    ],
)
def test_not_a_pair(first, second):
    assert is_transfer_pair(first, second) is False


def test_unknown_card_on_one_side_can_still_pair():
    assert is_transfer_pair(leg("expense", last4=None), leg("income", last4="5678")) is True


def test_incomplete_leg_never_pairs():
    assert is_transfer_pair(Leg(None, Decimal("1000000"), "UZS", AT, "1234"), leg("income", last4="5678")) is False
    assert is_transfer_pair(Leg("expense", None, "UZS", AT, "1234"), leg("income", last4="5678")) is False
    assert is_transfer_pair(Leg("expense", Decimal("1000000"), "UZS", None, "1234"), leg("income", last4="5678")) is False


async def save(session, user, kind, last4, minutes=0, amount="1000000"):
    card = await ts.find_card_by_last4(session, user.id, last4) or await ts.add_card(
        session, user.id, name=f"Karta {last4}", last4=last4, network="Humo"
    )
    parsed = make_parsed(
        transaction_type=kind, amount=Decimal(amount), occurred_at=AT + timedelta(minutes=minutes), card_last4=last4
    )
    return await ts.create_transaction(session, user, parsed, "P2P", None, card.id, NoteAnalysis())


def incoming(minutes=1, **overrides):
    base = {"transaction_type": "income", "amount": Decimal("1000000"), "occurred_at": AT + timedelta(minutes=minutes), "card_last4": "5678"}
    return make_parsed(**(base | overrides))


async def test_counterpart_is_found_among_saved_transactions(session, user):
    saved = await save(session, user, "expense", "1234")
    found = await find_transfer_counterpart(session, user.id, incoming())
    assert found.id == saved.id


async def test_counterpart_is_the_closest_in_time(session, user):
    await save(session, user, "expense", "1234", minutes=-8)
    close = await save(session, user, "expense", "1234", minutes=0)
    assert (await find_transfer_counterpart(session, user.id, incoming())).id == close.id


async def test_no_counterpart_for_unrelated_transactions(session, user):
    await save(session, user, "expense", "1234", amount="54000")
    await save(session, user, "income", "1234")
    assert await find_transfer_counterpart(session, user.id, incoming()) is None


async def test_counterpart_is_never_another_users_transaction(session, user, other_user):
    await save(session, other_user, "expense", "1234")
    assert await find_transfer_counterpart(session, user.id, incoming()) is None
