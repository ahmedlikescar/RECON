import time
from typing import Any

import numpy as np

from recon import ANALYZER_VERSION, FEATURE_SCHEMA
from recon.features.baselines import BaselineIndex
from recon.schemas import FunctionAnalysis


def rank_queries(
    queries: list[tuple[str, FunctionAnalysis]],
    targets: list[tuple[str, FunctionAnalysis]],
    index: BaselineIndex,
    method: str,
    top_k: int,
    threshold: float,
) -> dict[str, Any]:
    start = time.perf_counter()
    results = []
    for query_id, query in queries:
        scores, parts = index.scores(query, method)
        order = np.argsort(-scores, kind="stable")[:top_k]
        matches = []
        for rank, pos in enumerate(order, 1):
            target_id, target = targets[int(pos)]
            matches.append(
                {
                    "rank": rank,
                    "function_id": target_id,
                    "name": target.name,
                    "address": target.address,
                    "similarity_score": float(scores[pos]),
                    "accepted": bool(scores[pos] >= threshold),
                    "evidence": {key: float(value[pos]) for key, value in parts.items()},
                    "limitations": target.limitations,
                }
            )
        results.append(
            {
                "query_function_id": query_id,
                "name": query.name,
                "address": query.address,
                "state": "candidate" if matches and matches[0]["accepted"] else "unknown",
                "matches": matches,
            }
        )
    return {
        "method": method,
        "model_version": f"baseline-{method}-1",
        "feature_schema": FEATURE_SCHEMA,
        "analyzer_version": ANALYZER_VERSION,
        "threshold": threshold,
        "top_k": top_k,
        "candidate_count": len(targets),
        "query_count": len(queries),
        "results": results,
        "retrieval_seconds": time.perf_counter() - start,
        "limitations": [
            "Scores are similarity rankings, not probabilities or proof of equivalent behavior.",
            "The threshold is a user filter, not a calibrated guarantee. No match may exist in the candidate binary.",
            "Each query is ranked independently; this is not a one-to-one function assignment.",
        ],
    }
