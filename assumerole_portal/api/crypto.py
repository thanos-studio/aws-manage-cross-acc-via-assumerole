from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken


class EncryptionError(Exception):
    pass


@dataclass
class CredentialCipher:
    key: bytes

    @classmethod
    def from_env(cls, env_var: str = "CREDENTIAL_ENCRYPTION_KEY") -> "CredentialCipher":
        raw = os.getenv(env_var)
        if not raw:
            raise EncryptionError(f"Missing encryption key in environment variable {env_var}")
        try:
            decoded = base64.urlsafe_b64decode(raw.encode())
        except Exception as exc:  # pragma: no cover - defensive
            raise EncryptionError("Invalid encryption key encoding") from exc
        if len(decoded) != 32:
            raise EncryptionError("Encryption key must decode to 32 bytes for Fernet")
        return cls(raw.encode())

    def _fernet(self) -> Fernet:
        return Fernet(self.key)

    def encrypt(self, value: str) -> str:
        return self._fernet().encrypt(value.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet().decrypt(token.encode()).decode()
        except InvalidToken as exc:  # pragma: no cover - incorrect key or tampered data
            raise EncryptionError("Unable to decrypt stored secret") from exc


def sha256_digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
