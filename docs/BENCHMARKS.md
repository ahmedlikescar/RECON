# Measured local pilot

These measurements describe tiny known fixtures on one machine. They are not
runtime promises for arbitrary uploaded binaries. Full raw records are committed
in `experiments/native-benchmark.json`, `pilot-training.json`, and `pilot-evaluation.json`.

Host: macOS 27.0.1, arm64 Apple Silicon, Python 3.12.14. Training uses PyTorch
2.14.1 on CPU with one thread. Demo compiler: Zig 0.15.2's Linux x86-64 Clang.
The bundled ELF files are 4,664 and 6,416 bytes, with nine functions each.

| Measured operation | Observed time |
|---|---:|
| Two isolated parser runs, mean of three | 0.924 s |
| Native extraction inside those workers | 0.0075–0.0234 s total |
| Baseline candidate-index build | 0.00753 s |
| Combined baseline ranking, all nine queries | 0.00336 s |
| Pilot model cold load in benchmark process | 0.880 s |
| Neural embeddings, helper startup and FAISS search | 0.153 s |
| Dataset build from locally cached pinned sources, 16 builds | 8.069 s |
| CPU training, 19 epochs with early stopping | 2.280 s |
| Held-out evaluation of all five methods | 0.321 s |

Peak benchmark process RSS was 278,036,480 bytes. It includes the interpreter,
LIEF, sklearn, PyTorch and allocated tensors, rather than just index memory.
Child-process peak RSS and a large-corpus memory profile were not measured.
Ranking microtimings in the evaluation report exclude extraction, tokenization,
loading and index building, so they must not be presented as application latency.

FAISS was observed to crash when imported/searched directly in the same process
as PyTorch in this macOS environment. It now runs in a bounded fresh interpreter
with one OpenMP thread; the API/PyTorch process survives helper failure and uses
exact batched NumPy search. The measured benchmark reports
`faiss-exact-inner-product-isolated`. Regression tests verify persistent vector
indexes and compatibility rejection.

Reproduce after installing dependencies:

```sh
python scripts/benchmark.py
recon dataset build --offline
recon train --epochs 30 --seed 42
recon evaluate
```

Use a fresh data directory for an independent experiment. The training and
evaluation JSON includes seed, dataset hash, model version and environment.
No test-set hyperparameter search or cross-compiler result is claimed here.
