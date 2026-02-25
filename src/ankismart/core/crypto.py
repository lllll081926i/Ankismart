from __future__ import annotations

import base64
import ctypes
import hashlib
import os
import platform

from cryptography.fernet import Fernet, InvalidToken

_MASTER_KEY_ENV = "ANKISMART_MASTER_KEY"
_MASTER_KEY_SALT = "ankismart-master-salt"
_MACHINE_KEY_SALT = "ankismart-salt"
_DPAPI_PREFIX = "dpapi:"
_IS_WINDOWS = platform.system().lower().startswith("win")

if _IS_WINDOWS:
    from ctypes import wintypes

    class _DataBlob(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte)),
        ]

    _CryptProtectData = ctypes.windll.crypt32.CryptProtectData
    _CryptProtectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    _CryptProtectData.restype = wintypes.BOOL

    _CryptUnprotectData = ctypes.windll.crypt32.CryptUnprotectData
    _CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    _CryptUnprotectData.restype = wintypes.BOOL

    _LocalFree = ctypes.windll.kernel32.LocalFree
    _LocalFree.argtypes = [wintypes.HLOCAL]
    _LocalFree.restype = wintypes.HLOCAL


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


def _dpapi_encrypt(plaintext: str) -> str:
    if not _IS_WINDOWS:
        raise RuntimeError("DPAPI is only available on Windows")
    raw = plaintext.encode("utf-8")
    if not raw:
        return _DPAPI_PREFIX

    in_buffer = ctypes.create_string_buffer(raw)
    in_blob = _DataBlob(
        cbData=len(raw),
        pbData=ctypes.cast(in_buffer, ctypes.POINTER(ctypes.c_byte)),
    )
    out_blob = _DataBlob()
    ok = _CryptProtectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob))
    if not ok:
        raise OSError(f"CryptProtectData failed with code {ctypes.get_last_error()}")
    try:
        protected = ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        if out_blob.pbData:
            _LocalFree(out_blob.pbData)
    return _DPAPI_PREFIX + base64.urlsafe_b64encode(protected).decode("ascii")


def _dpapi_decrypt(ciphertext: str) -> str:
    if not _IS_WINDOWS:
        raise InvalidToken()
    token = ciphertext[len(_DPAPI_PREFIX):]
    if not token:
        return ""
    protected = base64.urlsafe_b64decode(token.encode("ascii"))

    in_buffer = ctypes.create_string_buffer(protected)
    in_blob = _DataBlob(
        cbData=len(protected),
        pbData=ctypes.cast(in_buffer, ctypes.POINTER(ctypes.c_byte)),
    )
    out_blob = _DataBlob()
    desc = wintypes.LPWSTR()

    ok = _CryptUnprotectData(
        ctypes.byref(in_blob),
        ctypes.byref(desc),
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise InvalidToken()
    try:
        plain = ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        if out_blob.pbData:
            _LocalFree(out_blob.pbData)
        if desc:
            _LocalFree(desc)
    return plain.decode("utf-8")


def encrypt(plaintext: str) -> str:
    """Encrypt a string and return base64-encoded ciphertext."""
    if not plaintext:
        return ""
    if not _get_master_secret() and _IS_WINDOWS:
        return _dpapi_encrypt(plaintext)
    f = Fernet(_derive_key())
    return f.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext and return plaintext."""
    if not ciphertext:
        return ""
    if ciphertext.startswith(_DPAPI_PREFIX):
        return _dpapi_decrypt(ciphertext)

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
