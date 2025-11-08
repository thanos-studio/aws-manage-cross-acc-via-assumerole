"""AES-GCM envelope encryption helper."""

from __future__ import annotations

import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


@dataclass
class EnvelopeCipher:
    """Provide authenticated encryption using AES-GCM."""

    key: bytes

    NONCE_SIZE = 12

    def encrypt(self, plaintext: bytes, associated_data: bytes | None = None) -> bytes:
        aesgcm = AESGCM(self.key)
        nonce = os.urandom(self.NONCE_SIZE)
        ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)
        return nonce + ciphertext

    def decrypt(self, payload: bytes, associated_data: bytes | None = None) -> bytes:
        nonce = payload[: self.NONCE_SIZE]
        ciphertext = payload[self.NONCE_SIZE :]
        aesgcm = AESGCM(self.key)
        return aesgcm.decrypt(nonce, ciphertext, associated_data)

