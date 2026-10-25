import importlib.util
import io
import json
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from recon import FEATURE_SCHEMA
from recon.errors import ReconError
from recon.features.baselines import structure
from recon.schemas import FunctionAnalysis
from recon.storage.artifacts import atomic_bytes, atomic_json, digest, read_json

MODEL_SCHEMA = "siamese-mean-cfg-1"
MAX_TOKENS = 256


def torch_module() -> Any:
    try:
        import torch

        return torch
    except ImportError as exc:
        raise ReconError(
            "RESEARCH_DEPENDENCIES",
            "Install research dependencies: uv sync --extra research. Baseline analysis remains available.",
            409,
        ) from exc


def encoder(vocabulary_size: int) -> Any:
    torch = torch_module()
    nn = torch.nn

    if TYPE_CHECKING:
        from torch.nn import Module as ModuleBase
    else:
        ModuleBase = nn.Module

    class Encoder(ModuleBase):
        def __init__(self) -> None:
            super().__init__()
            self.embedding = nn.Embedding(vocabulary_size, 64, padding_idx=0)
            self.projection = nn.Sequential(nn.Linear(69, 96), nn.GELU(), nn.Linear(96, 64))

        def forward(self, tokens: Any, statistics: Any) -> Any:
            mask = (tokens != 0).unsqueeze(-1)
            mean = (self.embedding(tokens) * mask).sum(1) / mask.sum(1).clamp(min=1)
            return torch.nn.functional.normalize(
                self.projection(torch.cat([mean, statistics], dim=1)), dim=1
            )

    if not 2 <= vocabulary_size <= 16384:
        raise ReconError("MODEL_VOCABULARY", "Model vocabulary exceeds the supported budget.")
    return Encoder()


def vocabulary(functions: list[FunctionAnalysis]) -> dict[str, int]:
    from collections import Counter

    counts = Counter(i.token for f in functions for i in f.instructions)
    words = [word for word, _ in sorted(counts.items(), key=lambda p: (-p[1], p[0]))[:8190]]
    return {"<PAD>": 0, "<UNK>": 1, **{word: i + 2 for i, word in enumerate(words)}}


def tensors(functions: list[FunctionAnalysis], vocab: dict[str, int]) -> tuple[Any, Any]:
    torch = torch_module()
    ids = [[vocab.get(i.token, 1) for i in f.instructions[:MAX_TOKENS]] for f in functions]
    tokens = torch.zeros((len(functions), MAX_TOKENS), dtype=torch.long)
    for pos, values in enumerate(ids):
        tokens[pos, : len(values)] = torch.tensor(values, dtype=torch.long)
    stats = (
        torch.tensor(np.log1p(np.asarray([structure(f) for f in functions], dtype=np.float32))) / 5
    )
    return tokens, stats


def save_package(path: Path, model: Any, vocab: dict[str, int], metadata: dict[str, Any]) -> None:
    from safetensors.torch import save

    path.mkdir(parents=True, exist_ok=True)
    weights = save({k: v.detach().cpu().contiguous() for k, v in model.state_dict().items()})
    vocab_raw = json.dumps(vocab, sort_keys=True).encode()
    atomic_bytes(path / "weights.safetensors", weights)
    atomic_bytes(path / "vocabulary.json", vocab_raw)
    manifest = {
        **metadata,
        "model_schema": MODEL_SCHEMA,
        "feature_schema": FEATURE_SCHEMA,
        "max_tokens": MAX_TOKENS,
        "embedding_dim": 64,
        "vocabulary_size": len(vocab),
        "weights_sha256": digest(weights),
        "vocabulary_sha256": digest(vocab_raw),
    }
    manifest["model_version"] = "siamese-" + digest(weights)[:12]
    atomic_json(path / "manifest.json", manifest)


def load_model(path: Path) -> tuple[Any, dict[str, int], dict[str, Any]]:
    if not (path / "manifest.json").is_file():
        raise ReconError(
            "MODEL_UNAVAILABLE",
            "No trained model is installed. Use a baseline method, or train a model in Research Mode.",
            409,
        )
    manifest = read_json(path / "manifest.json")
    if (
        manifest.get("model_schema") != MODEL_SCHEMA
        or manifest.get("feature_schema") != FEATURE_SCHEMA
        or manifest.get("max_tokens") != MAX_TOKENS
    ):
        raise ReconError(
            "MODEL_INCOMPATIBLE", "Model architecture or feature schema is incompatible.", 409
        )
    if (path / "weights.safetensors").stat().st_size > 32 * 1048576:
        raise ReconError("MODEL_LIMIT", "Model weights exceed the supported size budget.", 409)
    raw = (path / "weights.safetensors").read_bytes()
    if digest(raw) != manifest["weights_sha256"]:
        raise ReconError("MODEL_INTEGRITY", "Model weights failed their integrity check.", 409)
    vocab = read_json(path / "vocabulary.json", manifest["vocabulary_sha256"])
    if (
        len(vocab) != manifest["vocabulary_size"]
        or set(vocab.values()) != set(range(len(vocab)))
        or vocab.get("<PAD>") != 0
        or vocab.get("<UNK>") != 1
    ):
        raise ReconError(
            "MODEL_VOCABULARY", "Tokenizer does not match the supported vocabulary format.", 409
        )
    from safetensors.torch import load

    model = encoder(len(vocab))
    try:
        model.load_state_dict(load(raw), strict=True)
    except Exception as exc:
        raise ReconError(
            "MODEL_INCOMPATIBLE",
            "Model tensor shapes or keys do not match the declared architecture.",
            409,
        ) from exc
    model.eval()
    return model, vocab, manifest


