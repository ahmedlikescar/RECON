import copy
import struct
from pathlib import Path

import numpy as np
import pytest
from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from recon.cfg.graph import build_cfg
from recon.config import Settings
from recon.errors import ReconError
from recon.features.baselines import BaselineIndex
from recon.features.normalize import normalize
from recon.security.process import run_analysis
from recon.security.validation import csv_cell, inside, safe_filename, validate_elf
from recon.storage.artifacts import atomic_json, read_json


@pytest.fixture(scope="module")
def analysis(fixtures: Path, tmp_path_factory: pytest.TempPathFactory):
    settings = Settings(data_dir=tmp_path_factory.mktemp("analysis-workers"))
    return run_analysis(fixtures / "demo-O0.elf", settings)


def test_real_elf_functions_and_provenance(analysis):
    assert analysis.architecture == "x86-64"
    assert len(analysis.functions) == 9
    assert {"checksum_bytes", "reverse_bytes", "entry"} <= {f.name for f in analysis.functions}
    assert all(f.instructions and f.cfg.blocks for f in analysis.functions)
    assert all(f.discovery_method == "symbol_table" for f in analysis.functions)
    assert all(
        f.address <= i.address < f.end_address for f in analysis.functions for i in f.instructions
    )
    assert analysis.tool_versions["lief"] and analysis.duration_seconds > 0


def test_conditional_cfg_has_branch_and_fallthrough():
    decoder = Cs(CS_ARCH_X86, CS_MODE_64)
    decoder.detail = True
    # test edi,edi; je return_zero; mov eax,1; ret; xor eax,eax; ret
    code = bytes.fromhex("85ff7406b801000000c331c0c3")
    instructions = [normalize(i) for i in decoder.disasm(code, 0x1000)]
    cfg = build_cfg(instructions)
    assert len(cfg.blocks) == 3
    assert {(e.source, e.target, e.kind) for e in cfg.edges} == {
        ("b_1000", "b_100a", "branch"),
        ("b_1000", "b_1004", "fallthrough"),
    }
    assert instructions[1].token == "je|ADDR"


def test_call_does_not_create_intraprocedural_jump_edge():
    decoder = Cs(CS_ARCH_X86, CS_MODE_64)
    decoder.detail = True
    instructions = [normalize(i) for i in decoder.disasm(bytes.fromhex("e800000000c3"), 0x1000)]
    cfg = build_cfg(instructions)
    assert len(cfg.blocks) == 1 and cfg.edges == []


def test_normalization_removes_addresses_and_register_identity():
    decoder = Cs(CS_ARCH_X86, CS_MODE_64)
    decoder.detail = True
    a = normalize(next(decoder.disasm(bytes.fromhex("4889d8"), 0x1000)))
    b = normalize(next(decoder.disasm(bytes.fromhex("4d89c8"), 0x4000)))
    assert a.token == b.token == "mov|REG64,REG64"


def test_baseline_self_retrieval_and_names_are_not_features(analysis):
    functions = analysis.functions
    query = next(f for f in functions if f.name == "checksum_bytes")
    index = BaselineIndex(functions)
    scores, _ = index.scores(query, "hybrid")
    assert functions[int(scores.argmax())].name == "checksum_bytes"
    changed = query.model_copy(
        update={"name": "totally_different", "address": 123, "confidence": 0.01}
    )
    renamed_scores, _ = index.scores(changed, "hybrid")
    np.testing.assert_array_equal(scores, renamed_scores)


def test_persisted_baseline_matches_and_rejects_schema_drift(analysis, tmp_path):
    original = BaselineIndex(analysis.functions)
    path = tmp_path / "index.json"
    sha = atomic_json(path, original.manifest())
    restored = BaselineIndex.restore(analysis.functions, read_json(path, sha))
    expected, _ = original.scores(analysis.functions[0], "ngram")
    actual, _ = restored.scores(analysis.functions[0], "ngram")
    np.testing.assert_allclose(actual, expected, atol=1e-6)
    bad = copy.deepcopy(original.manifest())
    bad["feature_schema"] = "wrong"
    with pytest.raises(ReconError, match="schema"):
        BaselineIndex.restore(analysis.functions, bad)
    path.write_text("{}")
    with pytest.raises(ReconError, match="hash"):
        read_json(path, sha)


@pytest.mark.parametrize(
    "name", ["../program", "sub/program", "sub\\program", "x\x00y", ".", "a\n"]
)
def test_filename_traversal_rejected(name):
    with pytest.raises(ReconError):
        safe_filename(name)


def test_artifact_path_cannot_escape(tmp_path):
    with pytest.raises(ReconError):
        inside(tmp_path, "../outside")


@pytest.mark.parametrize(
    "symbol", ["=SUM(1,2)", " +cmd", "-2+3", "@name", "\tfunction", "\nformula"]
)
def test_csv_untrusted_symbols_are_not_formulas(symbol):
    assert csv_cell(symbol) == "'" + symbol


@pytest.mark.parametrize("data", [b"", b"MZ" + b"0" * 100, b"\x7fELF", b"\x7fELF" + b"0" * 100])
def test_invalid_inputs_rejected(data):
    with pytest.raises(ReconError):
        validate_elf(data, 1048576)


def test_oversized_architecture_and_section_bounds(fixtures):
    raw = (fixtures / "demo-O0.elf").read_bytes()
    with pytest.raises(ReconError) as exc:
        validate_elf(raw, len(raw) - 1)
    assert exc.value.code == "FILE_TOO_LARGE"
    wrong_arch = bytearray(raw)
    struct.pack_into("<H", wrong_arch, 18, 183)
    with pytest.raises(ReconError) as exc:
        validate_elf(wrong_arch, 1048576)
    assert exc.value.code == "UNSUPPORTED_ARCHITECTURE"
    truncated = raw[:100]
    with pytest.raises(ReconError):
        validate_elf(truncated, 1048576)


def test_worker_enforces_instruction_budget(fixtures, tmp_path):
    with pytest.raises(ReconError) as exc:
        run_analysis(fixtures / "demo-O0.elf", Settings(data_dir=tmp_path, max_instructions=100))
    assert exc.value.code == "INSTRUCTION_LIMIT"
    assert list(tmp_path.glob("worker-*")) == []


def test_worker_cancellation_leaves_no_partial_artifact(fixtures, tmp_path):
    with pytest.raises(ReconError) as exc:
        run_analysis(fixtures / "demo-O0.elf", Settings(data_dir=tmp_path), lambda: True)
    assert exc.value.code == "CANCELLED"
    assert list(tmp_path.glob("worker-*")) == []
