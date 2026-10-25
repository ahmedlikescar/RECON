import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from recon.errors import ReconError


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".partial-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def atomic_json(path: Path, data: Any) -> str:
    raw = json.dumps(data, sort_keys=True, ensure_ascii=True, allow_nan=False).encode()
    atomic_bytes(path, raw)
    return digest(raw)


def read_json(path: Path, expected_hash: str | None = None) -> Any:
    raw = path.read_bytes()
    if expected_hash and digest(raw) != expected_hash:
        raise ReconError(
            "ARTIFACT_INTEGRITY", "Stored artifact hash does not match. Reanalyze this file.", 409
        )
    return json.loads(raw)
