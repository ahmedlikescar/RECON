import json
import platform
import re
import shutil
import subprocess
import time
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

from elftools.elf.elffile import ELFFile

from recon import FEATURE_SCHEMA
from recon.config import REPO_ROOT, Settings
from recon.errors import ReconError
from recon.security.process import run_analysis
from recon.storage.artifacts import atomic_bytes, atomic_json, digest, read_json


def validate_dataset(dataset: dict[str, Any]) -> dict[str, Any]:
    if dataset.get("feature_schema") != FEATURE_SCHEMA:
        raise ReconError("DATASET_SCHEMA", "Dataset feature schema is incompatible.", 409)
    projects: dict[str, set[str]] = defaultdict(set)
    lineages: dict[str, set[str]] = defaultdict(set)
    source_hashes: dict[str, set[str]] = defaultdict(set)
    for sample in dataset["samples"]:
        projects[sample["project"]].add(sample["split"])
        lineages[sample["lineage"]].add(sample["split"])
        source_hashes[sample["source_function_hash"]].add(sample["split"])
    if any(len(v) > 1 for mapping in [projects, lineages, source_hashes] for v in mapping.values()):
        raise ReconError(
            "DATA_LEAKAGE",
            "Project, source lineage, or identical source function crosses dataset splits.",
            409,
        )
    if {s["split"] for s in dataset["samples"]} != {"train", "validation", "test"}:
        raise ReconError(
            "DATASET_SPLITS", "Train, validation, and test must all contain verified samples."
        )
    if near_duplicate_lineages(dataset["samples"]):
        raise ReconError(
            "DATA_LEAKAGE", "Near-duplicate normalized source functions cross splits.", 409
        )
    if dataset.get("dataset_hash") != dataset_hash(dataset):
        raise ReconError(
            "DATASET_INTEGRITY", "Dataset content changed without a matching manifest hash.", 409
        )
    return {
        "project_disjoint": True,
        "lineage_disjoint": True,
        "identical_source_disjoint": True,
        "near_duplicate_source_disjoint": True,
        "projects": {k: sorted(v) for k, v in projects.items()},
        "samples": len(dataset["samples"]),
    }


def dataset_hash(dataset: dict[str, Any]) -> str:
    value = {
        k: v
        for k, v in dataset.items()
        if k not in {"dataset_hash", "audit", "duration_seconds", "environment"}
    }
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def source_function_text(text: str, line: int) -> str:
    # Conservative balanced-brace extraction for these pinned C files; ambiguous cases are quarantined.
    tail = "\n".join(text.splitlines()[max(0, line - 1) :])
    opening = tail.find("{")
    if opening < 0 or ";" in tail[:opening]:
        raise ValueError("Not an unambiguous function definition")
    depth, end = 0, None
    for i, char in enumerate(tail[opening:], opening):
        depth += (char == "{") - (char == "}")
        if depth == 0:
            end = i + 1
            break
    if end is None:
        raise ValueError("Unbalanced function source")
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", tail[:end], flags=re.S)


def source_function_hash(text: str, line: int) -> str:
    return digest(re.sub(r"\s+", "", source_function_text(text, line)).encode())


def source_shingles(text: str, line: int) -> list[str]:
    text = source_function_text(text, line)
    tokens = re.findall(
        r'"(?:\\.|[^"\\])*"|\b[a-zA-Z_]\w*\b|\b\d+\b|==|!=|<=|>=|&&|\|\||[^\s]', text
    )
    keywords = {
        "if",
        "else",
        "return",
        "for",
        "while",
        "switch",
        "case",
        "break",
        "continue",
        "sizeof",
        "do",
        "int",
        "char",
        "long",
        "unsigned",
        "void",
        "const",
        "struct",
        "static",
        "float",
        "double",
        "short",
    }
    normalized = [t if t in keywords or not re.match(r'[a-zA-Z_0-9"]', t) else "ID" for t in tokens]
    return sorted(
        {
            digest(" ".join(normalized[i : i + 5]).encode())[:16]
            for i in range(max(0, len(normalized) - 4))
        }
    )


def near_duplicate_lineages(samples: list[dict[str, Any]]) -> set[str]:
    unique = {s["lineage"]: s for s in samples}
    rows = list(unique.values())
    duplicates = set()
    for pos, left in enumerate(rows):
        a = set(left.get("source_shingles", []))
        for right in rows[pos + 1 :]:
            if left["split"] == right["split"]:
                continue
            b = set(right.get("source_shingles", []))
            if a and b and len(a & b) / len(a | b) >= 0.9:
                duplicates.update([left["lineage"], right["lineage"]])
    return duplicates


