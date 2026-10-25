# Requirements and acceptance coverage

“Implemented” below means the listed behavior has local implementation/tests, not
that all production/security/performance properties are proven. The supplied full
specification remains authoritative. This is the first working version, not a claim
that every final SRS acceptance criterion is closed.

| Requirements | Evidence | Status / boundary |
|---|---|---|
| FR-001–004 | ELF admission; API upload; static worker; test_static_analysis/test_api | ELF implemented. PE deferred; packing detection is limited. Targets never intentionally executed. |
| FR-005–009 | Native discovery, normalized instructions, CFG, explorer; browser test | Implemented for supported ELF; indirect/exception edges incomplete. |
| FR-010–012 | Versioned tokens, opcode/n-gram/structural features, persisted scores | Implemented; deterministic baselines tested. |
| FR-013–015 | Pinned sources, DWARF labels, split and near-duplicate audit | Implemented pilot. Wider compiler/project matrix remains to validate. |
| FR-016–018 | CPU contrastive training, safetensors, model/schema checks | Real run saved; resume and round-trip tested. |
| FR-019–020 | Exact persisted candidate vectors, compatible search | Architecture/schema restricted; compiler/project filtering beyond dataset reports is deferred. |
| FR-021–023 | Scores labeled similarity, unknown threshold, query and two-binary UI | Browser workflow verified. Not one-to-one semantic matching. |
| FR-024–027 | Persistent jobs, restart handling, cancellation, versioned cache/indexes | Implemented; streaming progress is coarse by task phase. |
| FR-028 | Function name/address/mnemonic search, pagination | Implemented. Full arbitrary metadata filters deferred. |
| FR-029 | Analysis/comparison JSON and CSV exports | Implemented, including raw instruction provenance. Experiments use JSON to preserve nesting. |
| FR-030–032 | Dataset CLI; retrieval metrics, subgroup/false-match reports | Pilot measured. Real GCC/Clang run on this Mac unavailable. |
| FR-033–036 | Bundled demo, deletion, hashed artifacts, compatibility checks | Implemented; dependent comparison/index/evidence cleanup tested. |
| FR-037–038 | REA optional fallback; UI caveats | Caveats implemented; actual Ghidra and standalone Ghidra adapter unverified/deferred. |
| FR-039–040 | Loopback API, Origin/Host checks, health/capabilities | Implemented. Remote exposure/authentication deliberately unavailable. |
| FR-041–045 | REA provider, diagnostics, pinned contract and provenance | Adapter/fallback tested with labeled fixtures; genuine provider capabilities and output not yet exercised. |
| FR-046 | Optional assisted explanation | Not configured; external AI narratives absent by default. |
| FR-047–050 | Native/ML independence, consent, evidence distinction, diagnostics | Local fallback/consent tested; actual dependency-version health probes still need installed provider. |
| FR-051–056 | Source manifest, compiler matrix builder, labels/splits, baselines | Pilot implemented. Linux CI matrix configured, pending observed run. |
| FR-057–059 | Shared CPU encoder, checkpoints, optimizer, seeds/history | Real gradients/training and resume equivalence tested. |
| FR-060 | Recall/MRR/false matches, timing, vector/process memory records | Measured pilot; open-world no-match false-positive evaluation is not implemented. |
| FR-061–062 | Hash-verified model package load/save and offline CPU inference | Implemented for local packages; explicit model import UI/CLI remains deferred. |
| FR-063–066 | Candidate indexes, score/version/assembly, unknown threshold, baseline fallback | Implemented; FAISS runs in an isolated helper with exact NumPy fallback. |
| FR-067–068 | Baseline comparison report and optional Research Mode | Implemented; core mode never retrains. |
| FR-069 | Two-version binary comparison | Function-by-function ranked candidates implemented. A comprehensive changed/unchanged/removed classification is deferred. |
| FR-070 | Optional REA and native fallback | Fixture-tested; real Ghidra investigation unverified. |

| Non-functional requirements | Evidence / limits |
|---|---|
| NFR-001–003,024 | Bounded parser subprocess, validated extents/paths, streamed uploads, loopback/Origin checks. Full OS isolation differs by platform. |
| NFR-004–006 | Measured pilot phase timings and exact retrieval. No universal runtime target or accuracy guarantee. |
| NFR-007–008,023 | Persisted job failures, SQLite foreign keys, atomic hashed files, compatible index manifests. |
| NFR-009–013 | Seeds/environment/split audit, baselines, validation selection, held-out reports and uncertainty labels. Near-duplicate checks are heuristic. |
| NFR-014–018 | ELF-only scope, typed modules/API, migrations, tests/CI, evidence links and labeled controls. Full accessibility audit remains pending. |
| NFR-019–022,025 | No cloud inference, local logs/storage, platform docs, architecture/threat/model/dataset cards. Clean Linux CI still requires observed results. |
| NFR-026–033 | Optional provider boundaries/provenance/deadline/fallback implemented; full provider isolation and real installation are unverified. |
| NFR-034–037 | Offline baselines, CPU training preset, deterministic run, pinned source licenses. Only pilot-scale performance measured. |
| NFR-038–043 | No target execution, split isolation, safe weights/index compatibility, similarity labels and parser budgets. Training itself relies on a bounded preset, not an OS-isolated training worker. |
| NFR-044–045 | Real artifacts/logs, disclosed underperformance/failed runs, independent core mode. |

UC-01–04, UC-08–12, UC-18 and UC-20 have locally tested core paths. UC-05–07,
UC-17/19/22 have real pilot CLI runs and lifecycle tests. UC-13 requires the optional
approved setup; UC-14/15/21 have fixture/fallback tests only. UC-16 core independence
is tested. Human confirmation/rationale annotations for UC-15 are not implemented.

Original T-01–15 and AT-016–025 map to the test modules named above. AT-016's
genuine two-compiler matrix and TC-021's real REA/Ghidra end-to-end run are not
marked passed. All broader deferred work stays visible here and in `KNOWN_ISSUES.md`.
