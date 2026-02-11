"""Tests for ankismart.core.crypto module."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from ankismart.core.crypto import _derive_key, decrypt, encrypt


class TestDeriveKey:
    def test_returns_bytes(self):
        key = _derive_key()
        assert isinstance(key, bytes)

    def test_key_length_is_44(self):
        # Fernet keys are 32 bytes, base64-encoded = 44 bytes
        key = _derive_key()
        assert len(key) == 44

    def test_deterministic(self):
        assert _derive_key() == _derive_key()

    def test_different_machine_gives_different_key(self):
        real_key = _derive_key()
        with patch("ankismart.core.crypto.platform") as mock_platform:
            mock_platform.node.return_value = "other-host"
            mock_platform.machine.return_value = "arm64"
            other_key = _derive_key()
        assert real_key != other_key


class TestEncryptDecrypt:
    def test_round_trip(self):
        plaintext = "sk-secret-api-key-12345"
        ciphertext = encrypt(plaintext)
        assert ciphertext != plaintext
        assert decrypt(ciphertext) == plaintext

    def test_encrypt_returns_string(self):
        ct = encrypt("hello")
        assert isinstance(ct, str)

    def test_empty_string_round_trip(self):
        ct = encrypt("")
        assert decrypt(ct) == ""

    def test_unicode_round_trip(self):
        text = "密钥测试 🔑"
        assert decrypt(encrypt(text)) == text

    def test_decrypt_bad_ciphertext_raises(self):
        with pytest.raises(Exception):
            decrypt("not-valid-ciphertext")

    def test_ciphertext_is_different_each_time(self):
        # Fernet includes a timestamp, so two encryptions differ
        a = encrypt("same")
        b = encrypt("same")
        assert a != b
        # But both decrypt to the same value
        assert decrypt(a) == decrypt(b) == "same"
