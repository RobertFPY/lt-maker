# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, model policy, and global escalation rules. Historical evidence remains in committed recovery reports and prior controller commits.

## Current authorization

- Current phase: **Phase 6**
- Phase 1 harness / immutable Trace V1 PC-reference goldens: **ACCEPTED**
- Phase 2 state-restore semantics: **ACCEPTED**
- Phase 3 combat lifecycle semantics: **ACCEPTED**
- Phase 4 tilemap/board/event atomicity: **ACCEPTED**
- Phase 5 save/load/restart consolidation: **ACCEPTED**
- P5-T01 save-format / compatibility audit: **ACCEPTED** at `f0abf0cb4f4aa05df9f6bff86a959f203d25553f`
- P5-T02 canonical transactional load API: **ACCEPTED** at `788d47c4dad8b9c2b4201fa50f58414bc5e98837`
- P5-T03 canonical restart contract: **ACCEPTED** at `4059a2af59e3dc97a7bb557fffac649fc2ee6a19`
- Active task: **P6-T01 only — Define runtime capability interfaces**
- Primary model: **GPT-5.6 Terra / high**
- Escalation target: **GPT-5.6 Sol / max**
- Escalation pre-authorized: **NO**
- P6-T02/P6-T03 and Phase 7+: **UNAUTHORIZED**
- Production migration/behavior changes in P6-T01: **UNAUTHORIZED unless strictly required for a no-op interface proof explicitly listed below; default is report/design only**
- Golden/reference fixture changes: **UNAUTHORIZED**
- Project-data / asset changes: **UNAUTHORIZED**
- Controller gate after P6-T01: **YES — STOP FOR CONTROLLER REVIEW**

## Phase 5 acceptance record

The controller accepts `4059a2af59e3dc97a7bb557fffac649fc2ee6a19` (`fix(save): preserve pristine restart slots`) and closes Phase 5.

Accepted evidence:

- the commit is one direct descendant of P5-T03 authorization commit `4422419e0e30855e9bd79666c20fc284da0fbee8`;
- production scope is limited to `app/engine/save.py`, `app/engine/title_screen.py`, and `app/engine/runtime_debugger.py`, with bounded restart/debugger tests; no project data, Trace V1, comparator, manifest, or golden fixture changed;
- normal tactical saves keep current progress in SAVE_SLOT while a frozen deep copy of the matching `chapter_start_snapshot` becomes the RESTART_SLOT source;
- `snapshot_matches_chapter` and persistent restart validation use payload/metadata level identity rather than current-progress heuristics;
- the Test Chapter first-save path no longer seeds restart from mid-chapter progress when a valid pristine snapshot exists;
- save A -> B uses the current chapter's frozen snapshot when available and otherwise carries only source-proven same-chapter persistent restart material;
- stale/wrong-chapter restart material is removed/rejected instead of silently becoming the current slot's Restart Level source;
- restart payloads remain ordinary engine save payloads with `kind='start'` and level identity; gameplay-authoritative restart state is not moved into metadata-only storage;
- snapshot/restart data handed to the save thread is frozen before worker start, preventing later live gameplay mutations from changing restart bytes;
- restart persistence writes a temporary payload+metadata pair and removes incomplete/selectable restart material on failure while leaving the current-progress main save independent;
- desktop and Android Title Restart validate the same restart source and route through the accepted P5-T02 `LoadDestination.RESTART_LEVEL` transaction; Android differs only in immutable read/presentation orchestration;
- the canonical load transaction additionally rejects a restart payload whose level identity does not match the explicit requested chapter;
- Runtime Debugger restart prefers a matching in-memory snapshot, otherwise requires a matching persistent restart slot, and applies requested difficulty only through explicit canonical load context;
- overworld Restart Level remains the established special case using the matching main overworld SAVE_SLOT rather than tactical restart material;
- restart reconstructs chapter-start initiative state via `start_level` and does not restore current-progress initiative state;
- immutable S1/S2/S4/S12/S18 were reported exact PASS; focused canonical/restart/debugger/title/Android/Event suites and compile/diff/show checks were reported PASS;
- full discovery remains affected by the known shared-test pollution/native baseline and was not broadened into unrelated repair.

