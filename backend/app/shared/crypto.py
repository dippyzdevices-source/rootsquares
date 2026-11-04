"""Passwords (argon2), signed session tokens (JWT) and the Fernet encryption of square connection strings."""

from __future__ import annotations

import datetime as dt
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


# A fixed hash to verify against when the email is unknown, so a login takes about the same time either way.
DUMMY_HASH = _hasher.hash("not-a-real-password")


class Encryptor:
    """Fernet (AES-128-CBC + HMAC). The key comes from the environment (FERNET_KEY)."""

    def __init__(self, key: str) -> None:
        self._f = Fernet(key.encode())

    def encrypt(self, plain: str) -> str:
        return self._f.encrypt(plain.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._f.decrypt(token.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("cannot decrypt: wrong FERNET_KEY or corrupted value") from exc


def make_token(secret: str, sub: str, kind: str, ttl: dt.timedelta, **claims: str) -> str:
    now = dt.datetime.now(dt.UTC)
    return jwt.encode({**claims, "sub": sub, "typ": kind, "iat": now, "exp": now + ttl}, secret, algorithm="HS256")


def read_token(secret: str, token: str, kind: str) -> dict[str, Any] | None:
    try:
        claims: dict[str, Any] = jwt.decode(token, secret, algorithms=["HS256"], options={"require": ["exp", "sub", "typ"]})
    except jwt.PyJWTError:
        return None
    return claims if claims.get("typ") == kind else None
