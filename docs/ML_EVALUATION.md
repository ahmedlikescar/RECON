# Evaluation protocol and observed pilot results

The run uses seed 42, CPU deterministic operations, training-only vocabulary, and
validation-only checkpoint selection. All model settings and baseline weights were
fixed before final test evaluation. Validation compares O0→O2. Epoch 11 was selected;
training stopped at epoch 19 after eight epochs without validation improvement.

Final test evaluation compares all ordered different-build pairs within the held-out
ini project: 120 queries over ten verified functions and four optimization builds.
The test project was not used to select weights or change hyperparameters.

| Method | Recall@1 | Recall@5 | Recall@10 | MRR |
|---|---:|---:|---:|---:|
| Opcode cosine | 0.650 | 0.875 | 1.000 | 0.742 |
| Instruction n-grams | 0.725 | 0.900 | 1.000 | 0.806 |
| Structural features | 0.700 | 1.000 | 1.000 | 0.812 |
| Combined baseline | 0.825 | 0.950 | 1.000 | 0.875 |
| Neural encoder | 0.700 | 0.900 | 1.000 | 0.798 |

The neural model underperforms the combined baseline and n-grams. On the more
challenging O0→O2 subset (ten queries), Recall@1 is 0.60 combined, 0.50 n-gram,
and 0.40 neural. Similar O1/O2/O3 builds make the aggregate task easier.

At the fixed uncalibrated threshold 0.65, the neural method accepts 108 queries and
has 24 false top matches. The combined baseline accepts 60 with no false top matches
in this specific pilot. Neither observation is a calibrated safety guarantee, and
this is not an open-world no-match benchmark. Unknown state is a UI filter.

`experiments/pilot-evaluation.json` contains exact metrics, subgroup tables by
project/compiler pair/optimization/size, false-positive examples and query bootstrap
intervals. Queries repeat across build pairs; those intervals do not measure
project-level generalization. Candidate names are used only to label results.

Ranking timings exclude feature extraction, tokenization, loading and index creation.
See `BENCHMARKS.md` for timing scope. Reproduce with the pinned dataset/model and
`recon evaluate`; outputs must declare dataset/model/schema versions. Changing the
test corpus after looking at results is a new experiment, not a comparable rerun.
