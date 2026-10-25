from typing import Any

import numpy as np


def retrieval_metrics(
    rankings: list[list[str]],
    labels: list[str],
    scores: list[float] | None = None,
    threshold: float = 0.65,
) -> dict[str, Any]:
    if len(rankings) != len(labels) or not labels:
        raise ValueError("Rankings and nonempty labels must have the same length")
    ranks = [
        candidates.index(label) + 1 if label in candidates else float("inf")
        for candidates, label in zip(rankings, labels, strict=True)
    ]
    result: dict[str, Any] = {
        f"recall_at_{k}": sum(rank <= k for rank in ranks) / len(ranks) for k in [1, 5, 10]
    }
    result.update({"mrr": sum(1 / rank for rank in ranks) / len(ranks), "queries": len(labels)})
    if scores is not None:
        accepted = [i for i, score in enumerate(scores) if score >= threshold]
        correct = sum(ranks[i] == 1 for i in accepted)
        result.update(
            {
                "threshold": threshold,
                "accepted": len(accepted),
                "false_matches": len(accepted) - correct,
                "precision_accepted": correct / len(accepted) if accepted else None,
                "coverage": len(accepted) / len(ranks),
            }
        )
    # Query bootstrap, not a project-level generalization confidence interval.
    rng = np.random.default_rng(42)
    hits = np.asarray([rank == 1 for rank in ranks], dtype=float)
    resamples = [float(rng.choice(hits, size=len(hits), replace=True).mean()) for _ in range(300)]
    result["recall_at_1_query_bootstrap_95ci"] = [
        float(np.quantile(resamples, q)) for q in [0.025, 0.975]
    ]
    return result
