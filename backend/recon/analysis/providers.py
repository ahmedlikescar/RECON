import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from contextlib import suppress
from pathlib import Path
from typing import Any, Protocol

from recon.config import Settings
from recon.errors import ReconError
from recon.schemas import FunctionAnalysis
from recon.storage.artifacts import atomic_json, digest
from recon.storage.database import now

REA_VERSION = "6.8.0"
REA_SOURCE_COMMIT = "f69c52a1cf3940ed1999fcc0859a75dbb913d684"


class AnalysisProvider(Protocol):
    def capabilities(self) -> dict[str, Any]: ...
    def healthcheck(self) -> dict[str, Any]: ...
    def inspect_binary(self, binary: Path) -> dict[str, Any]: ...
    def list_functions(self, binary: Path) -> dict[str, Any]: ...
    def inspect_function(self, binary: Path, function: FunctionAnalysis) -> dict[str, Any]: ...
    def get_call_references(self, binary: Path, function: FunctionAnalysis) -> dict[str, Any]: ...
    def get_evidence(self, binary: Path, function: FunctionAnalysis) -> dict[str, Any]: ...


def bounded_command(
    command: list[str], timeout: int, cwd: Path, env: dict[str, str] | None = None
) -> str:
    """Owner-configured tool only; no shell and no target execution commands."""
    with tempfile.TemporaryDirectory(prefix="provider-", dir=cwd) as scratch:
        output = Path(scratch) / "output"
        with output.open("wb") as stream:
            process = subprocess.Popen(
                command,
                cwd=scratch,
                env=env,
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            started = time.monotonic()
            try:
                while process.poll() is None:
                    if time.monotonic() - started > timeout:
                        raise ReconError(
                            "PROVIDER_TIMEOUT",
                            "Optional analysis provider exceeded its deadline. Native evidence is still available.",
                            409,
                        )
                    if output.stat().st_size > 16 * 1048576:
                        raise ReconError(
                            "PROVIDER_OUTPUT_LIMIT",
                            "Optional provider output exceeded its budget.",
                            409,
                        )
                    time.sleep(0.05)
            finally:
                if process.poll() is None:
                    with suppress(ProcessLookupError):
                        os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        if output.stat().st_size > 16 * 1048576:
            raise ReconError(
                "PROVIDER_OUTPUT_LIMIT", "Optional provider output exceeded its budget.", 409
            )
        text = output.read_text(errors="replace")
        if process.returncode:
            raise ReconError(
                "PROVIDER_FAILED",
                "Optional provider failed. Check its local configuration; native evidence is still available.",
                409,
            )
        return text


def normalize_rea(
    evidence: dict[str, Any], binary: Path, function: FunctionAnalysis
) -> dict[str, Any]:
    if evidence.get("operation") != "analyze_function" or not isinstance(
        evidence.get("normalized_result"), dict
    ):
        raise ReconError(
            "PROVIDER_SCHEMA",
            "REA did not return a complete analyze_function Evidence record.",
            409,
        )
    result = evidence["normalized_result"]
    if not isinstance(result.get("procedure"), dict) or not isinstance(
        result.get("assembly"), list
    ):
        raise ReconError(
            "PROVIDER_SCHEMA", "REA function dossier does not match the pinned contract.", 409
        )
    procedure = result["procedure"]
    provider_address = str(procedure.get("address", ""))
    try:
        if int(provider_address, 16) != function.address:
            raise ValueError("address mismatch")
    except ValueError as exc:
        raise ReconError(
            "EVIDENCE_ADDRESS", "Provider evidence belongs to a different function address.", 409
        ) from exc
    return {
        "provider": "rea-ghidra",
        "provider_version": REA_VERSION,
        "function_address": function.address,
        "instruction_range": [function.address, function.end_address],
        "assembly": result["assembly"],
        "pseudocode": result.get("pseudocode") or None,
        "symbols": procedure,
        "references": {
            "incoming": result.get("incoming_references", []),
            "outgoing": result.get("outgoing_references", []),
            "unresolved_calls": result.get("unresolved_calls", []),
        },
        "source_artifact_hash": digest(binary.read_bytes()),
        "evidence_links": [evidence.get("evidence_id")],
        "limitations": [
            *evidence.get("limitations", []),
            *result.get("limitations", []),
            "Provider observations are static evidence, not ground truth or changes to ML scores.",
        ],
        "collected_at": now(),
        "raw_evidence": evidence,
        "external_ai_provider": None,
    }


class REAProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    def healthcheck(self) -> dict[str, Any]:
        command = self.settings.rea_command
        if not self.settings.rea_enabled:
            return {
                "id": "rea",
                "enabled": False,
                "available": False,
                "reason": "Optional integration is disabled. Native analysis and matching work independently.",
            }
        if not shutil.which("node"):
            return {
                "id": "rea",
                "enabled": True,
                "available": False,
                "reason": "Node.js is missing from PATH. REA 6.8.0 requires Node ^22.23.4, ^24.22.1, or >=26.12.1.",
            }
        if command is None or not command.is_file():
            return {
                "id": "rea",
                "enabled": True,
                "available": False,
                "reason": "REA executable is missing. Review the pinned setup plan in docs/REA_INTEGRATION.md before installing.",
            }
        ghidra = self.settings.ghidra_path
        if ghidra is None or not (ghidra / "support/analyzeHeadless").is_file():
            return {
                "id": "rea",
                "enabled": True,
                "available": False,
                "reason": "Ghidra is missing. Configure RECON_GHIDRA_PATH to an installed Ghidra directory.",
            }
        self.settings.root.mkdir(parents=True, exist_ok=True)
        try:
            text = bounded_command(
                [str(command.resolve()), "--version", "--json"], 5, self.settings.root
            )
            if not re.search(r"\b6\.8\.0\b", text):
                raise ReconError(
                    "REA_VERSION", "REA version is incompatible; this adapter pins 6.8.0.", 409
                )
            return {
                "id": "rea",
                "enabled": True,
                "available": True,
                "version": REA_VERSION,
                "reason": "Pinned executable and Ghidra path detected; actual provider capabilities are checked on request.",
            }
        except ReconError as exc:
            return {"id": "rea", "enabled": True, "available": False, "reason": exc.message}

    def call(
        self, command: str, binary: Path | None = None, selector: str | None = None
    ) -> dict[str, Any]:
        health = self.healthcheck()
        if not health["available"]:
            raise ReconError("PROVIDER_UNAVAILABLE", health["reason"], 409)
        args = [str(self.settings.rea_command.resolve()), command]  # type: ignore[union-attr]
        if binary:
            args.extend([str(binary.resolve()), "--provider", "ghidra"])
        if selector:
            args.append("--procedure=" + selector)
        args.append("--json")
        env = {k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "LANG", "JAVA_HOME"}}
        env["GHIDRA_INSTALL_DIR"] = str(self.settings.ghidra_path)
        env["REA_ANALYSIS_PROVIDER"] = "ghidra"
        env["JAVA_TOOL_OPTIONS"] = "-Xmx512m"
        raw = bounded_command(args, self.settings.provider_timeout, self.settings.root, env)
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ReconError(
                "PROVIDER_SCHEMA",
                "REA returned invalid JSON; native evidence is still available.",
                409,
            ) from exc
        if not isinstance(result, dict):
            raise ReconError("PROVIDER_SCHEMA", "REA output is not an Evidence object.", 409)
        return result

    def capabilities(self) -> dict[str, Any]:
        return self.call("capabilities")

    def inspect_binary(self, binary: Path) -> dict[str, Any]:
        return self.call("inspect", binary)

    def list_functions(self, binary: Path) -> dict[str, Any]:
        # Inventory is part of inspect Evidence, not an invented CLI list-functions command.
        return self.inspect_binary(binary)

    def inspect_function(self, binary: Path, function: FunctionAnalysis) -> dict[str, Any]:
        return normalize_rea(self.call("function", binary, hex(function.address)), binary, function)

    def get_call_references(self, binary: Path, function: FunctionAnalysis) -> dict[str, Any]:
        return self.inspect_function(binary, function)["references"]

    def get_evidence(self, binary: Path, function: FunctionAnalysis) -> dict[str, Any]:
        return self.inspect_function(binary, function)


class NativeProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    def healthcheck(self) -> dict[str, Any]:
        return {
            "id": "native",
            "enabled": True,
            "available": True,
            "reason": "LIEF + Capstone static analysis. No external service or API key.",
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            "static": True,
            "formats": ["ELF"],
            "architectures": ["x86-64"],
            "pseudocode": False,
        }

    def inspect_binary(self, binary: Path) -> dict[str, Any]:
        from recon.security.process import run_analysis

        return run_analysis(binary, self.settings).model_dump()

    def list_functions(self, binary: Path) -> dict[str, Any]:
        return {"functions": self.inspect_binary(binary)["functions"]}

    def inspect_function(self, binary: Path, function: FunctionAnalysis) -> dict[str, Any]:
        return {
            "provider": "native",
            "provider_version": "native-1",
            "function_address": function.address,
            "instruction_range": [function.address, function.end_address],
            "assembly": [i.model_dump() for i in function.instructions],
            "pseudocode": None,
            "source_artifact_hash": digest(binary.read_bytes()),
            "collected_at": now(),
            "limitations": [
                *function.limitations,
                "Native provider does not decompile source code.",
            ],
            "external_ai_provider": None,
        }

    def get_call_references(self, binary: Path, function: FunctionAnalysis) -> dict[str, Any]:
        return {
            "outgoing": [
                {"address": i.address, "target": i.branch_target}
                for i in function.instructions
                if i.flow == "call"
            ],
            "limitations": ["Direct calls only; indirect call targets are unknown."],
        }

    def get_evidence(self, binary: Path, function: FunctionAnalysis) -> dict[str, Any]:
        return self.inspect_function(binary, function)


class AnalysisOrchestrator:
    def __init__(self, settings: Settings):
        self.native = NativeProvider(settings)
        self.optional = REAProvider(settings)

    def investigate(
        self, binary: Path, function: FunctionAnalysis, consent: bool
    ) -> dict[str, Any]:
        if not consent:
            raise ReconError(
                "PROVIDER_CONSENT",
                "Approve the optional local Ghidra investigation before starting it. The target itself will not be executed.",
                409,
            )
        try:
            result = self.optional.get_evidence(binary, function)
            result["fallback"] = False
            return result
        except ReconError as exc:
            result = self.native.get_evidence(binary, function)
            result.update(
                {"fallback": True, "provider_error": {"code": exc.code, "message": exc.message}}
            )
            return result


def provider_status(settings: Settings) -> list[dict[str, Any]]:
    return [NativeProvider(settings).healthcheck(), REAProvider(settings).healthcheck()]


def investigate_function(
    settings: Settings, binary: Path, function: FunctionAnalysis, consent: bool
) -> dict[str, Any]:
    result = AnalysisOrchestrator(settings).investigate(binary, function, consent)
    path = settings.root / "evidence" / f"{digest(binary.read_bytes())}-{function.address:x}.json"
    atomic_json(path, result)
    return result
