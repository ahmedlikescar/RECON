# Implementation plan

The Word specification and master prompt are preserved in `docs/requirements/`.
Their final milestone list (section 26) sets delivery order. Earlier requirement
IDs remain applicable. A feature is complete only after its exit checks run.

## Starting point and assumptions

The repository initially contains a README. The development host is macOS on
Apple Silicon, with bundled Python 3.12 and Node 24, and Apple Clang 17. Native
GCC, Ghidra, and REA have not been found. The application targets little-endian
x86-64 ELF executables/shared objects first. Known C fixtures will be cross-compiled
without running the output. A NumPy exact index is allowed for the initial scale.
No external AI provider will be enabled or configured automatically.

## Repository layout

```text
backend/recon/
  api/          typed HTTP routes and local application lifecycle
  analysis/     static extraction and provider contracts
  cfg/          basic blocks and directed graph evidence
  features/     versioned normalization and baseline features
  ml/           dataset checks, CPU encoder, training and evaluation
  indexing/     compatible, persisted nearest-neighbor search
  storage/      database schema, migrations, atomic artifacts and jobs
  security/     validation and constrained parser process
frontend/src/   import, explorer, comparisons, research and integrations
scripts/        development, trusted fixture compilation and research commands
tests/          unit, integration and safe C fixtures
docs/           requirements, decisions, validation and limitations
experiments/    reproducible configs and measured reports
datasets/       source manifests; generated data stays local
models/         model documentation; local checkpoints stay local
```

## Ordered work

1. **Native analysis:** package/lock dependencies, threat model, constrained worker,
   ELF admission, LIEF metadata/symbol boundaries, Capstone disassembly, CFG,
   SQLite/migrations, persisted jobs, and health/capabilities. Validate real fixtures
   plus malformed, oversized, unsupported, and boundary cases.
2. **Baseline product slice:** normalized opcode/n-gram/CFG features, versioned exact
   retrieval, asynchronous comparisons, React explorer with side-by-side evidence,
   offline demo, JSON/CSV exports, cancellation, caching, and deletion. Validate the
   upload-to-comparison workflow in the browser.
3. **Ground truth:** pinned source manifests, compiler matrix, explicit function
   lineage, quarantine ambiguous labels, project-disjoint splits and duplicate checks.
4. **Neural research:** shared-weight CPU encoder, contrastive training, validation
   checkpoint selection, safe resumable artifacts and held-out retrieval evaluation.
   Record actual results against all baselines, including underperformance.
5. **Product inference:** compatible model registry/index, unknown threshold,
   optional Research Mode and persisted experiments, without retraining in Analysis Mode.
6. **Optional providers:** inspect official REA source/version/license before coding
   its adapter; add capabilities, diagnostics, version pin, explicit opt-in,
   normalized provenance, deadlines, and native fallback. A real Ghidra/REA run
   requires the optional installation and configuration to be available and approved.
7. **Delivery checks:** lint/types/tests/browser, offline and security checks,
   traceability, hardware/runtime records, clean-checkout instructions and known issues.

## Architecture

The browser talks only to a loopback FastAPI service. Upload validation and
content hashes precede persistence. A single bounded queue dispatches static
parsing to a separate constrained process; the imported path is never executable
command input. SQLite owns job state, functions, comparisons and provenance.
Artifacts and indexes are replaced atomically. Similarity uses extracted machine
instructions and graph structure, with no source names or source labels as inputs.
Optional evidence providers never alter ML scores. Model artifacts declare their
feature schema, dataset identity and hashes, and mismatches fail closed.
