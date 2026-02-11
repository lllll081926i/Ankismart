from __future__ import annotations

import base64
import hashlib
import platform

from cryptography.fernet import Fernet


def _derive_key() -> bytes:
    """Derive a Fernet key from machine-specific identifiers."""
    machine_id = f"{platform.node()}-{platform.machine()}-ankismart-salt"
    key_bytes = hashlib.sha256(machine_id.encode()).digest()
    return base64.urlsafe_b64encode(key_bytes)


def encrypt(plaintext: str) -> str:
    """Encrypt a string and return base64-encoded ciphertext."""
    f = Fernet(_derive_key())
    return f.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext and return plaintext."""
    f = Fernet(_derive_key())
    return f.decrypt(ciphertext.encode()).decode()
