"""Small measured local benchmark, using only the known bundled fixtures."""

import json
import platform
import resource
import statistics
import sys
import time

from recon.config import REPO_ROOT, Settings
from recon.features.baselines import BaselineIndex
from recon.ml.model import inference_model, neural_rank
from recon.security.process import run_analysis
from recon.storage.artifacts import atomic_json


def main() -> None:
    settings = Settings()
    fixture_root = REPO_ROOT / "tests/fixtures/compiled"
    wall, extraction = [], []
    for _ in range(3):
        start = time.perf_counter()
        a = run_analysis(fixture_root / "demo-O0.elf", settings)
        b = run_analysis(fixture_root / "demo-O2.elf", settings)
        wall.append(time.perf_counter() - start)
        extraction.append(a.duration_seconds + b.duration_seconds)
    start = time.perf_counter()
    index = BaselineIndex(b.functions)
    features = time.perf_counter() - start
    start = time.perf_counter()
    for function in a.functions:
        index.scores(function, "hybrid")
    ranking = time.perf_counter() - start
    package = REPO_ROOT / "models/pilot"
    start = time.perf_counter()
    _, _, metadata = inference_model(package)
    loading = time.perf_counter() - start
    neural = neural_rank(
        [(str(i), f) for i, f in enumerate(a.functions)],
        [(str(i), f) for i, f in enumerate(b.functions)],
        package,
        5,
        0.65,
    )
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        rss *= 1024
    report = {
        "date": "2026-10-25",
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "model_version": metadata["model_version"],
        "fixtures": [
            {"name": f"demo-{opt}.elf", "bytes": (fixture_root / f"demo-{opt}.elf").stat().st_size}
            for opt in ["O0", "O2"]
        ],
        "functions_per_binary": [len(a.functions), len(b.functions)],
        "replicates": 3,
        "two_binary_parser_wall_seconds": wall,
        "native_extraction_seconds": extraction,
        "mean_parser_wall_seconds": statistics.mean(wall),
        "baseline_index_build_seconds": features,
        "baseline_all_query_ranking_seconds": ranking,
        "model_cold_load_seconds": loading,
        "neural_inference_index_and_search_seconds": neural["retrieval_seconds"],
        "neural_index_engine": neural["index_engine"],
        "process_peak_rss_bytes": rss,
        "scope": "Tiny known fixtures; cold worker startup included in wall time; process RSS includes Python, LIEF, sklearn and PyTorch. No target executed. Not a production-scale benchmark.",
    }
    target = REPO_ROOT / "experiments/native-benchmark.json"
    atomic_json(target, report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
