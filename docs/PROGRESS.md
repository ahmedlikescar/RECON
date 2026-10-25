# Progress

2026-10-25: Read the complete engineering specification and master prompt. Confirmed
repository identity, write permission and existing README history. Inspected the
development host and official REA documentation before implementation.

## Checkpoint 1

Implemented constrained static ELF parsing, symbol/discovery provenance, Capstone
instructions, control-flow graphs, normalized features, baseline ranking and a
versioned persisted baseline index. Added two cross-compiled x86-64 ELF demo builds
from the same known C source; compiler output is never executed.

The parser/baseline checks pass Ruff and mypy. The static-analysis pytest suite
covers real extraction, branch/fallthrough edges, normalized operands, matching,
index compatibility, integrity, malformed input, traversal, instruction limits,
and cancellation. See `docs/TESTING.md` for observed results.

API/UI and research integration are still being built. This checkpoint is an
engine foundation, not a finished application. Follow `docs/PLAN.md` in order.

## Checkpoint 2

The working app now has the FastAPI service, Alembic schema, a persistent bounded
job queue, the React workspace/explorer/comparison UI, genuine side-by-side
assembly/CFG evidence, baseline indexes, unknown threshold, report export, cache
checks, cancellation and deletion. Core analysis works without weights or REA.

Added pinned-source dataset compilation, DWARF-verified source labels,
project-disjoint splits, duplicate/near-duplicate checks, a compact CPU Siamese
encoder, safe model/optimizer checkpoints and held-out evaluation. A real pilot
model was trained locally; it does not outperform the n-gram baseline on this
small test project. Research and model cards will document the practical limits.

Verified: 35 backend tests, 3 frontend unit tests, 3 Chromium end-to-end tests,
frontend type check/production build, backend Ruff and mypy. Browser tests load
real demo builds, inspect CFGs, compare, export, reject invalid input, and inspect
the narrow layout. Screenshot artifacts come from those browser runs.

The optional REA 6.8.0 CLI adapter uses inspected upstream contracts and has
normalization/fallback tests. No actual REA/Ghidra installation or end-to-end
provider investigation has run. Remaining hardening and traceability are tracked
in `KNOWN_ISSUES.md` and the final delivery notes.

## Checkpoint 3

Hardened streamed multipart limits without Content-Length, CSV formula escaping,
derived-evidence deletion, and reanalysis invalidation. Added cached inference,
persisted neural vectors bound to model/schema/candidate hashes, CPU-only Linux
PyTorch resolution, and bounded FAISS helper isolation with exact NumPy fallback.
The helper change fixes an observed native macOS crash in a regression test.

Added a genuine fixture/model benchmark, architecture and threat model, model/data
cards, evaluation protocol/results, upstream REA setup plan, and requirement coverage.
Unimplemented or externally unverified requirements are explicit in `TRACEABILITY.md`.
Pinned GitHub Actions workflows run backend checks on macOS/Linux, browser checks,
and a genuine GCC/Clang dataset build on Linux. CI is configured, not yet claimed passed.

Feature work stopped for the day at the owner's request. The GitHub README was
rewritten in a simpler student-project voice, with setup commands moved to
`SETUP.md`. Final local checks: 44 backend tests passed, 3 frontend unit tests
passed, and 3 browser tests passed. Ruff, mypy and the frontend build passed.
GitHub Actions execution has not yet been verified.
