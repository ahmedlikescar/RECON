import copy
from pathlib import Path

import numpy as np
import pytest
from recon import FEATURE_SCHEMA
from recon.analysis.native import analyze_file
from recon.config import REPO_ROOT, Settings
from recon.errors import ReconError
from recon.ml.dataset import dataset_hash, near_duplicate_lineages, validate_dataset
from recon.ml.metrics import retrieval_metrics
from recon.ml.model import (
    embed,
    encoder,
    inference_model,
    load_model,
    neural_rank,
    save_package,
    tensors,
    vocabulary,
)
from recon.ml.research import contrastive_loss, train
from recon.storage.artifacts import read_json

torch = pytest.importorskip("torch")


def test_bundled_pilot_integrity():
    model, vocab, manifest = load_model(REPO_ROOT / "models/pilot")
    assert manifest["model_version"] == "siamese-39d0c5aca865"
    assert len(vocab) > 2


def test_metrics_against_hand_calculated_rankings():
    result = retrieval_metrics(
        [["a", "b", "c"], ["a", "c", "b"], ["b", "c", "a"]], ["a", "b", "missing"], [0.9, 0.8, 0.1]
    )
    assert result["recall_at_1"] == pytest.approx(1 / 3)
    assert result["recall_at_5"] == pytest.approx(2 / 3)
    assert result["mrr"] == pytest.approx((1 + 1 / 3) / 3)
    assert result["precision_accepted"] == 0.5
    assert result["false_matches"] == 1


def tiny_dataset(fixtures: Path) -> dict:
    # Independent artificial split identities are for lifecycle tests only, never a benchmark.
    analysis = analyze_file(fixtures / "demo-O0.elf", Settings())
    functions = analysis.functions[:6]
    samples = []
    for pos, function in enumerate(functions):
        split = ["train", "train", "validation", "validation", "test", "test"][pos]
        for optimization in ["O0", "O2"]:
            samples.append(
                {
                    "project": split,
                    "split": split,
                    "lineage": f"fixture-{pos}",
                    "source_function_hash": f"hash-{pos}",
                    "source_shingles": [f"fixture-{pos}-shingle"],
                    "build_id": f"{split}-{optimization}",
                    "compiler": "test-fixture",
                    "optimization": optimization,
                    "function": function.model_dump(),
                }
            )
    dataset = {"feature_schema": FEATURE_SCHEMA, "samples": samples}
    dataset["dataset_hash"] = dataset_hash(dataset)
    return dataset


def test_project_lineage_and_duplicate_checks(fixtures):
    data = tiny_dataset(fixtures)
    assert validate_dataset(data)["project_disjoint"]
    bad = copy.deepcopy(data)
    bad["samples"][0]["split"] = "test"
    with pytest.raises(ReconError, match="crosses"):
        validate_dataset(bad)
    bad = copy.deepcopy(data)
    bad["samples"][0]["function"]["name"] = "changed"
    with pytest.raises(ReconError, match="hash"):
        validate_dataset(bad)
    a, b = copy.deepcopy(data["samples"][0]), copy.deepcopy(data["samples"][-1])
    b["source_shingles"] = a["source_shingles"]
    assert near_duplicate_lineages([a, b]) == {a["lineage"], b["lineage"]}


def test_dataset_identity_excludes_hardware_and_runtime(fixtures):
    data = tiny_dataset(fixtures)
    before = dataset_hash(data)
    data.update({"duration_seconds": 99, "environment": {"platform": "different"}})
    assert dataset_hash(data) == before


def test_real_gradient_and_learning_on_controlled_pairs(fixtures):
    torch.set_num_threads(1)
    torch.manual_seed(7)
    analysis = analyze_file(fixtures / "demo-O0.elf", Settings())
    functions = analysis.functions[:4]
    vocab = vocabulary(functions)
    model = encoder(len(vocab))
    inputs, stats = tensors([f for f in functions for _ in range(2)], vocab)
    labels = torch.tensor([i for i in range(4) for _ in range(2)])
    optimizer = torch.optim.Adam(model.parameters(), lr=0.005)
    losses = []
    for _ in range(15):
        optimizer.zero_grad()
        loss = contrastive_loss(model(inputs, stats), labels)
        loss.backward()
        assert sum(float(p.grad.abs().sum()) for p in model.parameters() if p.grad is not None) > 0
        optimizer.step()
        losses.append(float(loss.detach()))
    assert losses[-1] < losses[0] * 0.3


def test_safe_model_roundtrip_and_corruption(fixtures, tmp_path):
    functions = analyze_file(fixtures / "demo-O0.elf", Settings()).functions
    vocab = vocabulary(functions)
    model = encoder(len(vocab)).eval()
    expected = embed(model, vocab, functions)
    save_package(tmp_path, model, vocab, {"dataset_hash": "fixture"})
    loaded, loaded_vocab, manifest = load_model(tmp_path)
    np.testing.assert_allclose(embed(loaded, loaded_vocab, functions), expected, atol=1e-7)
    assert manifest["feature_schema"] == FEATURE_SCHEMA
    (tmp_path / "weights.safetensors").write_bytes(b"corrupt")
    with pytest.raises(ReconError, match="integrity"):
        load_model(tmp_path)


def test_resume_matches_uninterrupted_training(fixtures, tmp_path):
    data = tiny_dataset(fixtures)
    uninterrupted = tmp_path / "full"
    resumed = tmp_path / "resumed"
    full = train(data, uninterrupted, 3, 42)
    first = train(data, resumed, 1, 42)
    second = train(data, resumed, 3, 42, resume=True)
    assert len(first["history"]) == 1
    np.testing.assert_allclose(
        [h["loss"] for h in full["history"]], [h["loss"] for h in second["history"]], atol=1e-7
    )
    assert full["model_version"] == second["model_version"]
    changed = copy.deepcopy(data)
    changed["samples"][0]["function"]["name"] = "different"
    changed["dataset_hash"] = dataset_hash(changed)
    with pytest.raises(ReconError, match="same dataset"):
        train(changed, resumed, 4, 42, resume=True)


def test_persisted_neural_index_and_model_cache(fixtures, tmp_path):
    functions = analyze_file(fixtures / "demo-O0.elf", Settings()).functions
    vocab = vocabulary(functions)
    package = tmp_path / "model"
    save_package(package, encoder(len(vocab)).eval(), vocab, {"dataset_hash": "fixture"})
    assert inference_model(package)[0] is inference_model(package)[0]
    pairs = [(str(i), f) for i, f in enumerate(functions)]
    index = tmp_path / "index.npy"
    first = neural_rank(pairs, pairs, package, 5, 0.65, index)
    second = neural_rank(pairs, pairs, package, 5, 0.65, index)
    assert index.is_file()
    assert first["results"] == second["results"]
    manifest = read_json(index.with_suffix(".json"))
    manifest["feature_schema"] = "wrong"
    from recon.storage.artifacts import atomic_json

    atomic_json(index.with_suffix(".json"), manifest)
    with pytest.raises(ReconError, match="different functions"):
        neural_rank(pairs, pairs, package, 5, 0.65, index)
