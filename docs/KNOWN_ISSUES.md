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
- The direct PyTorch/FAISS path crashed in a macOS test. FAISS now runs in a bounded
  separate interpreter with one OpenMP thread and exact NumPy fallback; that path
  has passed the real model/index regression test and local benchmark.
- The pilot has one held-out project, no inlining/LTO stress suite, and weaker neural
  results than the combined baseline. Query bootstrap intervals are not project-level
  generalization evidence. Open-world no-match precision has not been benchmarked.
- Only one API server/trainer per data directory is supported. Jobs show coarse
  persisted phases rather than fine per-instruction progress. CLI dataset builds are
  synchronous trusted-source operations.
- Compiler/project collection filters, explicit model import UI, standalone Ghidra
  adapter, human match annotations, and a full changed/unchanged/removed version report
  remain later work. See `TRACEABILITY.md` for individual requirement status.
- Full keyboard/screen-reader accessibility and native Windows execution are not
  verified. The browser suite covers a desktop and narrow viewport in Chromium only.
- The app's project-wide license remains an owner decision. Training source licenses
  and notices are preserved under `datasets/licenses/` and the pinned manifest.
