import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path

from recon.config import Settings
from recon.errors import ReconError
from recon.schemas import Analysis
from recon.storage.artifacts import read_json


def run_analysis(
    source: Path, settings: Settings, cancelled: Callable[[], bool] | None = None
) -> Analysis:
    settings.root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="worker-", dir=settings.root) as scratch:
        target = Path(scratch) / "result.json"
        command = [
            sys.executable,
            "-m",
            "recon.security.worker",
            str(source.resolve()),
            str(target),
            settings.model_dump_json(),
        ]
        # OS-level network/write denial on macOS, plus resource/audit limits in worker.
        # On Linux use container networking/filesystem isolation in the documented launcher.
        if sys.platform == "darwin" and Path("/usr/bin/sandbox-exec").exists():
            profile = f"(version 1)(allow default)(deny network*)(deny file-write* (require-not (subpath {json.dumps(scratch)})))"
            command = ["/usr/bin/sandbox-exec", "-p", profile, *command]
        env = {
            k: v
            for k, v in os.environ.items()
            if k in {"PATH", "HOME", "SYSTEMROOT", "LANG", "VIRTUAL_ENV"}
        }
        env.update(
            {"PYTHONDONTWRITEBYTECODE": "1", "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}
        )
        with (Path(scratch) / "stderr").open("wb") as stderr:
            process = subprocess.Popen(
                command,
                cwd=scratch,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=stderr,
                start_new_session=True,
            )
            started = time.monotonic()
            try:
                while process.poll() is None:
                    if cancelled and cancelled():
                        raise ReconError("CANCELLED", "Analysis cancelled.", 409)
                    if time.monotonic() - started > settings.worker_timeout:
                        raise ReconError(
                            "WORKER_TIMEOUT", "Static parser exceeded its wall-clock budget."
                        )
                    if sys.platform == "darwin":
                        # RLIMIT_AS is not enforced by macOS: monitor the worker's actual RSS.
                        usage = subprocess.run(
                            ["/bin/ps", "-o", "rss=", "-p", str(process.pid)],
                            capture_output=True,
                            text=True,
                            timeout=2,
                            check=False,
                        ).stdout.strip()
                        if usage.isdigit() and int(usage) > settings.worker_memory_mb * 1024:
                            raise ReconError(
                                "MEMORY_LIMIT", "Static parser exceeded its memory budget."
                            )
                    time.sleep(0.05)
            finally:
                if process.poll() is None:
                    with suppress(ProcessLookupError):
                        os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        if process.returncode != 0 or not target.exists():
            raise ReconError(
                "WORKER_FAILED",
                "The isolated parser stopped unexpectedly or hit a resource limit. No analysis was saved.",
            )
        if target.stat().st_size > 64 * 1048576:
            raise ReconError("OUTPUT_LIMIT", "Parser output exceeded the artifact budget.")
        result = read_json(target)
        if not result["ok"]:
            raise ReconError(result["error"]["code"], result["error"]["message"])
        return Analysis.model_validate(result["analysis"])
