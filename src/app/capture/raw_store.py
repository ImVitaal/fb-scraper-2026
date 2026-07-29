"""Gzip raw-capture storage with SHA-256 integrity verification."""

from __future__ import annotations

import gzip
import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile


class RawCaptureIntegrityError(RuntimeError):
    """Raised when stored capture bytes do not match their recorded digest."""


@dataclass(frozen=True)
class StoredRawCapture:
    """Immutable location and integrity data for one raw capture."""

    capture_id: str
    sha256: str
    path: Path
    byte_count: int


class GzipRawCaptureStore:
    """Store private raw capture bytes outside the repository working tree."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def write(
        self, capture_id: str, raw_bytes: bytes, *, suffix: str = ".json"
    ) -> StoredRawCapture:
        """Write deterministic gzip bytes and return their verified metadata."""
        if not capture_id:
            raise ValueError("capture_id must be non-empty")
        digest = sha256(raw_bytes).hexdigest()
        path = self.root / f"{capture_id}{suffix}.gz"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing = self.read(capture_id, digest)
            if existing != raw_bytes:
                raise RawCaptureIntegrityError(f"capture bytes conflict: {capture_id}")
        else:
            self._atomic_write(path, gzip.compress(raw_bytes, mtime=0))
        return StoredRawCapture(capture_id, digest, path, len(raw_bytes))

    def read(self, capture_id: str, expected_sha256: str, *, suffix: str = ".json") -> bytes:
        """Read, decompress, and verify one capture against its recorded hash."""
        path = self.root / f"{capture_id}{suffix}.gz"
        try:
            raw_bytes = gzip.decompress(path.read_bytes())
        except (OSError, EOFError) as error:
            message = f"raw capture sha256 verification failed: {capture_id}"
            raise RawCaptureIntegrityError(message) from error
        actual = sha256(raw_bytes).hexdigest()
        if actual != expected_sha256.lower():
            raise RawCaptureIntegrityError(f"raw capture sha256 mismatch: {capture_id}")
        return raw_bytes

    @staticmethod
    def _atomic_write(path: Path, compressed_bytes: bytes) -> None:
        """Flush raw bytes before replacing the final capture path."""
        temporary: Path | None = None
        try:
            with NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as destination:
                temporary = Path(destination.name)
                destination.write(compressed_bytes)
                destination.flush()
                os.fsync(destination.fileno())
            temporary.replace(path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
