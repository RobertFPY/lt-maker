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
- P9-T03 architecture contamination audit: **ACCEPTED / PASS** at
  `14f93b42c411119bbd1871eed5d150541dbc4fde`
- Authorized task: **P9-T04 — Final release candidate review**
- P9-T04 status: **AUTHORIZED — NOT STARTED**
- Primary model: **GPT-5.6 Sol / max**
- Escalation target: **GPT-5.6 Sol / ultra**
- Escalation authorized: **NO**
- Prerequisite: **P9-T03 accepted**
- Controller gate after P9-T04: **FINAL**
- No task beyond P9-T04 is authorized.
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

## P9-T03 acceptance record

The controller accepts the P9-T03 PASS evidence at
`14f93b42c411119bbd1871eed5d150541dbc4fde`.

Accepted architecture conclusions:

- no Android gameplay fork remains;
- no staged authoritative restore remains;
- no partial-world publication remains;
- no worker thread improperly mutates authoritative gameplay state;
- no generic Event scheduling contamination remains;
- retained platform and presentation boundaries are justified;
- P9-T02 ABI support remains confined to build, editor, and tooling policy;
- no unresolved architecture contamination remains;
- no semantic escalation trigger was encountered.

The complete accepted evidence remains in
`recovery/p9_t03_architecture_contamination_audit.md`.

## P9-T04 execution gate

P9-T04 is **AUTHORIZED — NOT STARTED**. It may begin only:

1. after this controller-state change is committed outside the Codex sandbox;
2. after the resulting new HEAD is returned to the controller;
3. after the controller verifies that commit; and
4. in a **new Codex execution** whose model gate confirms exactly
   `GPT-5.6 Sol / max`.

P9-T04 must use the escalation target `GPT-5.6 Sol / ultra` only after explicit
controller authorization. Its controller gate is **FINAL**.

No task beyond P9-T04 is authorized. Merge to `master` remains unauthorized.

## Protected unexpected path

The expected zero-byte untracked path remains protected:

`recovery/pc-core-semantics`

Do not edit, delete, stage, rename, normalize, or clean this path.
