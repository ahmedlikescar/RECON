import re
import struct
from pathlib import Path

from recon.errors import ReconError


def safe_filename(name: str | None) -> str:
    name = name or "binary.elf"
    if len(name) > 200 or name in {".", ".."} or any(c in name for c in "/\\\x00"):
        raise ReconError(
            "UNSAFE_FILENAME", "Use a filename without directories or path separators."
        )
    if any(ord(c) < 32 for c in name):
        raise ReconError("UNSAFE_FILENAME", "The filename contains control characters.")
    return name


def safe_id(value: str) -> str:
    if not re.fullmatch(r"[a-f0-9]{32}", value):
        raise ReconError("NOT_FOUND", "Record not found.", 404)
    return value


def inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ReconError("UNSAFE_PATH", "Artifact path escapes the storage directory.", 409)
    return path


def validate_elf(data: bytes, max_bytes: int) -> dict[str, int]:
    if len(data) > max_bytes:
        raise ReconError(
            "FILE_TOO_LARGE", f"File exceeds the {max_bytes // 1048576} MiB limit.", 413
        )
    if not data.startswith(b"\x7fELF"):
        raise ReconError(
            "UNSUPPORTED_FORMAT",
            "This release supports x86-64 ELF executables and shared libraries. PE and Mach-O are not supported yet.",
        )
    if len(data) < 64:
        raise ReconError("CORRUPT_ELF", "The ELF header is truncated.")
    if data[4:7] != b"\x02\x01\x01":
        raise ReconError(
            "UNSUPPORTED_ARCHITECTURE", "Only little-endian, 64-bit ELF version 1 is supported."
        )
    fields = struct.unpack_from("<HHIQQQIHHHHHH", data, 16)
    kind, machine, version, entry, phoff, shoff, _, ehsize, phsize, phnum, shsize, shnum, shstr = (
        fields
    )
    if machine != 62:
        raise ReconError("UNSUPPORTED_ARCHITECTURE", "This ELF is not x86-64.")
    if kind not in {2, 3}:
        raise ReconError(
            "UNSUPPORTED_ELF_TYPE",
            "Import a linked executable or shared library, not a relocatable object.",
        )
    if ehsize != 64 or version != 1:
        raise ReconError("CORRUPT_ELF", "Invalid ELF header size or version.")
    if not 0 < shnum <= 4096 or shsize != 64 or shstr >= shnum:
        raise ReconError(
            "UNSUPPORTED_ELF_LAYOUT",
            "A bounded, conventional section table is required; sectionless and extended-numbering ELF are not supported.",
        )
    if shoff < 64 or shoff + shsize * shnum > len(data):
        raise ReconError("CORRUPT_ELF", "Section table extends beyond the file.")
    if phnum > 1024 or (
        phnum and (phsize != 56 or phoff < 64 or phoff + phsize * phnum > len(data))
    ):
        raise ReconError("CORRUPT_ELF", "Invalid program header table.")
    for i in range(phnum):
        _, _, offset, _, _, filesz, memsz, _ = struct.unpack_from(
            "<IIQQQQQQ", data, phoff + i * phsize
        )
        if filesz > memsz or offset + filesz > len(data) or memsz > 512 * 1048576:
            raise ReconError("CORRUPT_ELF", "Invalid or over-budget program segment.")
    executable_size = 0
    for i in range(shnum):
        _, stype, flags, _, offset, size, _, _, _, _ = struct.unpack_from(
            "<IIQQQQIIQQ", data, shoff + i * shsize
        )
        if size > 128 * 1048576 or (stype != 8 and offset + size > len(data)):
            raise ReconError("CORRUPT_ELF", "Invalid or over-budget section.")
        if flags & 0x800:
            raise ReconError(
                "UNSUPPORTED_COMPRESSION",
                "Compressed ELF sections are not supported in this release.",
            )
        if flags & 4:
            executable_size += size
    if executable_size == 0:
        raise ReconError(
            "NO_CODE", "No executable sections were found. The file may be packed or unsupported."
        )
    if executable_size > max_bytes:
        raise ReconError(
            "ANALYSIS_LIMIT", "Executable sections exceed the configured analysis budget."
        )
    return {"entry_point": entry, "section_count": shnum}
