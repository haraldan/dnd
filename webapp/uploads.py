"""Transient on-disk store for uploaded PDFs.

Files are written to a temp directory (``SPELLHDR_UPLOAD_DIR``), keyed by an
opaque per-browser session token and a ``kind`` (``header`` / ``spells``). They
are NOT durable state: every write opportunistically sweeps away any files older
than ``SPELLHDR_UPLOAD_TTL`` seconds, so the store cleans itself with no
background thread or cron. This keeps RAM flat and allows multiple workers.
"""

from __future__ import annotations

import os
import pathlib
import tempfile
import time

_DEFAULT_TTL = 3600  # seconds
_ALLOWED_KINDS = ("header", "spells")


def upload_dir() -> pathlib.Path:
    path = pathlib.Path(
        os.environ.get(
            "SPELLHDR_UPLOAD_DIR",
            os.path.join(tempfile.gettempdir(), "spellhdr-uploads"),
        )
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ttl() -> int:
    try:
        return int(os.environ.get("SPELLHDR_UPLOAD_TTL", _DEFAULT_TTL))
    except ValueError:
        return _DEFAULT_TTL


def _path(token: str, kind: str) -> pathlib.Path:
    if kind not in _ALLOWED_KINDS:
        raise ValueError(f"unknown upload kind: {kind!r}")
    # token is a hex uuid from the server; still guard against path tricks.
    safe = "".join(c for c in token if c.isalnum())
    return upload_dir() / f"{safe}_{kind}.pdf"


def sweep() -> None:
    """Delete upload files older than the TTL. Best-effort; never raises."""
    cutoff = time.time() - _ttl()
    try:
        for f in upload_dir().glob("*_*.pdf"):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
            except OSError:
                pass
    except OSError:
        pass


def save(token: str, kind: str, data: bytes) -> None:
    """Atomically store an uploaded PDF, sweeping stale files first."""
    sweep()
    path = _path(token, kind)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load(token: str, kind: str) -> bytes | None:
    """Return the stored PDF bytes, or None if absent."""
    try:
        return _path(token, kind).read_bytes()
    except (FileNotFoundError, OSError):
        return None
