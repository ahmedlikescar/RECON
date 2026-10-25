"""Single-use parser process. The target is never invoked as a program."""

import os
import resource
import sys
from pathlib import Path

from recon.analysis.native import analyze_file
from recon.config import Settings
from recon.errors import ReconError
from recon.storage.artifacts import atomic_json


def limits(settings: Settings) -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (settings.worker_timeout, settings.worker_timeout + 1))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1048576, 64 * 1048576))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    if sys.platform == "linux":
        limit = settings.worker_memory_mb * 1048576
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


def audit(event: str, args: tuple[object, ...]) -> None:
    if event.startswith(("subprocess.", "socket.")) or event in {
        "os.system",
        "os.exec",
        "os.posix_spawn",
        "pty.spawn",
    }:
        raise PermissionError("Parser workers cannot launch programs or open network connections.")


def main() -> None:
    source, target, settings_json = sys.argv[1:]
    settings = Settings.model_validate_json(settings_json)
    os.umask(0o077)
    limits(settings)
    sys.addaudithook(audit)
    try:
        result = {"ok": True, "analysis": analyze_file(Path(source), settings).model_dump()}
    except ReconError as exc:
        result = {"ok": False, "error": {"code": exc.code, "message": exc.message}}
    except (Exception, MemoryError) as exc:
        result = {
            "ok": False,
            "error": {
                "code": "PARSER_FAILED",
                "message": f"Static parser failed ({type(exc).__name__}). Try an unstripped, unpacked ELF build.",
            },
        }
    atomic_json(Path(target), result)


if __name__ == "__main__":
    main()