def debug_labels(path: Path, source_name: str) -> dict[int, tuple[str, int]]:
    labels: dict[int, tuple[str, int]] = {}
    ambiguous: set[int] = set()
    with path.open("rb") as stream:
        elf = ELFFile(stream)
        dwarf = elf.get_dwarf_info()
        for cu in dwarf.iter_CUs():
            lines = dwarf.line_program_for_CU(cu)
            if not lines:
                continue
            for die in cu.iter_DIEs():
                attrs = die.attributes
                if die.tag != "DW_TAG_subprogram" or "DW_AT_low_pc" not in attrs:
                    continue
                origin = (
                    die.get_DIE_from_attribute("DW_AT_abstract_origin")
                    if "DW_AT_abstract_origin" in attrs
                    else die
                )
                attrs = {**origin.attributes, **attrs}
                if not all(
                    k in attrs for k in ["DW_AT_name", "DW_AT_decl_file", "DW_AT_decl_line"]
                ):
                    continue
                index = int(attrs["DW_AT_decl_file"].value) - (
                    0 if lines.header.version >= 5 else 1
                )
                files = lines.header.file_entry
                if index < 0 or index >= len(files):
                    continue
                filename = files[index].name.decode(errors="replace")
                if Path(filename).name != source_name:
                    continue
                name = attrs["DW_AT_name"].value.decode(errors="replace")
                address = int(attrs["DW_AT_low_pc"].value)
                label = (name, int(attrs["DW_AT_decl_line"].value))
                if address in labels and labels[address] != label:
                    ambiguous.add(address)
                else:
                    labels[address] = label
    for address in ambiguous:
        labels.pop(address, None)
    return labels


def toolchains() -> tuple[list[dict[str, Any]], list[str]]:
    found, missing = [], []
    for kind in ["gcc", "clang"]:
        path = shutil.which(kind)
        if path and platform.system() == "Linux":
            version = subprocess.run(
                [path, "--version"], capture_output=True, text=True, check=True
            ).stdout
            if kind == "gcc" and "clang" in version.lower():
                missing.append("gcc (gcc executable is actually Clang)")
                continue
            found.append({"name": kind, "command": [path], "version": version.strip()})
        else:
            missing.append(f"native {kind} x86-64 Linux toolchain")
    if not found:
        import ziglang

        zig_path = Path(ziglang.__file__).parent / "zig"
        command = [str(zig_path), "cc", "-target", "x86_64-linux-musl"]
        version = subprocess.run(
            [*command, "--version"], capture_output=True, text=True, check=True
        ).stdout
        found.append({"name": "zig-clang", "command": command, "version": version.strip()})
    return found, missing