### Locked Phase-5 contracts

Later phases must preserve:

1. **Canonical load:** one shared main-thread authoritative transaction for desktop and Android; Android worker may read/unpickle immutable bytes only.
2. **S/Q publication:** saved state stack/queue remains transaction-local until complete world/controller reconstruction and publishes once.
3. **Compatibility state:** optional bounded `controller_state` only where exact phase/initiative progress requires it; default player/non-initiative/start/overworld payload shapes remain unchanged.
4. **Legacy initiative:** current-progress legacy initiative payload without exact tracker state fails explicitly rather than guessing.
5. **Restart:** SAVE_SLOT is current progress; RESTART_SLOT is source-proven pristine current-chapter material; current progress is never silently promoted to pristine restart truth.
6. **Restart source:** current-session `chapter_start_snapshot` is preferred when matching; persistent restart is fallback only when matching the intended chapter.
7. **Aura/board/FOW:** derived structures remain nonserialized and are rebuilt after authoritative data exists.
8. **Event serialization:** internal Event/EventProcessor support remains; user-facing arbitrary mid-event S3 remains unsupported.
9. **SAVE_SLOTS / RESTART_SLOTS:** remain distinct storage/menu contracts.

## P6-T01 — authorized scope

Execute **P6-T01 only** using **GPT-5.6 Terra / high**.

Escalation target: **GPT-5.6 Sol / max**, not pre-authorized.

PC behavioral reference:

`9314f54b49f4552b5a3d023b4da0012ce7dfbc89`

P6-T01 is an **architecture inventory / interface-design task**. P6-T02 owns migration of Android audio/resource policy. P6-T03 owns migration of accepted Android scheduling policy. Do not start either migration during P6-T01.

### Goal

Define narrow runtime capability boundaries that isolate platform policy from authoritative gameplay semantics without introducing a giant platform abstraction or spreading new `if is_android_runtime()` branches through gameplay-critical modules.

The desired direction is:

```text
gameplay/core code
    -> narrow capability/policy interface
        -> desktop/default implementation
        -> Android implementation
```

Capabilities may answer **how** platform work is performed. They must not answer or redefine **what gameplay happens, in what semantic order, or when authoritative state becomes visible**.

### Required whole-repo Android/platform branch inventory

Audit the current recovery HEAD, not only post-reference commit names.

Locate every runtime platform branch/capability use relevant to engine execution, including at minimum:

- `is_android_runtime()`;
- `is_android_render_optimization_enabled()`;
- any Android-specific cache/preload/resource toggles;
- Android streamed music/sound paths;
- Android touch/raw-input ownership;
- Android debugger routing;
- Android title/save/load presentation paths;
- Android tilemap pending-build/event barrier;
- frame-work budgets / incremental jobs;
- filesystem/build/runtime-environment checks that affect engine behavior;
- profiler/debugger observer routing;
- any direct platform checks in gameplay-critical combat/state/event/save modules.

For each occurrence record:

- file/function;
- caller;
- platform condition;
- data read/written;
- whether it can mutate authoritative gameplay state;
- whether it can advance a gameplay lifecycle/state machine;
- whether it changes ordering/timing only or changes outcomes;
- current accepted phase/task provenance;
- proposed capability boundary or reason to leave direct/local.

Do not assume every Android check must be abstracted. A direct check may remain when it is genuinely platform-local and does not leak through gameplay-critical code.

### Required capability families

Design narrow interfaces for the candidate families below only when source evidence supports them.

#### 1. Audio / music backend capability

Cover current platform differences such as streamed Android battle/title/game-over music versus desktop cached/mixer playback.

The interface may choose:

- streamed vs cached playback;
- preload/flush policy;
- resource release policy;
- backend-specific fade/play calls.

It must not choose:

- when combat starts/ends;
- when a battle-music semantic transition occurs;
- whether a combat/event hook fires;
- state-stack ordering.

P6-T02 will implement/migrate this interface later.

