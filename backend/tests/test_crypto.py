"""Tests for the envelope-encryption service.

Direct tests of the pure crypto module — no DB, no SP-API, no I/O.
"""
from __future__ import annotations

import secrets

import pytest
from cryptography.fernet import InvalidToken

from app.services import crypto


def _fresh_kek() -> str:
    """Return a freshly generated 32-byte url-safe base64 KEK."""
    return secrets.token_urlsafe(32)


def test_dek_wrap_unwrap_roundtrip() -> None:
    kek = _fresh_kek()
    dek = crypto.generate_dek()
    wrapped = crypto.wrap_dek(dek, kek)
    assert wrapped != dek
    unwrapped = crypto.unwrap_dek(wrapped, kek)
    assert unwrapped == dek


def test_unwrap_with_wrong_kek_fails() -> None:
    kek_a = _fresh_kek()
    kek_b = _fresh_kek()
    wrapped = crypto.wrap_dek(crypto.generate_dek(), kek_a)
    with pytest.raises(InvalidToken):
        crypto.unwrap_dek(wrapped, kek_b)


def test_tampered_dek_fails_to_unwrap() -> None:
    kek = _fresh_kek()
    wrapped = bytearray(crypto.wrap_dek(crypto.generate_dek(), kek))
    # Flip a byte in the ciphertext.
    wrapped[-5] = (wrapped[-5] + 1) % 256
    with pytest.raises(InvalidToken):
        crypto.unwrap_dek(bytes(wrapped), kek)


def test_encrypt_decrypt_roundtrip_for_secret() -> None:
    dek = crypto.generate_dek()
    plaintext = "amzn1.oa2-cs.v1.SECRET-VALUE-1234"
    ciphertext = crypto.encrypt(plaintext, dek)
    assert ciphertext != plaintext.encode("utf-8")
    assert crypto.decrypt(ciphertext, dek) == plaintext


def test_decrypt_with_wrong_dek_fails() -> None:
    dek_a = crypto.generate_dek()
    dek_b = crypto.generate_dek()
    ciphertext = crypto.encrypt("hello", dek_a)
    with pytest.raises(InvalidToken):
        crypto.decrypt(ciphertext, dek_b)


def test_tampered_ciphertext_fails_decrypt() -> None:
    """Fernet tokens are base64; flip a byte well inside the body with XOR
    so we land on a still-decodable-but-semantically-different sequence
    that fails HMAC verification."""
    dek = crypto.generate_dek()
    ciphertext = bytearray(
        crypto.encrypt("hello-world-this-needs-to-be-long-enough", dek)
    )
    ciphertext[10] ^= 0xFF
    with pytest.raises(InvalidToken):
        crypto.decrypt(bytes(ciphertext), dek)


def test_empty_kek_rejected() -> None:
    with pytest.raises(ValueError):
        crypto.wrap_dek(crypto.generate_dek(), "")


def test_kek_is_sha256_derived_so_any_string_works() -> None:
    """The dev default `dev-only-kek-replace-in-production-please-32b` should
    encrypt+decrypt round-trip even though it's not 32 bytes of base64."""
    kek = "dev-only-kek-replace-in-production-please-32b"
    dek = crypto.generate_dek()
    wrapped = crypto.wrap_dek(dek, kek)
    assert crypto.unwrap_dek(wrapped, kek) == dek