def build_dataset(settings: Settings, *, offline: bool = False) -> Path:
    start = time.perf_counter()
    root = settings.root / "research"
    root.mkdir(parents=True, exist_ok=True)
    manifest = read_json(REPO_ROOT / "datasets/manifests/sources.json")
    compilers, missing = toolchains()
    samples: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    builds: list[dict[str, Any]] = []
    for project in manifest["projects"]:
        folder = root / "sources" / project["name"]
        hashes = {}
        for filename in project["files"]:
            target = folder / filename
            if not target.is_file():
                if offline:
                    raise ReconError(
                        "SOURCE_MISSING", f"Offline source missing: {project['name']}/{filename}"
                    )
                url = f"https://raw.githubusercontent.com/{project['repository']}/{project['commit']}/{filename}"
                with urllib.request.urlopen(url, timeout=30) as response:
                    data = response.read(4 * 1048576 + 1)
                if len(data) > 4 * 1048576:
                    raise ReconError(
                        "SOURCE_LIMIT", "Pinned source file exceeds the download budget."
                    )
                atomic_bytes(target, data)
            hashes[filename] = digest(target.read_bytes())
            if hashes[filename] != project["file_sha256"][filename]:
                raise ReconError(
                    "SOURCE_INTEGRITY",
                    f"Pinned source hash mismatch: {project['name']}/{filename}",
                    409,
                )
        source = folder / project["source"]
        source_text = source.read_text()
        for compiler in compilers:
            for optimization in ["O0", "O1", "O2", "O3"]:
                build_id = f"{project['name']}-{compiler['name']}-{optimization}"
                target = root / "builds" / f"{build_id}.so"
                target.parent.mkdir(parents=True, exist_ok=True)
                flags = [
                    f"-{optimization}",
                    "-g",
                    "-gdwarf-4",
                    "-fno-inline",
                    "-fno-builtin",
                    "-fno-stack-protector",
                    "-fno-sanitize=all",
                    "-fPIC",
                    "-shared",
                    "-nostartfiles",
                    "-Wl,--build-id=none",
                    f"-ffile-prefix-map={settings.root}=/recon-data",
                    f"-ffile-prefix-map={REPO_ROOT}=/recon-source",
                ]
                args = [*compiler["command"], *flags, str(source), "-o", str(target)]
                result = subprocess.run(args, capture_output=True, text=True, timeout=120)
                atomic_bytes(
                    target.with_suffix(".build.txt"), (result.stdout + result.stderr).encode()
                )
                if result.returncode:
                    quarantine.append(
                        {
                            "build_id": build_id,
                            "reason": "compiler_failed",
                            "diagnostics": result.stderr[:4000],
                        }
                    )
                    continue
                target.chmod(0o600)
                analysis = run_analysis(target, settings)
                labels = debug_labels(target, source.name)
                builds.append(
                    {
                        "id": build_id,
                        "project": project["name"],
                        "commit": project["commit"],
                        "source_hashes": hashes,
                        "license": project["license"],
                        "compiler": compiler["name"],
                        "compiler_version": compiler["version"],
                        "flags": [
                            flag.replace(str(settings.root), "<DATA_DIR>").replace(
                                str(REPO_ROOT), "<REPO_ROOT>"
                            )
                            for flag in flags
                        ],
                        "sha256": analysis.sha256,
                        "architecture": "x86-64",
                        "optimization": optimization,
                        "executed": False,
                    }
                )
                for function in analysis.functions:
                    label = labels.get(function.address)
                    if not label or label[0] != function.name or len(function.instructions) < 4:
                        quarantine.append(
                            {
                                "build_id": build_id,
                                "function": function.name,
                                "reason": "unverified_label_or_tiny_function",
                            }
                        )
                        continue
                    try:
                        source_hash = source_function_hash(source_text, label[1])
                    except ValueError:
                        quarantine.append(
                            {
                                "build_id": build_id,
                                "function": function.name,
                                "reason": "ambiguous_source_definition",
                            }
                        )
                        continue
                    lineage = f"{project['repository']}@{project['commit']}:{project['source']}:{label[0]}:{label[1]}"
                    samples.append(
                        {
                            "project": project["name"],
                            "split": project["split"],
                            "lineage": lineage,
                            "source_function_hash": source_hash,
                            "source_shingles": source_shingles(source_text, label[1]),
                            "source_line": label[1],
                            "label_method": "DWARF_entry_and_symbol_name",
                            "build_id": build_id,
                            "compiler": compiler["name"],
                            "optimization": optimization,
                            "function": function.model_dump(),
                        }
                    )
    # Quarantine identical function source shared across splits rather than force leakage.
    split_hashes: dict[str, set[str]] = defaultdict(set)
    for sample in samples:
        split_hashes[sample["source_function_hash"]].add(sample["split"])
    duplicates = {h for h, splits in split_hashes.items() if len(splits) > 1}
    samples = [s for s in samples if s["source_function_hash"] not in duplicates]
    if duplicates:
        quarantine.append({"reason": "cross_split_identical_source", "hashes": sorted(duplicates)})
    near_duplicates = near_duplicate_lineages(samples)
    samples = [s for s in samples if s["lineage"] not in near_duplicates]
    if near_duplicates:
        quarantine.append(
            {"reason": "cross_split_near_duplicate", "lineages": sorted(near_duplicates)}
        )
    dataset = {
        "schema_version": "dataset-1",
        "feature_schema": FEATURE_SCHEMA,
        "sources_manifest": manifest,
        "builds": builds,
        "samples": samples,
        "quarantine": quarantine,
        "missing_toolchains": missing,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "duration_seconds": time.perf_counter() - start,
        "limitations": [
            "Small pilot dataset; not evidence of generalization to arbitrary binaries.",
            "Inlining is disabled to establish reliable source lineages; real optimized binaries are harder.",
            "Exact duplicates and identifier-normalized source shingle similarity >=0.90 across splits are quarantined. Semantic duplicates may still remain.",
            "Cross-compiler evaluation requires separate genuine GCC/Clang builds. Missing toolchains are disclosed.",
        ],
    }
    dataset["dataset_hash"] = dataset_hash(dataset)
    dataset["audit"] = validate_dataset(dataset)
    path = root / "dataset.json"
    atomic_json(path, dataset)
    return path
