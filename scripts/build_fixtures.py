"""Cross-compile known C sources. Never execute any compiler output."""

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def compiler() -> list[str]:
    if os.environ.get("RECON_CC"):
        return [os.environ["RECON_CC"]]
    import ziglang

    return [str(Path(ziglang.__file__).parent / "zig"), "cc", "-target", "x86_64-linux-musl"]


def build(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    cc = compiler()
    version = subprocess.run([*cc, "--version"], capture_output=True, text=True, check=True).stdout
    source = ROOT / "tests/fixtures/demo.c"
    manifest = {
        "source": "tests/fixtures/demo.c",
        "license": "MIT",
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "compiler_version": version.strip(),
        "builds": [],
    }
    for optimization in ["O0", "O2"]:
        target = output / f"demo-{optimization}.elf"
        flags = [
            f"-{optimization}",
            "-g",
            "-fno-inline",
            "-fno-builtin",
            "-fno-stack-protector",
            "-fno-sanitize=all",
            "-ffreestanding",
            "-nostdlib",
            "-static",
            "-Wl,-e,entry",
            "-Wl,--build-id=none",
        ]
        result = subprocess.run(
            [*cc, *flags, str(source), "-o", str(target)], capture_output=True, text=True
        )
        (output / f"{optimization}-build.txt").write_text(result.stdout + result.stderr)
        result.check_returncode()
        target.chmod(0o600)
        manifest["builds"].append(
            {
                "path": target.name,
                "flags": flags,
                "architecture": "x86-64",
                "optimization": optimization,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "executed": False,
            }
        )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / ".recon/fixtures")
    args = parser.parse_args()
    result = build(args.output)
    print(
        f"Compiled {len(result['builds'])} x86-64 ELF fixtures to {args.output}; neither was executed."
    )
