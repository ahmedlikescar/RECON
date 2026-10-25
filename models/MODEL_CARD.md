# Pilot model card

`models/pilot/` contains actually trained `weights.safetensors`, a JSON vocabulary
and a manifest, not fabricated weights. `experiments/pilot-training.json` records
every epoch's loss, gradient norm and validation MRR. The selected model is
`siamese-39d0c5aca865`, from epoch 11, seed 42.

Inputs: at most 256 normalized instruction tokens, masked mean of 64-dimensional
token embeddings, and five log structural statistics scaled by 1/5. Projection:
69→96, GELU, 96→64, L2 normalization. Training: shared weights, supervised contrastive
InfoNCE temperature 0.1, AdamW learning rate 0.003, weight decay 0.01, maximum 16
lineages with two builds each per batch, CPU, one thread, deterministic algorithms.

Training projects: rxi/vec and rxi/map (80 samples, 20 lineages). Validation:
tiny-AES-c (80 samples). Test: rxi/ini (40 samples), only after checkpoint selection.
Source licenses/provenance are listed in `docs/ML_DATASET.md` and the pinned manifest.

This is an educational pilot. It underperforms the combined baseline in the measured
held-out experiment. Use for ranked candidate exploration with assembly/CFG evidence,
not proof of semantic equivalence, maliciousness, correctness or safety. Long functions
are truncated; stripped boundaries, inlining, compiler drift and unseen projects are
significant limitations. Cross-architecture support is absent.

Weights/tokenizer/schema hashes are verified on load. Incompatible or corrupt
packages fail clearly. Optimizer checkpoints use separate safetensors/JSON, not
pickle. Default analysis never retrains, and baseline-only operation is supported.
The shipped model is installed only by the demo preparer when research dependencies
are present; locally trained models are not overwritten.
