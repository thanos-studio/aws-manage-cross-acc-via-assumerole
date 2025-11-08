"""Utility to hash values for verification without storing plaintext."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass


@dataclass
class VerificationHash:
    """Generate and validate salted hashes using PBKDF2."""

    iterations: int = 100_000
    salt_size: int = 16

    def hash(self, value: str) -> str:
        salt = os.urandom(self.salt_size)
        digest = hashlib.pbkdf2_hmac("sha256", value.encode(), salt, self.iterations)
        return base64.b64encode(salt + digest).decode()

    def verify(self, value: str, hashed: str) -> bool:
        raw = base64.b64decode(hashed.encode())
        salt = raw[: self.salt_size]
        digest = raw[self.salt_size :]
        candidate = hashlib.pbkdf2_hmac("sha256", value.encode(), salt, self.iterations)
        return hmac.compare_digest(candidate, digest)