#### 2. Resource load / preload capability

Cover platform differences around expensive resource/audio loading, battle-animation/resource setup, title assets, and safe background immutable work.

Separate:

- immutable/background preparation;
- main-thread pygame/resource publication requirements;
- authoritative gameplay state.

Do not design an interface that lets a worker mutate `game`, DB runtime state, Event state, combat solver state, or authoritative registries.

#### 3. Render / cache capability

Cover accepted Android render/cache optimizations and title/UI cache policy.

The interface may decide:

- whether a presentation cache is enabled;
- cache size/lifetime/prefill policy;
- rendering-only fast paths.

It must preserve invalidation correctness and INV-07 observer behavior. Do not hide gameplay data mutation behind a render interface.

#### 4. Frame-work budget / scheduling capability

This is design-only in P6-T01. P6-T03 owns migration.

Map accepted uses such as Phase-4 Android pending tilemap preparation and any other time-budgeted platform work.

The capability may provide:

- a numeric work budget;
- whether progressive **off-world/non-authoritative** preparation is enabled;
- platform-specific budget selection.

It must never authorize:

- yielding between authoritative gameplay mutations;
- staged combat solver/action/cleanup semantics;
- staged live GameState hydration;
- one-unit-at-a-time live event mutations;
- partial board/unit/region/aura/FOW publication.

The accepted transaction contracts from Phases 2–5 remain stronger than any scheduling policy.

#### 5. Filesystem / runtime-environment capability

Audit whether engine runtime currently has platform-specific filesystem/path/build assumptions worth encapsulating.

Keep editor/build-only concerns separate from runtime capability design when possible.

Do not create a broad service locator just to wrap `os.path`.

#### 6. Input / touch capability

Audit current Android raw-touch consumer/input handling.

Define a capability only if doing so reduces platform leakage without changing the existing InputManager/gameplay action semantics.

Fast-forward remains timing-only under INV-06; input edges may not be replayed across additional logical updates.

### Explicitly protected direct policies

P6-T01 must identify, but not migrate or redesign, these accepted behaviors:

- Android streamed battle music from `9004c67b...` and current recovery equivalents;
- Phase-4 Event-local pending tilemap preparation barrier;
- P5 Android save worker immutable read/unpickle + opaque loader presentation;
- Android debugger/touch release behavior around restart;
- profiler/debugger observer isolation;
- desktop synchronous gameplay semantics.

### Capability design rules

Every proposed interface must satisfy all of the following:

1. **Narrow responsibility.** Prefer small functions/protocols over one `PlatformServices` god object.
2. **Default semantics.** Desktop/default implementation must remain straightforward and reference-compatible.
3. **No gameplay fork.** No capability may branch combat actions, RNG, hooks, events, turn/phase logic, save semantics, restart semantics, unit mutation, aura/FOW rules, or state-machine ordering.
4. **No hidden scheduling.** A call that looks synchronous to gameplay code must not secretly resume gameplay across host frames unless its work is explicitly off-world and caller lifecycle is already protected by an accepted barrier.
5. **Observable output equivalence.** Shared optimizations remain only when behavior/order/output is equivalent under existing traces/tests.
6. **No editor dependency.** Engine remains importable without PyQt5.
7. **No circular platform ownership.** Capability modules may depend on low-level runtime/config/audio/render helpers, but gameplay modules must not be required by the capability implementation merely to decide platform policy.
8. **Testability.** Each capability should support deterministic unit tests or injection/patching without mutating project data.
9. **Incremental migration.** P6-T02/P6-T03 must be able to migrate one family at a time without a flag day.
10. **Deletion path.** Identify which direct Android checks should disappear after migration and which should intentionally remain local.

### Required architecture map

For each proposed capability provide:

- proposed module/name;
- minimal API signatures;
- default/desktop behavior;
- Android behavior;
- current callers to migrate;
- current direct platform checks eliminated;
- authoritative-state contract;
- threading contract;
- failure contract;
- test strategy;
- migration owner: P6-T02, P6-T03, later phase, or LEAVE-DIRECT.

