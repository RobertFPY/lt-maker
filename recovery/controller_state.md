# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture,
> invariants, model policy, task definitions, and global escalation rules.

## Current authorization

- Current phase: **Phase 9 — Full validation and release candidate**
- Phases 1–8: **ACCEPTED**
- P9-T01 full PC regression matrix: **ACCEPTED** at
  `50e7339986d3eff2998d49000c3b61437949e358`
- P9-T02 full Android regression/performance matrix: **ACCEPTED / PASS** at
  `981593e78efd2f6f537e48d81d5cdc076585b284`
- Active task: **P9-T03 — Architecture contamination audit**
- P9-T03 status: **AUTHORIZED**
- Primary model: **GPT-5.6 Terra / high**
- Escalation target: **GPT-5.6 Sol / max**
- Escalation authorized: **NO**
- Prerequisite: **P9-T02 accepted**
- Controller gate after P9-T03: **YES — STOP FOR CONTROLLER REVIEW**
- P9-T04: **UNAUTHORIZED**
- No later task is authorized.
- Trace V1/comparator/manifest/golden changes: **UNAUTHORIZED**
- Project data/assets: **UNAUTHORIZED**
- Merge to `master`: **UNAUTHORIZED**

## P9-T02 acceptance record

The controller accepts the P9-T02 PASS evidence at
`981593e78efd2f6f537e48d81d5cdc076585b284`.

Accepted facts:

- ESC-02 was explicitly authorized and is resolved;
- the x86_64 WSA ABI blocker was repaired while preserving the default
  `arm64-v8a` build target;
- strict APK ABI-directory and ELF-machine verification passed;
- the current x86_64 artifact installed and launched successfully on WSA;
- project metadata, resources, database, engine, title, and gameplay startup
  completed;
- the previous EM_AARCH64/EM_X86_64 linker mismatch and SIGSEGV did not
  reproduce;
- representative Android Event/combat, tilemap, movement/FOW, save/load,
  pristine restart, fast-forward, debugger/profiler, audio/resource, and
  synchronization-point validation passed;
- no gameplay, save-schema, project-data, Trace V1, golden, work-budget,
  cache, renderer, audio-policy, or scheduling semantic was changed;
- remaining physical-device performance and acoustic-observation limitations
  are non-blocking for P9-T02 acceptance.

The complete accepted evidence remains in
`recovery/p9_t02_android_regression_performance.md`.

## P9-T03 execution gate

P9-T03 may begin only in a **new Codex execution** after the controller-state
synchronization commit exists at HEAD and the model gate confirms exactly:

`GPT-5.6 Terra / high`

P9-T03 must audit the categories and obey the acceptance/stop conditions in
`plan.md`. Every remaining suspicious architecture case requires explicit
classification and justification. If remaining contamination requires
architecture-level reconciliation rather than bounded local cleanup, stop and
request the configured escalation target; do not self-escalate.

P9-T04 and every later task remain unauthorized until controller review and
acceptance of P9-T03.

## Protected unexpected path

The expected zero-byte untracked path remains protected:

`recovery/pc-core-semantics`

Do not edit, delete, stage, rename, normalize, or clean this path.
