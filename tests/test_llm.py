import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.schemas import LLMNoteAnalysis, LLMTransaction
from app.services.llm import (
    NOTE_SYSTEM_PROMPT,
    PARSE_SYSTEM_PROMPT,
    LLMError,
    LLMService,
    extract_json,
)

TZ = ZoneInfo("Asia/Tashkent")
NOW = datetime(2026, 11, 19, 15, 30, tzinfo=TZ)

VALID_TRANSACTION = json.dumps(
    {
        "transaction_type": "expense",
        "amount": 250000,
        "currency": "uzs",
        "merchant": "Kamolon",
        "card_last4": "1234",
        "card_network": "Uzcard",
        "occurred_at": "2026-11-19T10:15:00+05:00",
        "category_guess": "Ovqatlanish",
        "confidence": 0.86,
        "missing_fields": [],
        "explanation": "ok",
    }
)


class ScriptedClient:
    """LLM o'rniga navbat bilan tayyor javob qaytaradi."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts: list[tuple[str, str]] = []

    async def complete(self, system: str, user: str, schema: dict) -> str:
        self.prompts.append((system, user))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def test_extract_json_reads_plain_object():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_reads_fenced_object_with_prose():
    assert extract_json('Here you go:\n```json\n{"a": 1}\n```\nDone') == {"a": 1}


def test_extract_json_rejects_non_object():
    with pytest.raises(ValueError):
        extract_json("[1, 2, 3]")


def test_extract_json_rejects_garbage():
    with pytest.raises(ValueError):
        extract_json("not json at all")


async def test_parse_transaction_returns_validated_model():
    service = LLMService(ScriptedClient(VALID_TRANSACTION))
    result = await service.parse_transaction("xabar", "Asia/Tashkent", NOW, ["Ovqatlanish"])
    assert isinstance(result, LLMTransaction)
    assert result.currency == "UZS"
    assert result.card_last4 == "1234"


async def test_invalid_json_is_retried():
    client = ScriptedClient("oops, not json", VALID_TRANSACTION)
    service = LLMService(client, max_attempts=3)
    result = await service.parse_transaction("xabar", "Asia/Tashkent", NOW, [])
    assert result.amount == 250000
    assert len(client.prompts) == 2


async def test_schema_violation_is_retried():
    wrong_shape = json.dumps({"transaction_type": "spending", "amount": "many"})
    client = ScriptedClient(wrong_shape, VALID_TRANSACTION)
    result = await LLMService(client, max_attempts=3).parse_transaction("xabar", "Asia/Tashkent", NOW, [])
    assert result.transaction_type == "expense"


async def test_gives_up_after_max_attempts():
    client = ScriptedClient("bad", "bad", "bad")
    with pytest.raises(LLMError):
        await LLMService(client, max_attempts=3).parse_transaction("xabar", "Asia/Tashkent", NOW, [])
    assert len(client.prompts) == 3


async def test_provider_error_is_not_retried_by_service():
    client = ScriptedClient(LLMError("rate limited"), VALID_TRANSACTION)
    with pytest.raises(LLMError):
        await LLMService(client, max_attempts=3).parse_transaction("xabar", "Asia/Tashkent", NOW, [])
    assert len(client.prompts) == 1


async def test_parse_prompt_carries_message_time_and_categories():
    client = ScriptedClient(VALID_TRANSACTION)
    await LLMService(client).parse_transaction("Kamolonda 250 ming", "Asia/Tashkent", NOW, ["Ovqatlanish", "P2P"])
    system, user = client.prompts[0]
    assert system == PARSE_SYSTEM_PROMPT
    assert "Kamolonda 250 ming" in user
    assert "Asia/Tashkent" in user
    assert "2026-11-19T15:30" in user
    assert "Ovqatlanish" in user and "P2P" in user


def test_llm_transaction_cleans_up_unusable_values():
    model = LLMTransaction.model_validate(
        {
            "transaction_type": "expense",
            "amount": -5,
            "currency": "so'm",
            "card_last4": "12",
            "card_network": "Mir",
            "occurred_at": "yesterday-ish",
            "confidence": 3,
        }
    )
    assert model.amount is None
    assert model.currency == "UZS"
    assert model.card_last4 is None
    assert model.card_network == "Unknown"
    assert model.occurred_at is None
    assert model.confidence == 1.0


async def test_analyze_note_returns_validated_model():
    reply = json.dumps(
        {
            "category_guess": "Ovqatlanish",
            "tags": ["do'stlar", "tushlik"],
            "people_count": 3,
            "is_shared_expense": True,
            "is_recurring": False,
            "recurring_period": "none",
            "summary": "3 kishi Kamolonda ovqatlandi",
        }
    )
    client = ScriptedClient(reply)
    result = await LLMService(client).analyze_note(
        note="Kamolonda ovqatlandik 3 kishi",
        merchant="KAMOLON",
        transaction_type="expense",
        categories=["Ovqatlanish", "P2P"],
    )
    assert isinstance(result, LLMNoteAnalysis)
    assert result.people_count == 3
    assert result.is_shared_expense is True
    system, user = client.prompts[0]
    assert system == NOTE_SYSTEM_PROMPT
    assert "Kamolonda ovqatlandik 3 kishi" in user and "KAMOLON" in user


def test_note_analysis_normalizes_bad_period():
    model = LLMNoteAnalysis.model_validate({"recurring_period": "fortnightly", "people_count": 0})
    assert model.recurring_period == "none"
    assert model.people_count is None
