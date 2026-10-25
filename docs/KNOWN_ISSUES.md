# Known issues and scope

- This is an incremental implementation. Consult `PROGRESS.md` for verified features.
- x86-64 little-endian ELF executables/shared libraries are the initial target.
  PE, Mach-O, relocatable objects, sectionless ELF, compressed sections, and extended
  section numbering currently fail explicitly.
- Stripped binary boundaries are uncertain. The fallback uses ELF entry points
  and direct-call targets; it does not recover jump tables, exception control flow,
  or all tail-call functions.
- Known UPX markers are rejected. This is not a comprehensive packer/encryption detector.
- macOS workers have OS network/write denial, a wall/CPU budget and monitored RSS.
  Linux workers have resource/audit limits; OS filesystem/network isolation requires
  the documented container launcher. Windows support is through WSL2, not native.
- No actual GCC build or cross-compiler benchmark has run on this Apple Silicon host.
- REA/Ghidra are optional and have not been installed or configured. No real provider
  investigation is claimed. REA setup requires the explicit approval described in the specification.
