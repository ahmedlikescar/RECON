import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np


def exact_search(
    queries: np.ndarray, candidates: np.ndarray, top_k: int
) -> tuple[np.ndarray, np.ndarray, str]:
    if importlib.util.find_spec("faiss"):
        # Separate native runtimes: a FAISS crash must never terminate the API/PyTorch process.
        with tempfile.TemporaryDirectory(prefix="recon-faiss-") as folder:
            source, target = Path(folder) / "input.npz", Path(folder) / "output.npz"
            np.savez(
                source, candidates=candidates.astype("float32"), queries=queries.astype("float32")
            )
            env = {
                k: v for k, v in os.environ.items() if k in {"HOME", "PATH", "VIRTUAL_ENV", "LANG"}
            }
            env.update(
                {
                    "OMP_NUM_THREADS": "1",
                    "OPENBLAS_NUM_THREADS": "1",
                    "PYTHONDONTWRITEBYTECODE": "1",
                }
            )
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "recon.indexing.faiss_worker",
                        str(source),
                        str(target),
                        str(top_k),
                    ],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=12,
                    check=False,
                )
                if (
                    result.returncode == 0
                    and target.is_file()
                    and target.stat().st_size <= 8 * 1048576
                ):
                    arrays = np.load(target, allow_pickle=False)
                    scores, order = arrays["scores"], arrays["order"]
                    shape = (len(queries), min(top_k, len(candidates)))
                    if (
                        scores.shape == order.shape == shape
                        and np.isfinite(scores).all()
                        and ((order >= 0) & (order < len(candidates))).all()
                    ):
                        return scores, order, "faiss-exact-inner-product-isolated"
            except (subprocess.TimeoutExpired, OSError, ValueError):
                pass
    # Bound transient matrices for the same exact search when FAISS is missing or fails.
    all_scores, all_order = [], []
    for offset in range(0, len(queries), 128):
        matrix = queries[offset : offset + 128] @ candidates.T
        order = np.argsort(-matrix, axis=1, kind="stable")[:, :top_k]
        all_scores.append(np.take_along_axis(matrix, order, axis=1))
        all_order.append(order)
    return np.concatenate(all_scores), np.concatenate(all_order), "numpy-exact-inner-product"
