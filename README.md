# recon, reverse engineering tool

we're building a local binary analysis and function similarity tool.

RECON inspects compiled programs without running them, compares functions
across different builds, and show the instructions and control flow behind each match.

the core app runs locally without paid AI APIs. the first working version includes
an explorer, side-by-side comparisons, a research pipeline, and an optional REA adapter.

![the RECON workspace](docs/images/workspace.png)

## run locally

Use Python 3.12, Node.js 22+ and pnpm 11. macOS and Linux are the development
targets; use WSL2 on Windows. Install [uv](https://docs.astral.sh/uv/getting-started/installation/)
and [pnpm](https://pnpm.io/installation) first if needed.

```sh
uv sync
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend build
uv run python scripts/demo.py
```

Open [the local app](http://127.0.0.1:8000), then click **Load demo**. The bundled
O0/O2 ELF files were compiled from `tests/fixtures/demo.c`; neither is executed.
Once dependencies are installed, the demo and core analysis work offline.

For neural inference and research, install the extra dependencies instead:

```sh
uv sync --extra research
uv run python scripts/demo.py
```

The demo installer picks up the genuinely trained pilot weights in `models/pilot/`
when PyTorch is available. Baselines work without them. The pilot is a small
research example, and its results are not a guarantee about other binaries.

## development in VS Code

Open this repository folder. `.vscode/` contains interpreter settings and tasks
for the local app, fixture builds, and backend tests. For frontend development:

```sh
uv run python scripts/demo.py --prepare-only
uv run recon serve
# in another terminal
pnpm --dir frontend dev
```

The development UI is at [localhost:5173](http://127.0.0.1:5173). Data stays under
`.recon/`, which is ignored by Git. The API binds to loopback and exposes its typed
contract at [the local API docs](http://127.0.0.1:8000/docs).

## tests and research

```sh
uv run pytest -q
uv run ruff check backend scripts tests
uv run mypy backend/recon
pnpm --dir frontend test
pnpm --dir frontend build
pnpm --dir frontend exec playwright install chromium
pnpm --dir frontend test:e2e

uv run --extra research recon dataset build
uv run --extra research recon dataset audit
uv run --extra research recon train --epochs 30 --seed 42
uv run --extra research recon evaluate
```

Dataset building downloads pinned, licensed C sources on first use and records
hashes, compiler versions, flags and source labels. Ordinary analysis never downloads
anything. On this Mac, dataset builds use Zig's x86-64 Linux cross compiler;
actual GCC/Clang cross-compiler results are not claimed.

See [the plan](docs/PLAN.md), [verified progress](docs/PROGRESS.md),
[test results](docs/TESTING.md), and [known limitations](docs/KNOWN_ISSUES.md).
REA is optional, disabled by default, and requires a separate approved setup.