Do not write large speculative interfaces. If an API has no current caller/proven use, do not add it merely for future cleanliness.

### Classification vocabulary

Classify every audited platform branch as one of:

- `CAP-AUDIO`
- `CAP-RESOURCE`
- `CAP-RENDER-CACHE`
- `CAP-WORK-BUDGET`
- `CAP-FILESYSTEM`
- `CAP-INPUT-TOUCH`
- `OBSERVER-ONLY`
- `GAMEPLAY-SEMANTIC — MUST NOT PLATFORM-FORK`
- `LEAVE-DIRECT — PLATFORM-LOCAL`
- `REMOVE-WORKAROUND`
- `NEEDS-CONTROLLER-DECISION`

Also carry forward recovery disposition where useful:

- KEEP-SHARED
- KEEP-PLATFORM
- REWRITE-PLATFORM
- RESTORE-PC-SEMANTICS
- REMOVE-WORKAROUND
- KEEP-CORRECTNESS-FIX

### Deliverable

Create only:

`recovery/p6_t01_runtime_capability_map.md`

No production migration is expected in P6-T01.

Required sections:

1. whole-repo platform-branch inventory;
2. authoritative gameplay vs platform-policy boundary;
3. audio/music capability proposal;
4. resource/preload capability proposal;
5. render/cache capability proposal;
6. frame-work budget capability proposal;
7. filesystem/runtime-environment findings;
8. input/touch findings;
9. observer/debugger/profiler findings;
10. direct checks intentionally left local;
11. P6-T02 migration plan;
12. P6-T03 migration plan;
13. proposed modules/APIs/signatures;
14. dependency/circular-import analysis;
15. tests required for later migration;
16. unresolved controller decisions / escalation evidence.

If an extremely small no-op protocol/type definition is necessary to prove import layering, STOP and request controller authorization before production creation. Report-only is the default authorized output.

### Validation / proof

P6-T01 is design/audit, so do not invent behavior tests merely to make a report look active. Use existing tests and focused source inspection to prove classification.

Run at minimum immutable comparisons covering platform-sensitive protected semantics:

- S5 combat;
- S12 aura;
- S13 FOW;
- S14 tilemap;
- S16 fast-forward;
- S17 debugger/profiler observer;
- S18 game-over/restart.

Do not regenerate any golden.

Run relevant current tests for:

- Android runtime helpers;
- streamed music/audio policy;
- Android title/render caches;
- Phase-4 tilemap pending barrier;
- P5 canonical Android load/restart routing;
- debugger/touch/input behavior;
- profiler observer behavior.

Run broader unittest discovery and report existing baseline/native Windows termination without fixing unrelated issues.

Then:

- `python -m compileall -q app`
- `git diff --check`
- commit only `recovery/p6_t01_runtime_capability_map.md`
- `git show --check`
- `git status --short`

### Explicitly out of scope

Do not:

- implement P6-T02;
- implement P6-T03;
- migrate audio/resource/render/tilemap/input callers yet;
- add a giant platform service/container;
- alter gameplay/state/combat/save/restart semantics;
- change P4 tilemap barrier behavior;
- change P5 canonical load/restart behavior;
- modify Trace V1/comparator/manifest/goldens;
- modify project data/assets;
- fix unrelated baseline tests;
- merge master.

## Escalation / stop rules

Primary: **GPT-5.6 Terra / high**.
Escalation target: **GPT-5.6 Sol / max**.
Pre-authorized: **NO**.

STOP on:

- **ESC-02** platform branch semantics cross subsystems nonlocally and cannot be classified safely;
- **ESC-04** multiple incompatible capability boundaries change gameplay-visible semantics;
- **ESC-05** an existing accepted platform policy appears to violate a locked invariant;
- **ESC-07** a proposed platform boundary requires gameplay-semantic divergence;
- **ESC-09** safe isolation would require a new cross-cutting runtime/service architecture.

Do not self-escalate.

## Gate status

**Phase 5 is ACCEPTED. P6-T01 is the only authorized task. P6-T02/P6-T03 and Phase 7+ remain blocked pending P6-T01 controller review.**
