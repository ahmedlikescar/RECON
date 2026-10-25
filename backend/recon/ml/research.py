import json
import os
import platform
import random
import time
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from recon.config import Settings
from recon.errors import ReconError
from recon.features.baselines import BaselineIndex
from recon.ml.dataset import validate_dataset
from recon.ml.metrics import retrieval_metrics
from recon.ml.model import (
    embed,
    encoder,
    load_model,
    save_package,
    tensors,
    torch_module,
    vocabulary,
)
from recon.schemas import FunctionAnalysis
from recon.storage.artifacts import atomic_bytes, atomic_json, digest, read_json
from recon.storage.database import now


def contrastive_loss(embeddings: Any, labels: Any, temperature: float = 0.1) -> Any:
    torch = torch_module()
    logits = embeddings @ embeddings.T / temperature
    eye = torch.eye(len(labels), dtype=torch.bool)
    logits = logits.masked_fill(eye, -1e9)
    positives = labels[:, None].eq(labels[None, :]) & ~eye
    log_prob = logits - torch.logsumexp(logits, dim=1, keepdim=True)
    return -((log_prob * positives).sum(1) / positives.sum(1).clamp(min=1)).mean()


def evaluate(
    samples: list[dict[str, Any]],
    *,
    model_package: Path | None = None,
    split: str = "test",
    validation_only: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        if sample["split"] == split:
            groups[sample["build_id"]].append(sample)
    methods = ["opcode", "ngram", "structure", "hybrid"]
    model_data = load_model(model_package) if model_package else None
    if model_data:
        methods.append("neural")
    records: dict[str, list[dict[str, Any]]] = {m: [] for m in methods}
    embeddings = (
        {
            k: embed(
                model_data[0],
                model_data[1],
                [FunctionAnalysis.model_validate(s["function"]) for s in group],
            )
            for k, group in groups.items()
        }
        if model_data
        else {}
    )
    index_bytes = 0
    for target_id, targets in sorted(groups.items()):
        target_functions = [FunctionAnalysis.model_validate(s["function"]) for s in targets]
        baseline = BaselineIndex(target_functions)
        index_bytes += (
            baseline.opcode_vectors.nbytes
            + baseline.structures.nbytes
            + baseline.ngram_vectors.data.nbytes
        )
        for query_id, queries in sorted(groups.items()):
            if query_id == target_id or queries[0]["project"] != targets[0]["project"]:
                continue
            if validation_only and not (
                queries[0]["optimization"] == "O0" and targets[0]["optimization"] == "O2"
            ):
                continue
            target_labels = [s["lineage"] for s in targets]
            for pos, query in enumerate(queries):
                if query["lineage"] not in target_labels:
                    continue
                function = FunctionAnalysis.model_validate(query["function"])
                for method in methods:
                    tick = time.perf_counter()
                    if method == "neural":
                        scores = embeddings[query_id][pos] @ embeddings[target_id].T
                    else:
                        scores, _ = baseline.scores(function, method)
                    order = np.argsort(-scores, kind="stable")
                    records[method].append(
                        {
                            "ranking": [target_labels[int(i)] for i in order],
                            "label": query["lineage"],
                            "score": float(scores[order[0]]),
                            "seconds": time.perf_counter() - tick,
                            "project": query["project"],
                            "compiler_pair": query["compiler"] + "→" + targets[0]["compiler"],
                            "optimization_pair": query["optimization"]
                            + "→"
                            + targets[0]["optimization"],
                            "size": "small"
                            if len(function.instructions) < 30
                            else "medium"
                            if len(function.instructions) < 100
                            else "large",
                        }
                    )
    output = {}
    for method, rows in records.items():
        if not rows:
            raise ReconError("EVALUATION_EMPTY", f"No verified retrieval pairs in {split}.")
        metrics = retrieval_metrics(
            [r["ranking"] for r in rows], [r["label"] for r in rows], [r["score"] for r in rows]
        )
        subgroup: dict[str, Any] = {}
        for key in ["project", "compiler_pair", "optimization_pair", "size"]:
            subgroup[key] = {}
            for value in sorted({r[key] for r in rows}):
                subset = [r for r in rows if r[key] == value]
                subgroup[key][value] = retrieval_metrics(
                    [r["ranking"] for r in subset], [r["label"] for r in subset]
                )
        output[method] = {
            **metrics,
            "mean_ranking_ms": float(np.mean([r["seconds"] for r in rows])) * 1000,
            "subgroups": subgroup,
            "false_positive_examples": [
                {"query": r["label"], "candidate": r["ranking"][0], "score": r["score"]}
                for r in rows
                if r["ranking"][0] != r["label"]
            ][:10],
        }
    return {
        "split": split,
        "methods": output,
        "duration_seconds": time.perf_counter() - started,
        "baseline_vector_bytes": index_bytes,
        "model_version": model_data[2]["model_version"] if model_data else None,
        "limitations": [
            "Ranking timings exclude extraction, tokenization, and model loading. End-to-end timings are recorded separately.",
            "Repeated queries across build pairs are correlated. Query bootstrap intervals are not project-level uncertainty.",
            "Accepted-match precision uses a fixed uncalibrated 0.65 threshold. No-match detection on open-world distractors is not benchmarked.",
        ],
    }


def train(
    dataset: dict[str, Any],
    root: Path,
    epochs: int,
    seed: int,
    *,
    resume: bool = False,
    cancelled: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    validate_dataset(dataset)
    torch = torch_module()
    torch.set_num_threads(1)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    random.seed(seed)
    np.random.seed(seed)
    samples = [s for s in dataset["samples"] if s["split"] == "train"]
    functions = [FunctionAnalysis.model_validate(s["function"]) for s in samples]
    vocab = vocabulary(functions)
    model = encoder(len(vocab))
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.003, weight_decay=0.01)
    groups: dict[str, list[int]] = defaultdict(list)
    for i, sample in enumerate(samples):
        groups[sample["lineage"]].append(i)
    groups = {key: ids for key, ids in groups.items() if len(ids) >= 2}
    if len(groups) < 2:
        raise ReconError(
            "TRAINING_PAIRS",
            "At least two verified training lineages with multiple builds are required.",
        )
    tokens, statistics = tensors(functions, vocab)
    checkpoint = root / "models/checkpoint"
    best = root / "models/best-training"
    history: list[dict[str, Any]] = []
    best_mrr, start_epoch = -1.0, 0
    started = time.perf_counter()
    if resume:
        model, loaded_vocab, manifest = load_model(checkpoint)
        if (
            manifest.get("dataset_hash") != dataset["dataset_hash"]
            or loaded_vocab != vocab
            or manifest.get("seed") != seed
        ):
            raise ReconError(
                "CHECKPOINT_INCOMPATIBLE",
                "Resume requires the same dataset, tokenizer and seed.",
                409,
            )
        optimizer = torch.optim.AdamW(model.parameters(), lr=0.003, weight_decay=0.01)
        state = read_json(checkpoint / "optimizer.json", manifest["optimizer_metadata_sha256"])
        raw = (checkpoint / "optimizer.safetensors").read_bytes()
        if digest(raw) != manifest["optimizer_sha256"]:
            raise ReconError(
                "CHECKPOINT_INTEGRITY", "Optimizer checkpoint failed its hash check.", 409
            )
        from safetensors.torch import load

        loaded = load(raw)
        optimizer.load_state_dict(
            {
                "param_groups": state["param_groups"],
                "state": {
                    int(key): {name: loaded[f"{key}.{name}"] for name in names}
                    for key, names in state["state"].items()
                },
            }
        )
        history, start_epoch, best_mrr = (
            manifest["history"],
            manifest["epoch"],
            manifest["best_validation_mrr"],
        )
    base = {
        "dataset_hash": dataset["dataset_hash"],
        "seed": seed,
        "training_projects": sorted({s["project"] for s in samples}),
        "architecture": "64-dim token embedding → masked mean + log-CFG statistics → 96 → 64 normalized embedding",
        "loss": "supervised contrastive InfoNCE",
        "temperature": 0.1,
        "optimizer": "AdamW",
        "learning_rate": 0.003,
        "hardware": platform.processor() or platform.machine(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "cpu_threads": 1,
        "training_samples": len(samples),
        "training_lineages": len(groups),
        "nondeterminism": "CPU deterministic algorithms requested; cross-platform floating point can differ.",
    }
    for epoch in range(start_epoch, epochs):
        if cancelled and cancelled():
            raise ReconError(
                "CANCELLED", "Training cancelled. Compatible checkpoint is retained.", 409
            )
        torch.manual_seed(seed + epoch)
        rng = random.Random(seed + epoch)
        keys = sorted(groups)
        rng.shuffle(keys)
        losses, gradients = [], []
        model.train()
        for offset in range(0, len(keys), 16):
            batch = keys[offset : offset + 16]
            if len(batch) < 2:
                continue
            positions = [pos for key in batch for pos in rng.sample(groups[key], 2)]
            labels = torch.tensor([i for i in range(len(batch)) for _ in range(2)])
            optimizer.zero_grad()
            loss = contrastive_loss(model(tokens[positions], statistics[positions]), labels)
            loss.backward()
            gradient = float(torch.nn.utils.clip_grad_norm_(model.parameters(), 5))
            if not np.isfinite(float(loss.detach())) or not np.isfinite(gradient):
                raise ReconError(
                    "TRAINING_DIVERGED", "Training produced nonfinite loss or gradients."
                )
            optimizer.step()
            losses.append(float(loss.detach()))
            gradients.append(gradient)
        metadata = {**base, "epoch": epoch + 1, "history": history, "best_validation_mrr": best_mrr}
        save_package(checkpoint, model, vocab, metadata)
        validation = evaluate(
            dataset["samples"], model_package=checkpoint, split="validation", validation_only=True
        )
        val_mrr = validation["methods"]["neural"]["mrr"]
        history.append(
            {
                "epoch": epoch + 1,
                "loss": float(np.mean(losses)),
                "gradient_norm": float(np.mean(gradients)),
                "validation_mrr": val_mrr,
            }
        )
        if val_mrr > best_mrr:
            best_mrr = val_mrr
            save_package(
                best,
                model,
                vocab,
                {**base, "epoch": epoch + 1, "validation_mrr": val_mrr, "history": history},
            )
        # Safe optimizer persistence: only tensors plus JSON, never pickle.
        state = optimizer.state_dict()
        from safetensors.torch import save

        raw = save(
            {
                f"{key}.{name}": value.contiguous()
                for key, values in state["state"].items()
                for name, value in values.items()
            }
        )
        checkpoint.mkdir(parents=True, exist_ok=True)
        atomic_bytes(checkpoint / "optimizer.safetensors", raw)
        state_json = {
            "param_groups": state["param_groups"],
            "state": {str(key): list(values) for key, values in state["state"].items()},
        }
        optimizer_meta_hash = atomic_json(checkpoint / "optimizer.json", state_json)
        save_package(
            checkpoint,
            model,
            vocab,
            {
                **base,
                "epoch": epoch + 1,
                "history": history,
                "best_validation_mrr": best_mrr,
                "optimizer_sha256": digest(raw),
                "optimizer_metadata_sha256": optimizer_meta_hash,
            },
        )
        print(json.dumps(history[-1]), flush=True)
        best_epoch = max(history, key=lambda r: r["validation_mrr"])["epoch"]
        if epoch + 1 - best_epoch >= 8:
            break
    best_model, _, best_manifest = load_model(best)
    run_dir = root / "models/runs" / (now().replace(":", "-") + f"-{seed}")
    save_package(
        run_dir,
        best_model,
        vocab,
        {
            **best_manifest,
            "history": history,
            "training_duration_seconds": time.perf_counter() - started,
        },
    )
    root.joinpath("models").mkdir(parents=True, exist_ok=True)
    link = root / "models/.current-next"
    link.unlink(missing_ok=True)
    link.symlink_to(run_dir.relative_to(root / "models"), target_is_directory=True)
    os.replace(link, root / "models/current")
    return {
        **base,
        "history": history,
        "best_validation_mrr": best_mrr,
        "selected_epoch": best_manifest["epoch"],
        "model_version": best_manifest["model_version"],
        "duration_seconds": time.perf_counter() - started,
        "test_set_used_for_selection": False,
    }


def run_experiment(
    task: dict[str, Any], settings: Settings, cancelled: Callable[[], bool]
) -> tuple[str, str]:
    dataset = read_json(settings.root / "research/dataset.json")
    audit = validate_dataset(dataset)
    if task["kind"] == "train":
        config = task["config_json"]
        result = train(
            dataset,
            settings.root,
            config["epochs"],
            config["seed"],
            resume=config["resume"],
            cancelled=cancelled,
        )
    else:
        path = settings.root / "models/current"
        if path.exists():
            _, _, manifest = load_model(path)
            if manifest["dataset_hash"] != dataset["dataset_hash"]:
                raise ReconError(
                    "MODEL_DATASET_MISMATCH",
                    "The trained model belongs to another dataset. Evaluate against its original frozen dataset.",
                    409,
                )
        result = evaluate(dataset["samples"], model_package=path if path.exists() else None)
    result.update(
        {
            "dataset_hash": dataset["dataset_hash"],
            "audit": audit,
            "created_at": now(),
            "dataset_environment": dataset["environment"],
            "missing_toolchains": dataset["missing_toolchains"],
            "dataset_limitations": dataset["limitations"],
        }
    )
    artifact = f"experiments/{task['resource_id']}.json"
    sha = atomic_json(settings.root / artifact, result)
    return artifact, sha
