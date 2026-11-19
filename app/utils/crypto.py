"""Maxfiy maydonlarni (asl xabar, izoh) bazada shifrlangan holda saqlash."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class DecryptionError(Exception):
    """Shifrlangan qiymat joriy kalit bilan ochilmadi."""


class Cipher:
    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode())
        except (ValueError, TypeError) as error:
            raise ValueError(
                "ENCRYPTION_KEY noto‘g‘ri. Yangi kalit: "
                'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            ) from error

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except InvalidToken as error:
            raise DecryptionError("Qiymatni ochib bo‘lmadi: ENCRYPTION_KEY o‘zgargan bo‘lishi mumkin") from error


_cipher: Cipher | None = None


def get_cipher() -> Cipher:
    """Sozlamalardagi ENCRYPTION_KEY bilan ishlaydigan yagona shifrlovchi."""
    global _cipher
    if _cipher is None:
        from app.config import get_settings

        _cipher = Cipher(get_settings().encryption_key.get_secret_value())
    return _cipher
