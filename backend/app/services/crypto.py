"""Envelope encryption for at-rest secrets.

Layered keys:

  KEK (from ENCRYPTION_KEK env var)
   └── wraps the per-user DEK (data encryption key)
        └── encrypts the user's actual secrets (refresh_token, etc.)

Benefits over single-key Fernet:
- Rotating the KEK only requires re-wrapping DEKs, not re-encrypting ciphertext.
- KMS upgrade path: replace the KEK with a call to AWS KMS / GCP KMS later
  without a schema change.

All functions are pure — they accept inputs and return outputs, no I/O.
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet


def generate_dek() -> bytes:
    """Return a fresh Fernet-compatible DEK (url-safe base64 of 32 random bytes)."""
    return Fernet.generate_key()


def _kek_fernet(kek_raw: str) -> Fernet:
    """Derive a Fernet key from the KEK env-var string.

    The KEK is intentionally lenient: ANY non-empty string is accepted and
    SHA-256-hashed down to a deterministic 32 bytes. That keeps dev defaults
    simple while still requiring at least 32 bytes of entropy in production
    (use `python -c 'import secrets; print(secrets.token_urlsafe(32))'`).
    """
    if not kek_raw:
        raise ValueError("ENCRYPTION_KEK is empty")
    digest = hashlib.sha256(kek_raw.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def wrap_dek(dek: bytes, kek_raw: str) -> bytes:
    return _kek_fernet(kek_raw).encrypt(dek)


def unwrap_dek(wrapped: bytes, kek_raw: str) -> bytes:
    """Decrypt the DEK using the KEK. Raises ``InvalidToken`` on tampered input."""
    return _kek_fernet(kek_raw).decrypt(wrapped)


def encrypt(plaintext: str, dek: bytes) -> bytes:
    return Fernet(dek).encrypt(plaintext.encode("utf-8"))


def decrypt(ciphertext: bytes, dek: bytes) -> str:
    return Fernet(dek).decrypt(ciphertext).decode("utf-8")
