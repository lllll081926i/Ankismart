from __future__ import annotations

import base64
import hashlib
import os
import platform

from cryptography.fernet import Fernet, InvalidToken

_MASTER_KEY_ENV = "ANKISMART_MASTER_KEY"
_MASTER_KEY_SALT = "ankismart-master-salt"
_MACHINE_KEY_SALT = "ankismart-salt"


def _derive_machine_key() -> bytes:
    """Derive a Fernet key from machine-specific identifiers."""
    machine_id = f"{platform.node()}-{platform.machine()}-{_MACHINE_KEY_SALT}"
    key_bytes = hashlib.sha256(machine_id.encode()).digest()
    return base64.urlsafe_b64encode(key_bytes)


def _derive_master_key(secret: str) -> bytes:
    material = f"{secret}-{_MASTER_KEY_SALT}"
    key_bytes = hashlib.sha256(material.encode()).digest()
    return base64.urlsafe_b64encode(key_bytes)


def _get_master_secret() -> str:
    return os.getenv(_MASTER_KEY_ENV, "").strip()


def _derive_key() -> bytes:
    """Derive active Fernet key.

    Priority:
    1. ANKISMART_MASTER_KEY (cross-device stable)
    2. Machine-bound fallback (legacy behavior)
    """
    secret = _get_master_secret()
    if secret:
        return _derive_master_key(secret)
    return _derive_machine_key()


def encrypt(plaintext: str) -> str:
    """Encrypt a string and return base64-encoded ciphertext."""
    f = Fernet(_derive_key())
    return f.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext and return plaintext."""
    encoded = ciphertext.encode()
    last_error: Exception | None = None
    candidate_keys = [_derive_key()]

    # When master key is enabled, keep backward compatibility with machine key.
    if _get_master_secret():
        machine_key = _derive_machine_key()
        if machine_key not in candidate_keys:
            candidate_keys.append(machine_key)

    for key in candidate_keys:
        try:
            return Fernet(key).decrypt(encoded).decode()
        except InvalidToken as exc:
            last_error = exc
            continue

    raise last_error or InvalidToken()
