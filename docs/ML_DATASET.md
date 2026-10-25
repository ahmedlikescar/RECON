# Dataset card

This is a small research pilot, built from four pinned permissively licensed C
projects. Exact revisions, file hashes and license paths are in
`datasets/manifests/sources.json`. Builds and analyses stay in `.recon/research/`.

| Split | Project | License | Function lineages | Samples |
|---|---|---|---:|---:|
| Train | rxi/vec and rxi/map | MIT | 20 | 80 |
| Validation | kokke/tiny-AES-c | Unlicense | 20 | 80 |
| Test | rxi/ini | MIT | 10 | 40 |

The observed host run has 16 builds, four optimization levels O0/O1/O2/O3, 50
verified function lineages and 200 samples. It uses Zig 0.15.2's Clang Linux x86-64
cross compiler. No compiled output was executed. GCC was not available here, so
this run is cross-optimization, not cross-compiler evidence.

DWARF source-file/name/line metadata and entry addresses must agree with LIEF's
function symbol. Missing, tiny, merged/ambiguous or unverified entries are quarantined.
Compiler flags disable inlining to make source lineage auditable. Ground-truth
symbols/debug data are excluded from feature generation and model inputs.

Projects are assigned splits in the source manifest before pair creation. The
builder/auditor checks project, lineage and normalized source hash separation, and
quarantines cross-split identifier-normalized 5-token shingles with Jaccard similarity
at least 0.90. These heuristics cannot prove semantic deduplication.

Rebuild with `recon dataset build`; use `--offline` after source acquisition. Every
download is pinned to a source commit and SHA-256. Build logs, compiler versions,
flags, binary hashes, labels, quarantines and split audit are saved. Runtime/hardware
are recorded separately from content identity. Machine/toolchain changes can still
produce different compiled artifacts; the manifest makes that visible.

This corpus has only one validation and one test project, repeated related queries,
no LTO/inlining stress suite and no representative stripped/packed binaries. Several
projects share an author. It cannot establish broad binary-similarity performance.
