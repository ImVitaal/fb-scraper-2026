"""Windows Data Protection API wrappers for current-user session encryption."""

from __future__ import annotations

import ctypes
from ctypes import wintypes


class DpapiError(RuntimeError):
    """Raised when Windows DPAPI cannot encrypt or decrypt session bytes."""


class DataBlob(ctypes.Structure):
    """Native DATA_BLOB required by CryptProtectData APIs."""

    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(value: bytes) -> tuple[DataBlob, ctypes.Array[ctypes.c_char]]:
    if not value:
        raise DpapiError("DPAPI input must be non-empty")
    buffer = ctypes.create_string_buffer(value)
    return DataBlob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def _copy_and_free(blob: DataBlob) -> bytes:
    try:
        return ctypes.string_at(blob.pbData, blob.cbData)
    finally:
        if blob.pbData:
            ctypes.windll.kernel32.LocalFree(blob.pbData)


def protect_for_current_user(plaintext: bytes) -> bytes:
    """Encrypt bytes for only the current Windows user."""
    source, _buffer = _blob(plaintext)
    result = DataBlob()
    success = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)
    )
    if not success:
        raise DpapiError(f"CryptProtectData failed: {ctypes.get_last_error()}")
    return _copy_and_free(result)


def unprotect_for_current_user(ciphertext: bytes) -> bytes:
    """Decrypt current-user DPAPI bytes and fail closed on an invalid envelope."""
    source, _buffer = _blob(ciphertext)
    result = DataBlob()
    success = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)
    )
    if not success:
        raise DpapiError(f"CryptUnprotectData failed: {ctypes.get_last_error()}")
    return _copy_and_free(result)
