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

Checkpoint 1 finished with **20 tests passed** in 2.16 seconds.

## 2026-10-25 application checkpoint

`pytest -q`: **35 passed** in 7.49 seconds. Includes API persistence, comparisons,
deletion/integrity, optional-provider fallback, hand-calculated metrics, genuine
contrastive gradients, safe model round-trip and checkpoint resume equivalence.

`pnpm --dir frontend test`: **3 passed**. `pnpm --dir frontend build`: TypeScript
and production build passed. `pnpm --dir frontend test:e2e`: **3 passed** in
6.6 seconds using Chromium. The browser actually loads the compiled fixtures,
opens assembly/CFG, compares, and downloads JSON. It also tests a rejected upload
and a 390px viewport. Screenshots in `docs/images/` come from this run.

`ruff check backend scripts tests`: passed. `mypy backend/recon`: passed across
33 source files. An earlier Playwright run selected the delete button because
the filename query was not anchored; the locator was corrected and the actual
flow then passed. The invalid-upload and narrow-layout tests passed in both runs.

The installed FastAPI/Starlette test client emits one deprecation warning for
its httpx compatibility layer. Tests pass; no warning is hidden.

## 2026-10-25 hardening checkpoint

Added streaming body-budget coverage, formula-safe CSV cells, analysis report export,
reanalysis invalidation, evidence cleanup, packaged model integrity, persisted neural
vectors and inference cache tests. The full backend suite passes after the changes;
the final run finished with **44 passed** in 7.00 seconds. See `PROGRESS.md` for
the end-of-day checkpoint.

A direct FAISS/PyTorch in-process test caused a native segmentation fault on this
macOS host (the first hardening run stopped after 16 tests). A dedicated run reproduced
it. FAISS now executes in a bounded independent interpreter; the focused regression
and full suite then passed. The local benchmark confirmed the isolated FAISS engine.

Browser tests also assert that the demo workflow makes no external HTTP requests.
All three browser tests and frontend type/unit/build checks passed again after
formatting. Current source files are checked by Prettier, Ruff and mypy.
