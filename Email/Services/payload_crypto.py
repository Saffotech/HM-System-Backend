"""Fernet encryption for email template payloads. Never log plaintext."""
from cryptography.fernet import Fernet, InvalidToken

from config import settings


class PayloadCryptoError(Exception):
    pass


def _fernet() -> Fernet:
    key = (settings.EMAIL_PAYLOAD_ENCRYPTION_KEY or "").strip()
    if not key:
        raise PayloadCryptoError("Email payload encryption is not configured")
    try:
        return Fernet(key.encode("utf-8"))
    except Exception as exc:
        raise PayloadCryptoError("Email payload encryption key is invalid") from exc


def encrypt_payload(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_payload(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise PayloadCryptoError("Email payload could not be decrypted") from exc
