# Engineering decisions

2026-10-25:

1. Section 26 of the supplied specification is the delivery sequence. Original
   FR/NFR/UC identifiers remain requirements; the final traceability table marks
   partial or deferred items explicitly.
2. Start with x86-64 ELF, as the stated MVP permits. PE, Mach-O, sectionless and
   compressed ELF are rejected rather than guessed. Native Windows is not validated;
   WSL2 is the documented development route.
3. Use Zig's pinned cross compiler for known Linux ELF fixtures on this Apple Silicon
   host. It is a Clang toolchain, not GCC. Linux CI builds a genuine GCC/Clang matrix;
   successful CI execution will be reported only after observed completion.
4. Keep exact search at pilot scale. This avoids approximate-neighbor tuning and
   makes benchmark rankings reproducible. FAISS is optional and CPU-only.
5. The first encoder uses masked mean token pooling plus log structural statistics,
   with a compact shared projection. Its performance is measured against all
   baselines, and the strongest observed method remains the combined baseline.
6. Use safetensors plus JSON for weights and optimizer state. No pickle checkpoints
   or arbitrary downloaded model code are accepted. Only compatible artifacts load.
7. Bundle a small, actually trained pilot model with its run history and provenance.
   It is a demonstration artifact, not a production accuracy claim. The core app
   remains functional when PyTorch/weights are absent.
8. REA 6.8.0 and upstream commit `f69c52a1cf3940ed1999fcc0859a75dbb913d684`
   were inspected before adapter implementation. Installation/configuration has not
   been approved or performed. No global agent settings are modified.
9. Preserve the supplied full requirements as text. Do not publish the Word file's
   document metadata. Keep generated local inputs/datasets out of Git.
10. After initial testing, source hashes and near-duplicate audits were strengthened,
    and runtime/hardware were removed from dataset content identity. Training was
    repeated with unchanged seed/config; the selected model weights were identical.
    The final dataset hash/report supersede the preliminary pilot report.
