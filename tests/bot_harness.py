"""Botni haqiqiy Telegram'siz sinash uchun yordamchi.

Dispatcher haqiqiy, faqat tarmoq sessiyasi soxta: bot yuborgan har bir so'rov
ro'yxatga yoziladi va testlar shu ro'yxatni tekshiradi.
"""

from __future__ import annotations

import itertools
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import EditMessageText, GetFile, GetMe, SendDocument, SendMessage, SendPhoto, TelegramMethod
from aiogram.types import Chat, File, Message, Update, User

from app.bot.dispatcher import build_dispatcher
from app.services.notes import NoteAnalyzer
from app.services.parser import TransactionParser


class RecordingSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[TelegramMethod[Any]] = []
        self.file_bytes = b"\xff\xd8fake-jpeg-bytes"  # bot "yuklab oladigan" fayl mazmuni
        self._ids = itertools.count(1000)

    async def close(self) -> None:
        pass

    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:
        self.requests.append(method)
        if isinstance(method, (SendMessage, SendDocument, SendPhoto, EditMessageText)):
            return Message(
                message_id=getattr(method, "message_id", None) or next(self._ids),
                date=datetime.now(),
                chat=Chat(id=int(method.chat_id or 0), type="private"),
                text=getattr(method, "text", None),
            )
        if isinstance(method, GetFile):
            return File(file_id=method.file_id, file_unique_id="u", file_size=20, file_path="photos/file_1.jpg")
        if isinstance(method, GetMe):
            return User(id=42, is_bot=True, first_name="MoneyTrack", username="moneytrack_test_bot")
        return True

    async def stream_content(self, *args: Any, **kwargs: Any) -> AsyncGenerator[bytes, None]:
        yield self.file_bytes


class BotHarness:
    def __init__(self, session_factory, now: datetime, llm=None, user_id: int = 1001, dispatcher=None) -> None:
        self.session = RecordingSession()
        self.bot = Bot(
            "123456789:TEST-TOKEN-NOT-REAL-000000000000000000",
            session=self.session,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        self.now = now
        self.user_id = user_id
        self.dp = dispatcher or build_dispatcher(
            session_factory=session_factory,
            parser=TransactionParser(llm),
            note_analyzer=NoteAnalyzer(llm),
            storage=MemoryStorage(),
            clock=lambda: self.now,
        )
        self._update_ids = itertools.count(1)
        self._message_ids = itertools.count(1)

    def as_user(self, user_id: int) -> BotHarness:
        """Xuddi shu botga boshqa foydalanuvchi nomidan yozish."""
        other = BotHarness.__new__(BotHarness)
        other.__dict__.update(self.__dict__)
        other.user_id = user_id
        return other

    # --- yuborish --------------------------------------------------------- #

    def _from(self) -> dict[str, Any]:
        return {"id": self.user_id, "is_bot": False, "first_name": "Ali", "username": f"user{self.user_id}"}

    def _chat(self, chat_type: str = "private") -> dict[str, Any]:
        return {"id": self.user_id, "type": chat_type}

    async def _feed(self, payload: dict[str, Any]) -> list[TelegramMethod[Any]]:
        before = len(self.session.requests)
        update = Update.model_validate({"update_id": next(self._update_ids), **payload}, context={"bot": self.bot})
        await self.dp.feed_update(self.bot, update)
        return self.session.requests[before:]

    async def send(self, text: str, forward_from: str | None = None, forward_date: datetime | None = None,
                   chat_type: str = "private") -> list[TelegramMethod[Any]]:  # fmt: skip
        message: dict[str, Any] = {
            "message_id": next(self._message_ids),
            "date": int(self.now.timestamp()),
            "chat": self._chat(chat_type),
            "from": self._from(),
            "text": text,
        }
        if text.startswith("/"):
            message["entities"] = [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}]
        if forward_from or forward_date:
            message["forward_origin"] = {
                "type": "user",
                "date": int((forward_date or self.now).timestamp()),
                "sender_user": {"id": 777, "is_bot": True, "first_name": "Bank", "username": forward_from or "somebot"},
            }
        return await self._feed({"message": message})

    async def send_photo(self) -> list[TelegramMethod[Any]]:
        message = {
            "message_id": next(self._message_ids),
            "date": int(self.now.timestamp()),
            "chat": self._chat(),
            "from": self._from(),
            "photo": [{"file_id": "f", "file_unique_id": "u", "width": 10, "height": 10}],
        }
        return await self._feed({"message": message})

    async def send_file(self, file_name: str, mime_type: str | None = None, data: bytes | None = None):
        """Rasmni «fayl» sifatida yuborish (siqilmagan holda)."""
        if data is not None:
            self.session.file_bytes = data
        document = {"file_id": "d", "file_unique_id": "ud", "file_name": file_name, "file_size": 5000}
        if mime_type:
            document["mime_type"] = mime_type
        message = {
            "message_id": next(self._message_ids),
            "date": int(self.now.timestamp()),
            "chat": self._chat(),
            "from": self._from(),
            "document": document,
        }
        return await self._feed({"message": message})

    async def click(self, label: str) -> list[TelegramMethod[Any]]:
        """Oxirgi klaviaturadan matnida ``label`` bor tugmani bosadi."""
        source = self.last_with_keyboard()
        for row in source.reply_markup.inline_keyboard:
            for button in row:
                if label in button.text:
                    return await self.click_data(button.callback_data, source)
        raise AssertionError(f"Tugma topilmadi: {label!r}. Bor tugmalar: {self.buttons()}")

    async def click_data(self, data: str, source: Any = None) -> list[TelegramMethod[Any]]:
        callback = {
            "id": str(next(self._update_ids)),
            "from": self._from(),
            "chat_instance": "test",
            "data": data,
            "message": {
                "message_id": getattr(source, "message_id", None) or 999,
                "date": int(self.now.timestamp()),
                "chat": self._chat(),
                "text": getattr(source, "text", None) or "eski xabar",
            },
        }
        return await self._feed({"callback_query": callback})

    # --- o'qish ----------------------------------------------------------- #

    def _mine(self) -> list[Any]:
        return [
            request for request in self.session.requests
            if isinstance(request, (SendMessage, EditMessageText, SendDocument))
            and int(request.chat_id) == self.user_id
        ]  # fmt: skip

    def last_with_keyboard(self) -> Any:
        for request in reversed(self._mine()):
            if getattr(request, "reply_markup", None) is not None and hasattr(request.reply_markup, "inline_keyboard"):
                return request
        raise AssertionError("Klaviaturali xabar yo'q")

    def last_text(self) -> str:
        for request in reversed(self._mine()):
            if isinstance(request, (SendMessage, EditMessageText)):
                return request.text
        raise AssertionError("Bot hali hech narsa yubormadi")

    def all_text(self) -> str:
        return "\n---\n".join(r.text for r in self._mine() if isinstance(r, (SendMessage, EditMessageText)))

    def buttons(self) -> list[str]:
        return [button.text for row in self.last_with_keyboard().reply_markup.inline_keyboard for button in row]

    def documents(self) -> list[SendDocument]:
        return [request for request in self._mine() if isinstance(request, SendDocument)]
