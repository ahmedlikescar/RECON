"""Isolate FAISS/OpenMP from the process that loads PyTorch."""

import resource
import sys
from pathlib import Path


def main() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (10, 11))
    resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1048576, 8 * 1048576))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if sys.platform == "linux":
        resource.setrlimit(resource.RLIMIT_AS, (1024 * 1048576, 1024 * 1048576))
    import faiss
    import numpy as np

    faiss.omp_set_num_threads(1)
    source, target, k = sys.argv[1:]
    arrays = np.load(source, allow_pickle=False)
    candidates, queries = arrays["candidates"], arrays["queries"]
    assert candidates.dtype == queries.dtype == np.float32
    assert candidates.ndim == queries.ndim == 2 and candidates.shape[1] == queries.shape[1] == 64
    assert 0 < len(candidates) <= 20000 and 0 < len(queries) <= 20000 and 1 <= int(k) <= 50
    index = faiss.IndexFlatIP(64)
    index.add(candidates)
    scores, order = index.search(queries, min(int(k), len(candidates)))
    np.savez(Path(target), scores=scores, order=order)


if __name__ == "__main__":
    main()
