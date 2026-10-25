import hashlib
import time
from pathlib import Path
from typing import Any

import capstone
import lief
from capstone import CS_ARCH_X86, CS_MODE_64, Cs

from recon.cfg.graph import build_cfg
from recon.config import Settings
from recon.errors import ReconError
from recon.features.normalize import normalize
from recon.schemas import Analysis, FunctionAnalysis
from recon.security.validation import validate_elf


def text(value: str | bytes) -> str:
    return value.decode(errors="replace") if isinstance(value, bytes) else value


def analyze_file(path: Path, settings: Settings) -> Analysis:
    """Static bytes only. Call through the constrained worker for user uploads."""
    started = time.perf_counter()
    data = path.read_bytes()
    validate_elf(data, settings.max_upload_bytes)
    lief.logging.disable()
    binary = lief.ELF.parse(data)
    if binary is None:
        raise ReconError("CORRUPT_ELF", "LIEF could not parse this ELF.")
    sections = list(binary.sections)
    if any(text(s.name).lower().startswith(("upx", ".upx")) for s in sections):
        raise ReconError(
            "PACKED_INPUT",
            "UPX section markers found. Import an authorized unpacked build instead.",
        )
    code = [s for s in sections if int(s.flags) & 4 and s.size and s.type.name != "NOBITS"]
    decoder = Cs(CS_ARCH_X86, CS_MODE_64)
    decoder.detail = True
    # Entry point + exact symbol addresses. Names are presentation/provenance only.
    entries: dict[int, tuple[str, int, str, float]] = {}

    def section_for(address: int) -> Any:
        return next(
            (s for s in code if s.virtual_address <= address < s.virtual_address + s.size), None
        )

    for symbol in binary.symbols:
        if symbol.type.name != "FUNC" or symbol.shndx == 0 or not section_for(symbol.value):
            continue
        if symbol.size > settings.max_function_bytes:
            raise ReconError(
                "FUNCTION_LIMIT",
                f"A symbol exceeds the {settings.max_function_bytes}-byte function budget.",
            )
        entry = (text(symbol.name) or f"sub_{symbol.value:x}", int(symbol.size), "symbol_table", 1.0)
        previous = entries.get(int(symbol.value))
        if previous is None or previous[1] < entry[1]:
            entries[int(symbol.value)] = entry
    if section_for(binary.entrypoint) and binary.entrypoint not in entries:
        entries[int(binary.entrypoint)] = (
            f"entry_{binary.entrypoint:x}",
            0,
            "elf_entry_heuristic",
            0.55,
        )
    # Conservative stripped-file fallback. Linear sweep is explicitly uncertain.
    if not any(e[2] == "symbol_table" for e in entries.values()):
        sweep_budget = settings.max_instructions
        for section in code:
            raw = data[section.offset : section.offset + section.size]
            for ins in decoder.disasm(raw, section.virtual_address, count=sweep_budget):
                sweep_budget -= 1
                if ins.group(capstone.CS_GRP_CALL) and ins.operands and ins.operands[0].type == 2:
                    address = int(ins.operands[0].imm)
                    if section_for(address) and address not in entries:
                        entries[address] = (f"sub_{address:x}", 0, "direct_call_heuristic", 0.4)
                if sweep_budget <= 0:
                    raise ReconError(
                        "INSTRUCTION_LIMIT",
                        "Stripped-file discovery reached the instruction budget.",
                    )
    if not entries:
        raise ReconError(
            "NO_FUNCTIONS",
            "No function symbols, usable entry point, or direct call targets were found. Try a symbol-bearing build or optional Ghidra.",
        )
    if len(entries) > settings.max_functions:
        raise ReconError("FUNCTION_LIMIT", "Too many functions for the configured analysis budget.")
    addresses = sorted(entries)
    functions = []
    total_instructions = 0
    for pos, address in enumerate(addresses):
        name, size, method, confidence = entries[address]
        section = section_for(address)
        assert section is not None
        section_end = int(section.virtual_address + section.size)
        next_address = addresses[pos + 1] if pos + 1 < len(addresses) else section_end
        end = (
            min(address + size, section_end)
            if size
            else min(next_address, section_end, address + settings.max_function_bytes)
        )
        offset = int(section.offset + address - section.virtual_address)
        raw = data[offset : offset + end - address]
        instructions = []
        for instruction in decoder.disasm(raw, address):
            instructions.append(normalize(instruction))
            total_instructions += 1
            if total_instructions > settings.max_instructions:
                raise ReconError(
                    "INSTRUCTION_LIMIT", "Analysis reached the configured instruction budget."
                )
        if not instructions:
            continue
        decoded_end = instructions[-1].address + instructions[-1].size
        limitations = []
        if not size:
            limitations.append(
                "Function end is estimated from neighboring entries and section bounds; it may include padding or other code."
            )
        if decoded_end < end:
            limitations.append(
                "Disassembly stopped before the declared function end; the remaining bytes are undecoded."
            )
        cfg = build_cfg(instructions)
        if cfg.unresolved_branches:
            limitations.append(
                "Some jumps leave this function or use indirect targets. CFG edges are incomplete; jump tables are not resolved."
            )
        functions.append(
            FunctionAnalysis(
                address=address,
                end_address=end,
                name=name,
                discovery_method=method,
                confidence=confidence,
                bytes_hash=hashlib.sha256(raw).hexdigest(),
                instructions=instructions,
                cfg=cfg,
                limitations=limitations,
            )
        )
    if not functions:
        raise ReconError("NO_FUNCTIONS", "No decodable functions were found.")
    return Analysis(
        sha256=hashlib.sha256(data).hexdigest(),
        entry_point=int(binary.entrypoint),
        sections=[
            {
                "name": text(s.name),
                "address": int(s.virtual_address),
                "size": int(s.size),
                "executable": bool(int(s.flags) & 4),
            }
            for s in sections
        ],
        imports=sorted({text(s.name) for s in binary.imported_symbols if s.name}),
        functions=functions,
        limitations=[
            "Static inspection only; the imported binary was never executed.",
            "Similar machine code is not proof of equivalent behavior. Packing and encryption detection is limited to known markers and decodability.",
            "Symbol tables and heuristic boundaries may be incomplete or incorrect. Exception edges and indirect jump tables are not recovered.",
        ],
        duration_seconds=time.perf_counter() - started,
        tool_versions={"lief": getattr(lief, "__version__", "unknown"), "capstone": capstone.__version__},
    )