def model_status(path: Path) -> dict[str, Any]:
    if not (path / "manifest.json").exists():
        return {
            "available": False,
            "reason": "No trained weights installed. Baseline methods are ready.",
        }
    try:
        manifest = read_json(path / "manifest.json")
        if (
            manifest.get("model_schema") != MODEL_SCHEMA
            or manifest.get("feature_schema") != FEATURE_SCHEMA
        ):
            return {"available": False, "reason": "Installed weights use an incompatible schema."}
        if (
            digest((path / "weights.safetensors").read_bytes()) != manifest["weights_sha256"]
            or digest((path / "vocabulary.json").read_bytes()) != manifest["vocabulary_sha256"]
        ):
            return {
                "available": False,
                "reason": "Installed model artifacts failed their integrity checks.",
            }
        available = importlib.util.find_spec("torch") is not None
        return {
            "available": available,
            "model_version": manifest["model_version"],
            "dataset_hash": manifest["dataset_hash"],
            "validation_mrr": manifest.get("validation_mrr"),
            "reason": "Locally trained pilot model."
            if available
            else "Research dependencies are missing.",
        }
    except Exception:
        return {"available": False, "reason": "Installed model manifest is unreadable."}


def embed(model: Any, vocab: dict[str, int], functions: list[FunctionAnalysis]) -> np.ndarray:
    torch = torch_module()
    outputs = []
    with torch.inference_mode():
        for offset in range(0, len(functions), 64):
            tokens, stats = tensors(functions[offset : offset + 64], vocab)
            outputs.append(model(tokens, stats).cpu().numpy())
    return np.concatenate(outputs)


@lru_cache(maxsize=2)
def _inference_model(path: str, manifest_hash: str) -> tuple[Any, dict[str, int], dict[str, Any]]:
    return load_model(Path(path))


def inference_model(path: Path) -> tuple[Any, dict[str, int], dict[str, Any]]:
    if not (path / "manifest.json").is_file():
        return load_model(path)
    raw = (path / "manifest.json").read_bytes()
    manifest = json.loads(raw)
    for filename, key in [
        ("weights.safetensors", "weights_sha256"),
        ("vocabulary.json", "vocabulary_sha256"),
    ]:
        if digest((path / filename).read_bytes()) != manifest[key]:
            raise ReconError(
                "MODEL_INTEGRITY",
                "Model artifacts changed after loading. Install a verified package.",
                409,
            )
    return _inference_model(str(path.resolve()), digest(raw))


def neural_rank(
    queries: list[tuple[str, FunctionAnalysis]],
    targets: list[tuple[str, FunctionAnalysis]],
    path: Path,
    top_k: int,
    threshold: float,
    index_path: Path | None = None,
) -> dict[str, Any]:
    import time

    start = time.perf_counter()
    model, vocab, metadata = inference_model(path)
    expected = {
        "feature_schema": FEATURE_SCHEMA,
        "model_version": metadata["model_version"],
        "function_ids": [i for i, _ in targets],
        "function_hashes": [f.bytes_hash for _, f in targets],
    }
    if index_path and index_path.is_file():
        index_manifest = read_json(index_path.with_suffix(".json"))
        if any(index_manifest.get(key) != value for key, value in expected.items()):
            raise ReconError(
                "INDEX_INCOMPATIBLE",
                "Neural index belongs to different functions, feature schema, or model. Rebuild it.",
                409,
            )
        raw_vectors = index_path.read_bytes()
        if digest(raw_vectors) != index_manifest["vectors_sha256"]:
            raise ReconError(
                "INDEX_INTEGRITY", "Neural index vectors failed their integrity check.", 409
            )
        target_vectors = np.load(io.BytesIO(raw_vectors), allow_pickle=False)
        if target_vectors.shape != (len(targets), 64) or not np.isfinite(target_vectors).all():
            raise ReconError("INDEX_INCOMPATIBLE", "Neural index shape or values are invalid.", 409)
    else:
        target_vectors = embed(model, vocab, [f for _, f in targets]).astype("float32")
        if index_path:
            output = io.BytesIO()
            np.save(output, target_vectors, allow_pickle=False)
            raw_vectors = output.getvalue()
            atomic_bytes(index_path, raw_vectors)
            atomic_json(
                index_path.with_suffix(".json"), {**expected, "vectors_sha256": digest(raw_vectors)}
            )
    query_vectors = embed(model, vocab, [f for _, f in queries]).astype("float32")
    from recon.indexing.search import exact_search

    similarities, order, engine = exact_search(query_vectors, target_vectors, top_k)
    results = []
    for pos, (query_id, query) in enumerate(queries):
        matches = []
        for rank, (target_pos, score) in enumerate(
            zip(order[pos], similarities[pos], strict=True), 1
        ):
            target_id, target = targets[int(target_pos)]
            # Raw cosine, not a probability. Negative scores are retained.
            matches.append(
                {
                    "rank": rank,
                    "function_id": target_id,
                    "name": target.name,
                    "address": target.address,
                    "similarity_score": float(score),
                    "accepted": bool(score >= threshold),
                    "evidence": {"embedding_cosine": float(score)},
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
        "method": "neural",
        "model_version": metadata["model_version"],
        "feature_schema": FEATURE_SCHEMA,
        "index_engine": engine,
        "threshold": threshold,
        "top_k": top_k,
        "candidate_count": len(targets),
        "query_count": len(queries),
        "results": results,
        "retrieval_seconds": time.perf_counter() - start,
        "limitations": [
            "Cosine similarity is a ranking score, not a probability or proof of equivalent behavior.",
            "Pilot model trained on a small corpus. Results may underperform simple baselines.",
            "Functions are truncated to 256 normalized instruction tokens for this model.",
        ],
    }
