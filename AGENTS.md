# Working on RECON

RECON is a local static binary analysis and function similarity application. Read
`docs/requirements/ENGINEERING_SPECIFICATION.txt` and `docs/PLAN.md` before changing scope.

- Never run or load an imported binary. Only the compiler may run when building our known source fixtures.
- Start with x86-64 ELF. Reject other targets explicitly; do not pretend analysis succeeded.
- Keep native analysis and baseline matching usable offline, without REA, trained weights, or API keys.
- Keep source labels, names, build settings, and debug data out of similarity features.
- Split research data by project before forming pairs. Never select models using the test split.
- Record real commands and measured results. Missing integrations and untested platforms stay marked as such.
- Use Python 3.12, LIEF, Capstone, NetworkX, FastAPI, SQLAlchemy/Alembic, React/TypeScript/Vite.
- Keep resource limits, strict input schemas, atomic artifacts, and provenance at module boundaries.
- Run Ruff, mypy, pytest, frontend type checks/unit tests/build, and Playwright for relevant changes.
- Update architecture, decisions, progress, testing, benchmarks, and known issues at milestones.
- Completed, verified work may be committed and pushed to `origin` under the user's standing instruction.

Current milestone: establish the first real static-analysis and baseline-comparison workflow, then
reproducible research and optional evidence providers. See `docs/PROGRESS.md` for verified status.
