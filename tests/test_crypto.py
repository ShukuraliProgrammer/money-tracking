import pytest
from cryptography.fernet import Fernet

from app.utils.crypto import Cipher, DecryptionError


def test_cipher_roundtrip_returns_original_text():
    cipher = Cipher(Fernet.generate_key().decode())
    token = cipher.encrypt("Kamolonda ovqatlandik 3 kishi")
    assert cipher.decrypt(token) == "Kamolonda ovqatlandik 3 kishi"


def test_cipher_output_does_not_contain_plaintext():
    cipher = Cipher(Fernet.generate_key().decode())
    assert "Kamolonda" not in cipher.encrypt("Kamolonda")


def test_cipher_rejects_token_from_another_key():
    token = Cipher(Fernet.generate_key().decode()).encrypt("secret")
    with pytest.raises(DecryptionError):
        Cipher(Fernet.generate_key().decode()).decrypt(token)


def test_cipher_rejects_malformed_key():
    with pytest.raises(ValueError):
        Cipher("not-a-key")
