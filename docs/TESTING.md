# Validation log

## 2026-10-25 parser checkpoint

Host: Apple Silicon, macOS 27.0.1, Python 3.12.14. Demo builds use Zig 0.15.2's
x86-64 Linux cross compiler, at O0 and O2. No compiled output was executed.

Commands:

```sh
uv sync --extra research
python scripts/build_fixtures.py
pytest tests/test_static_analysis.py -q
mypy backend/recon/analysis/native.py backend/recon/cfg backend/recon/features backend/recon/security backend/recon/storage/artifacts.py
ruff check backend/recon/analysis/native.py backend/recon/cfg backend/recon/features backend/recon/security
```

The first test run found a real persistence bug: scikit-learn's vocabulary
indices included NumPy integers that JSON cannot serialize. Index manifests now
convert those indices explicitly. Mypy also caught disassembly flow typing and
LIEF's bytes-or-string symbol names; both were corrected. A demo compile initially
failed because Zig's debug sanitizer runtime required libc in a freestanding
binary; known fixture builds now explicitly disable that sanitizer.

Final checkpoint results are recorded in the commit's test run and progress note.
API, browser, neural-model lifecycle and real REA/Ghidra validation follow later;
none is implied by the parser checkpoint.
