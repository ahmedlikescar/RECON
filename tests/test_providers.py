from pathlib import Path

import pytest
from recon.analysis.native import analyze_file
from recon.analysis.providers import REA_VERSION, AnalysisOrchestrator, REAProvider, normalize_rea
from recon.config import Settings
from recon.errors import ReconError


def test_optional_provider_missing_and_disabled():
    assert not REAProvider(Settings()).healthcheck()["enabled"]
    health = REAProvider(Settings(rea_enabled=True, rea_command=Path("/missing/rea"))).healthcheck()
    assert not health["available"]
    assert "missing" in health["reason"].lower()


def test_normalize_pinned_contract_and_provenance(fixtures, tmp_path):
    binary = fixtures / "demo-O0.elf"
    function = analyze_file(binary, Settings()).functions[0]
    evidence = {
        "operation": "analyze_function",
        "evidence_id": "synthetic-contract-fixture",
        "limitations": ["fixture, not a real REA run"],
        "normalized_result": {
            "procedure": {"address": hex(function.address), "name": function.name},
            "assembly": ["fixture assembly"],
            "pseudocode": "fixture pseudocode",
            "incoming_references": [],
            "outgoing_references": [],
            "limitations": [],
        },
    }
    result = normalize_rea(evidence, binary, function)
    assert result["provider_version"] == REA_VERSION
    assert result["function_address"] == function.address
    assert result["source_artifact_hash"]
    assert result["raw_evidence"] == evidence
    evidence["normalized_result"]["procedure"]["address"] = "0x1"
    with pytest.raises(ReconError, match="different function"):
        normalize_rea(evidence, binary, function)


def test_provider_timeout_falls_back_to_actual_native_evidence(fixtures, tmp_path, monkeypatch):
    binary = fixtures / "demo-O0.elf"
    function = analyze_file(binary, Settings()).functions[0]
    orchestrator = AnalysisOrchestrator(Settings(data_dir=tmp_path))

    def timeout(*args, **kwargs):
        raise ReconError("PROVIDER_TIMEOUT", "Provider exceeded deadline", 409)

    monkeypatch.setattr(orchestrator.optional, "get_evidence", timeout)
    result = orchestrator.investigate(binary, function, True)
    assert result["fallback"] and result["provider"] == "native"
    assert result["assembly"][0]["address"] == function.instructions[0].address
    assert result["provider_error"]["code"] == "PROVIDER_TIMEOUT"
