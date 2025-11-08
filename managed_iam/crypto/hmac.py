"""HMAC utilities for webhook signing."""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass


class SignatureError(ValueError):
    """Raised when signature validation fails."""


@dataclass
class HmacVerifier:
    """Validate signatures produced with a shared secret."""

    secret: bytes
    tolerance_seconds: int = 300

    def sign(self, payload: bytes, timestamp: int | None = None, nonce: str | None = None) -> str:
        ts = str(timestamp or int(time.time()))
        nonce_part = nonce or ""
        message = b"|".join([ts.encode(), nonce_part.encode(), payload])
        digest = hmac.new(self.secret, message, hashlib.sha256).hexdigest()
        return digest

    def verify(self, payload: bytes, provided_signature: str, timestamp: int, nonce: str) -> None:
        if abs(int(time.time()) - timestamp) > self.tolerance_seconds:
            raise SignatureError("signature timestamp outside tolerance")

        expected = self.sign(payload, timestamp=timestamp, nonce=nonce)
        if not hmac.compare_digest(expected, provided_signature):
            raise SignatureError("invalid signature")

