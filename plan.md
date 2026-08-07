# PC Core Semantics Recovery — Master Execution Plan

> **Status:** ACTIVE
> **Plan owner / controller:** ChatGPT (project planner, reviewer, gatekeeper)
> **Executor:** Codex (implementation agent only)
> **Recovery branch:** `recovery/pc-core-semantics`
> **PC behavioral reference:** `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`
> **Recovery starting HEAD:** `0821182a717de2baaf52a699ee325241ffaddd03`
> **Android introduction / mixed-change landmark:** `52bd040317f16b7973602dd78e769ed990501549`
> **Model policy version:** 2026-08-08

---

## 0. PURPOSE OF THIS FILE

This file is the authoritative recovery plan for restoring the gameplay core to the original PC semantics while preserving later features, correctness fixes, safe performance optimizations, and Android-specific optimizations that do not alter gameplay behavior.

Codex is an **executor**, not the project architect. Codex must not redesign this plan, widen task scope, skip gates, or decide that a behavior change is acceptable without explicit approval from the plan controller.

The controller is responsible for:

- defining and revising architecture;
- approving each phase transition;
- reviewing evidence, diffs, tests, and regressions;
- deciding whether an optimization is behavior-preserving;
- deciding whether Android-only divergent behavior is acceptable;
- assigning or reassigning tasks by model tier;
- deciding whether a workaround is removed, retained, or rewritten;
- determining whether the recovery can advance to the next gate.

Codex is responsible for:

- inspecting code and history as requested;
- implementing exactly the active task packet;
- writing tests and diagnostic tooling;
- running specified verification commands;
- reporting evidence and unresolved risks;
- stopping at required gates.

The user acts as the bridge between Codex and the controller when a controller review is required.

---

# 1. MANDATORY CODEX SESSION PROTOCOL

## 1.1 Read-before-work rule

At the beginning of **every Codex task/session in this repository**, before editing any file, Codex must:

1. Read `AGENTS.md`.
2. Read this entire `plan.md`.
3. Identify the active phase and exact task ID requested by the user/controller.
4. State the task ID, required model, current model, allowed scope, and stop conditions.
5. Inspect `git status`, current branch, and current HEAD.
6. Refuse to work directly on `master` for recovery tasks.
7. Refuse to begin if the model gate is not satisfied.
8. Refuse to begin if the requested task has an unmet prerequisite or controller gate.

If Codex cannot read this file, cannot determine the current model, cannot determine the branch, or cannot identify the requested task ID, **STOP** and ask the user to resolve the condition. Do not guess.

## 1.2 Branch rule

All recovery implementation work must occur on:

`recovery/pc-core-semantics`

or a short-lived child branch explicitly authorized by the controller.

Codex must never force-push, rewrite shared history, reset `master`, or perform a broad revert unless the active task explicitly instructs it.

## 1.3 No autonomous phase advancement

Completing a task does not authorize Codex to start the next task.

At every task marked **CONTROLLER GATE**, Codex must stop after reporting results and say that controller review is required. The user will return the report to the controller and later provide the next authorized task ID.

## 1.4 No silent substitutions

Codex must not silently:

- replace a required model with another model;
- weaken a test because it fails;
- alter acceptance criteria;
- change expected PC behavior to match current Android behavior;
- preserve an optimization merely because it improves FPS;
- remove a feature because recovering it is difficult;
- modify game project content/assets to make engine tests pass unless the task explicitly concerns project data.

---

# 2. MODEL GATING POLICY

The recovery deliberately uses stronger models only where architectural reasoning and cross-subsystem correctness justify the token cost.

OpenAI's current Codex model family used by this plan:

- `GPT-5.3-Codex`: primary long-horizon agentic coding/reasoning model.
- `GPT-5.3-Codex-Spark`: fast model reserved for narrow, mechanical, well-specified work.

**Do not substitute models.** If the currently selected Codex model is not exactly the required model for the active task, stop before editing and ask the user to switch models.

If a required model is no longer available in the product, stop and ask the user to return to the controller so this policy can be revised. Do not choose a replacement yourself.

## 2.1 Tier A — architecture-critical

**Required model:** `GPT-5.3-Codex`
**Required reasoning level:** `xhigh` when the Codex UI/CLI exposes reasoning level; otherwise the highest available reasoning setting.

Use Tier A for:

- `GameState` lifecycle changes;
- state machine semantics;
- combat lifecycle restoration;
- save/load transactional semantics;
- restart architecture;
- tilemap/board atomicity;
- migration of staged gameplay operations;
- cross-platform policy architecture;
- debugging nonlocal regressions;
- final integration/reconciliation;
- any task touching more than one correctness-critical subsystem.

## 2.2 Tier B — bounded engineering

**Required model:** `GPT-5.3-Codex`
**Required reasoning level:** `medium` or `high` as specified by the task.

Use Tier B for:

- regression harness implementation from an approved design;
- feature preservation work with clear contracts;
- Android backend/platform adapters;
- medium-sized refactors with stable semantics;
- save compatibility tests;
- fast-forward/debug/restart feature verification;
- performance benchmarking and profiling scripts.

## 2.3 Tier C — narrow mechanical work

**Required model:** `GPT-5.3-Codex-Spark`

Use Tier C only for tasks that are fully specified and local, such as:

- documentation updates;
- adding repetitive test cases to an already-established test pattern;
- mechanical renames after an API is frozen;
- collecting file/commit inventories;
- narrow one-file cleanup where behavior must remain unchanged;
- generating reports from existing test/profiler output.

Spark must not perform independent architecture decisions or recovery-critical semantic refactors.

---

# 3. NON-NEGOTIABLE SYSTEM INVARIANTS

These invariants override performance goals.

## INV-01 — One gameplay core

There is one authoritative gameplay core shared by PC and Android. There must not be separate PC and Android gameplay implementations.

## INV-02 — PC semantics are the behavioral reference

For systems that existed before Android work, `9314f54b` defines the initial PC behavioral reference unless a later independent correctness fix or explicitly preserved feature supersedes it.

The reference is behavioral, not textual. We do not blindly copy old files.

## INV-03 — No observable partial gameplay state

Live gameplay code must not observe a half-restored or half-built state.

Forbidden examples include:

- state stack restored while level/tilemap is missing;
- camera/map state active before the map is valid;
- board swapped before aura/fog/regions are valid;
- combat hooks split so unrelated game logic can observe an intermediate combat state.

## INV-04 — Android may optimize presentation/resource policy, not gameplay ordering

Android may differ in:

- rendering strategy;
- frame presentation/skipping;
- audio streaming;
- resource preload;
- memory/cache policy;
- filesystem/build integration;
- background preparation that does not mutate the live gameplay world.

Android must not differ in:

- combat solver semantics;
- action ordering;
- event ordering;
- RNG consumption/order;
- skill/item hook ordering;
- state-machine logical transitions;
- final gameplay state at synchronization points.

## INV-05 — Optimization must be behavior-preserving

An optimization belongs in shared core only when it preserves externally observable gameplay behavior and ordering.

Safe candidates include:

- memoization with correct invalidation;
- eliminating redundant work;
- avoiding allocations;
- equivalent algorithms;
- culling/render caching that does not affect logic;
- batching draw work while preserving visual ordering;
- faster lookups/indexes.

## INV-06 — Fast-forward changes time, not outcomes

With identical seed/input, fast-forward ON and OFF must produce the same logical action trace and final game state. Fast-forward may reduce waits or presentation frames but must not skip logical hooks/updates.

## INV-07 — Debugger/profiler are observers

PC and Android debugger/profiler functionality must remain available as required, but instrumentation must not alter gameplay behavior, state ordering, or cache validity.

## INV-08 — Feature preservation

The recovery must preserve later intended features and their legitimate fixes, including at minimum:

- fast-forward / speed controls;
- debugger functionality on PC and Android;
- runtime profiling;
- restart game/chapter functionality;
- save/load enhancements;
- later independent gameplay correctness fixes;
- Android build support;
- Android audio streaming and other accepted platform-specific features.

## INV-09 — Project content is protected

Game data, resources, animations, portraits, levels, events, classes, items, skills, project-specific content, and unrelated editor improvements are not rollback targets.

## INV-10 — Evidence before optimization retention

A performance change that cannot demonstrate semantic equivalence remains disabled/reverted from the shared core until proved safe.

---

# 4. RECOVERY CLASSIFICATION

Every post-reference engine change must end in exactly one classification:

### KEEP-SHARED

Behavior-preserving optimization, feature, or bugfix beneficial to both PC and Android.

### KEEP-PLATFORM

Useful platform-specific implementation whose observable gameplay semantics remain shared. Android audio streaming is the canonical example.

### REWRITE-PLATFORM

The goal is valid for Android, but the current implementation contaminates core semantics. Keep the goal; rewrite behind Android/runtime policy.

### RESTORE-PC-SEMANTICS

Current implementation changes gameplay/lifecycle semantics. Restore the original PC semantics in core while re-porting independent features/fixes.

### REMOVE-WORKAROUND

A later guard/workaround only exists because a staged/partial state was introduced. Remove only after the originating invalid state is impossible and tests prove the guard is unnecessary.

### KEEP-CORRECTNESS-FIX

A later fix repairs a real invariant independent of Android optimization and must survive recovery.

---

# 5. HIGH-RISK COMMIT / SUBSYSTEM MAP

The following is a starting map, not a substitute for code-level review.

## 5.1 Strong candidates to keep

- `7735ca29` — hierarchical runtime profiling.
- `6631e736` — release debugger/render-panel performance work, subject to debugger-preservation tests.
- `97c58a63` — difficulty setup correctness fix.
- `a566ae6d` — Windows editor workspace fix.
- `d2bbd026` — Android profiler thread isolation; preserve.
- `9004c67b` — Android streamed battle music; preserve as platform-specific backend behavior.
- Android build/config/tooling that does not change gameplay semantics.
- Project content/resource changes.

## 5.2 High-risk recovery cluster

- `cdd4be2a` — staged tilemap board rebuild.
- `6b96e2f1` — batched tilemap transition state.
- `78acb08a` through `fff0145d` — staged map/simple/base/animation combat sequence.
- `390638ac` — camera guard during staged restore.
- `6bd9da4b` — map-safety guards for staged loading.
- `8306e1a9` — deferred saved state until level restore completes.

These commits are not automatically reverted. Their changes must be decomposed into semantic changes, safe optimizations, features, and workaround fixes.

## 5.3 Mixed commit warning

`52bd0403` is a large mixed commit. Never revert it wholesale. Audit by subsystem and file intent.

---

# 6. DEFINITION OF SYNCHRONIZATION POINT

A synchronization point is a point where PC and Android must expose equivalent logical game state despite platform-specific presentation timing.

Examples:

- immediately after level load finishes;
- immediately before player control begins;
- after a movement action commits;
- after combat cleanup and state-stack handling complete;
- after an event command transaction completes;
- after tilemap change commits;
- after save restore fully commits;
- after chapter restart reaches playable state;
- at phase transition completion.

Behavioral comparison must happen at synchronization points, not arbitrary intermediate render frames.

---

# 7. REQUIRED REPORT FORMAT FOR EVERY CODEX TASK

Before implementation, Codex must print:

```
TASK: <ID>
MODEL REQUIRED: <model + reasoning>
MODEL CURRENT: <detected model + reasoning>
BRANCH: <branch>
HEAD: <sha>
SCOPE: <files/modules>
INVARIANTS: <INV ids>
PREREQUISITES: <task ids>
```

If model mismatch exists, output only the mismatch, request the required model, and STOP.

After implementation, Codex must report:

```
TASK RESULT: PASS | PARTIAL | FAIL
FILES CHANGED:
BEHAVIORAL CHANGES:
TESTS ADDED/UPDATED:
COMMANDS RUN:
TEST RESULTS:
REFERENCE COMPARISON:
PERFORMANCE IMPACT (if measured):
KNOWN RISKS:
UNRESOLVED QUESTIONS:
COMMIT SHA:
NEXT ACTION: CONTROLLER REVIEW | NONE
```

Never claim PASS if required tests were skipped.

---

# 8. PHASE 0 — BASELINE, INVENTORY, AND SAFETY RAILS

## Goal

Create objective evidence before changing semantics.

### P0-T01 — Capture recovery baseline

**Model:** Tier C — `GPT-5.3-Codex-Spark`
**Risk:** Low
**Controller gate:** No

Tasks:

- verify recovery branch starts at `0821182a...`;
- record Python/runtime/dependency versions;
- record current full test-suite result;
- inventory relevant Android/runtime flags;
- inventory current profiling controls;
- list engine files changed between `9314f54b` and recovery HEAD;
- generate a concise `recovery/baseline.md` report; do not modify engine behavior.

Acceptance:

- baseline report committed;
- no engine behavior changes;
- test failures, if any, recorded verbatim and categorized rather than fixed.

### P0-T02 — Build post-reference semantic change inventory

**Model:** Tier B — `GPT-5.3-Codex` medium
**Risk:** Medium
**Prerequisite:** P0-T01
**Controller gate:** YES

Tasks:

- inspect all changed engine/runtime files after `9314f54b`;
- map each change to KEEP-SHARED / KEEP-PLATFORM / REWRITE-PLATFORM / RESTORE-PC-SEMANTICS / REMOVE-WORKAROUND / KEEP-CORRECTNESS-FIX;
- identify mixed changes inside individual commits;
- identify all `is_android_runtime`, render optimization gates, staged jobs, generators/yields, worker threads, and deferred commits in engine code;
- produce `recovery/change_inventory.md`.

Acceptance:

- every correctness-critical changed engine file classified;
- uncertain cases explicitly marked `NEEDS-CONTROLLER-DECISION`;
- no production behavior changes.

**STOP FOR CONTROLLER REVIEW.**

---

# 9. PHASE 1 — BEHAVIORAL REGRESSION HARNESS

## Goal

Establish a repeatable oracle for logical behavior before restoring core semantics.

### P1-T01 — Design deterministic trace schema

**Model:** Tier A — `GPT-5.3-Codex` xhigh
**Prerequisite:** Controller approval of P0-T02
**Controller gate:** YES

Design, do not yet broadly instrument production code.

Trace must capture enough information to compare behaviors without depending on render frame count:

- state stack nids at synchronization points;
- active level/overworld identity;
- unit nid/uid-relevant logical state;
- positions, HP, mana, statuses, skills, inventory/durability;
- game/level vars relevant to scenarios;
- RNG state/checkpoints where feasible;
- combat playback/action sequence;
- triggered event identifiers/order;
- turn/phase;
- tilemap/board identity and required invariants;
- save/load/restart completion state.

Do not log volatile surface/audio objects or frame timings as equality criteria.

Deliver design and proposed helper APIs/tests.

**STOP FOR CONTROLLER REVIEW.**

### P1-T02 — Implement trace/test harness

**Model:** Tier B — `GPT-5.3-Codex` high
**Prerequisite:** Approved P1-T01 design
**Controller gate:** No

Implement the approved harness with minimal production intrusion.

### P1-T03 — Establish PC-reference golden scenarios

**Model:** Tier A — `GPT-5.3-Codex` xhigh
**Prerequisite:** P1-T02
**Controller gate:** YES

Run/create representative deterministic scenarios against the PC reference and current branch as technically appropriate.

Minimum scenario families:

1. New game to first playable map.
2. Existing save load.
3. Save/load during event where supported.
4. Restart current chapter.
5. Standard map combat.
6. Simple combat.
7. Animation combat.
8. Arena/base combat where applicable.
9. Skill proc and pre/post-combat hooks.
10. Item durability/uses and broken/unusable handling.
11. Promotion/class-change edge cases.
12. Aura propagation/teardown/load.
13. Fog-of-war move preview/cancel/wait.
14. Tilemap change.
15. Phase transition.
16. Fast-forward ON vs OFF equivalence.
17. Debugger disabled/enabled observer-equivalence.
18. Game-over/restart path.

Do not make current code pass by changing expected reference behavior.

**STOP FOR CONTROLLER REVIEW.**

---

# 10. PHASE 2 — RESTORE GAMESTATE AND STATE-MACHINE ATOMICITY

## Goal

Eliminate partial live state as an accepted core condition.

### P2-T01 — Audit GameState/load/state restore delta

**Model:** Tier A — `GPT-5.3-Codex` xhigh
**Prerequisite:** Approved Phase 1 harness
**Controller gate:** YES

Focus:

- `app/engine/game_state.py`;
- state machine files;
- title/load job states;
- chapter/overworld restore entry points;
- staged-state fields and commit paths;
- later restart/save feature dependencies.

Deliver a function-level restore/re-port map before edits.

**STOP FOR CONTROLLER REVIEW.**

### P2-T02 — Restore synchronous PC state semantics

**Model:** Tier A — `GPT-5.3-Codex` xhigh
**Prerequisite:** Approved P2-T01
**Controller gate:** YES

Requirements:

- PC core must not install saved state stack before required level/overworld structures exist;
- do not solve this by making every shared state tolerate arbitrary missing globals;
- restore an atomic logical transaction boundary;
- retain later save format/features independent of staging;
- retain restart feature intent;
- isolate any Android progressive preparation outside authoritative live state.

Run full targeted harness and full unit suite.

**STOP FOR CONTROLLER REVIEW.**

### P2-T03 — Remove obsolete staged-restore workarounds

**Model:** Tier B — `GPT-5.3-Codex` high
**Prerequisite:** Controller accepts P2-T02
**Controller gate:** YES

Candidates include camera/map/tilemap guards introduced solely to tolerate invalid partial restore.

Rule: remove a guard only if tests demonstrate the invalid state can no longer occur. Guards that remain valid defensive programming independent of staging may stay, but must be documented as such.

**STOP FOR CONTROLLER REVIEW.**

---

# 11. PHASE 3 — RESTORE COMBAT LIFECYCLE SEMANTICS

## Goal

Return shared combat logic to the PC ordering contract while retaining safe optimizations and later correctness fixes.

### P3-T01 — Build combat lifecycle reference map

**Model:** Tier A — `GPT-5.3-Codex` xhigh
**Prerequisite:** Phase 2 accepted
**Controller gate:** YES

Compare PC reference vs current for:

- `SimpleCombat`;
- `MapCombat`;
- `BaseCombat`;
- `AnimationCombat`;
- arena paths;
- solver initialization and advancement;
- pre-combat hooks;
- action generation/application;
- playback generation;
- item/skill cleanup hooks;
- broken/unusable item checks;
- EXP and promotion transitions;
- state-stack handling;
- `end_combat` ordering;
- transform animation preparation;
- battle music preparation.

Separate gameplay work from presentation/resource work.

**STOP FOR CONTROLLER REVIEW.**

### P3-T02 — Restore Simple/Map combat core ordering

**Model:** Tier A — `GPT-5.3-Codex` xhigh
**Prerequisite:** Approved P3-T01
**Controller gate:** YES

No yielding/staging may expose an intermediate gameplay transaction to unrelated states.

Preserve safe computational optimizations only when trace-equivalent.

**STOP FOR CONTROLLER REVIEW.**

### P3-T03 — Restore Base/Animation/Arena combat core ordering

**Model:** Tier A — `GPT-5.3-Codex` xhigh
**Prerequisite:** P3-T02 accepted
**Controller gate:** YES

Retain Android-only battle music streaming as a platform implementation detail.

Animation/resource preparation may be progressive on Android only if it cannot mutate/advance shared gameplay semantics prematurely.

**STOP FOR CONTROLLER REVIEW.**

### P3-T04 — Combat feature/fix preservation sweep

**Model:** Tier B — `GPT-5.3-Codex` high
**Prerequisite:** P3-T03 accepted
**Controller gate:** YES

Verify later correctness fixes and project-specific mechanics remain intact, especially:

- cleanup ordering;
- durability/uses costs;
- promotion cancel/finalization semantics;
- skill cache invalidation;
- aura-related combat interactions;
- fast-forward behavior;
- debug controls relevant to combat.

**STOP FOR CONTROLLER REVIEW.**

---

# 12. PHASE 4 — TILEMAP / BOARD / EVENT ATOMICITY

## Goal

Preserve performance wins without exposing partially rebuilt board state.

### P4-T01 — Decompose staged tilemap optimization

**Model:** Tier A — `GPT-5.3-Codex` xhigh
**Prerequisite:** Phase 3 accepted
**Controller gate:** YES

Audit:

- `GameBoard.build_iter` and related incremental helpers;
- `TilemapChangeJob`;
- batched tilemap transition state;
- aura/terrain/fog/region rebuilding;
- event rendering deferral;
- commit ordering.

Classify each part as computational optimization vs scheduling semantic change.

**STOP FOR CONTROLLER REVIEW.**

### P4-T02 — Restore desktop atomic tilemap semantics

**Model:** Tier A — `GPT-5.3-Codex` xhigh
**Prerequisite:** Approved P4-T01
**Controller gate:** YES

Desktop path should preserve original synchronous logical behavior.

Safe lookup/build optimizations may remain shared.

**STOP FOR CONTROLLER REVIEW.**

### P4-T03 — Rebuild Android-only progressive board preparation

**Model:** Tier A — `GPT-5.3-Codex` xhigh
**Prerequisite:** P4-T02 accepted
**Controller gate:** YES

Only if profiling justifies retaining it.

Contract:

```
LIVE OLD STATE
    -> build all pending structures off-world
    -> validate pending world
    -> one atomic logical commit
LIVE NEW STATE
```

The live `game` object must not point piecemeal at pending structures.

**STOP FOR CONTROLLER REVIEW.**

---

# 13. PHASE 5 — SAVE / LOAD / RESTART FEATURE CONSOLIDATION

## Goal

Keep all desired capabilities without making Android staging part of core semantics.

### P5-T01 — Save format and compatibility audit

**Model:** Tier B — `GPT-5.3-Codex` high
**Prerequisite:** Phase 4 accepted
**Controller gate:** YES

Inventory:

- fields added since reference;
- event-state serialization behavior;
- restart-slot behavior;
- chapter-start snapshot behavior;
- aura reconstruction requirements;
- current save compatibility expectations;
- Android load orchestration dependencies.

Test old/reference-compatible saves and current saves where fixtures are available.

**STOP FOR CONTROLLER REVIEW.**

### P5-T02 — Canonical transactional load API

**Model:** Tier A — `GPT-5.3-Codex` xhigh
**Prerequisite:** Approved P5-T01
**Controller gate:** YES

Design and implement one authoritative core load transaction.

Android may perform expensive resource preparation around it, but must not redefine when logical restore becomes visible.

**STOP FOR CONTROLLER REVIEW.**

### P5-T03 — Canonical restart contract

**Model:** Tier A — `GPT-5.3-Codex` xhigh
**Prerequisite:** P5-T02 accepted
**Controller gate:** YES

Preserve:

- restart current chapter;
- difficulty selection behavior as intended;
- Test Chapter edge cases;
- game-over restart;
- debug-triggered restart.

Define exactly what constitutes pristine chapter-start state and ensure restart cannot inherit accidental mid-chapter partial state.

**STOP FOR CONTROLLER REVIEW.**

---

# 14. PHASE 6 — PLATFORM POLICY BOUNDARY

## Goal

Move Android-specific policies out of gameplay semantics.

### P6-T01 — Define runtime capability interfaces

**Model:** Tier A — `GPT-5.3-Codex` xhigh
**Prerequisite:** Phase 5 accepted
**Controller gate:** YES

Prefer narrow capabilities over a giant platform abstraction.

Candidate boundaries:

- audio/music backend;
- resource loading/preload policy;
- render/cache policy;
- frame-work budget policy;
- filesystem/build path handling.

Avoid sprinkling new `if is_android_runtime()` through gameplay code.

**STOP FOR CONTROLLER REVIEW.**

### P6-T02 — Migrate Android audio/resource policy

**Model:** Tier B — `GPT-5.3-Codex` high
**Prerequisite:** Approved P6-T01
**Controller gate:** No

Keep current Android streamed battle music behavior where correct.

### P6-T03 — Migrate accepted Android scheduling policy

**Model:** Tier A — `GPT-5.3-Codex` xhigh
**Prerequisite:** P6-T02
**Controller gate:** YES

Only migrate scheduling behaviors previously approved as safe. Any scheduling that requires core gameplay to tolerate partial state is rejected or redesigned.

**STOP FOR CONTROLLER REVIEW.**

---

# 15. PHASE 7 — PRESERVE AND VERIFY USER-FACING FEATURES

## P7-T01 — Fast-forward equivalence suite

**Model:** Tier B — `GPT-5.3-Codex` high
**Prerequisite:** Phase 6 accepted
**Controller gate:** YES

Compare fast-forward ON/OFF using identical seed/input.

Must match:

- actions;
- RNG-dependent outcomes;
- combat results;
- XP;
- durability/costs;
- skills/statuses;
- events;
- final state.

Only timings/presentation may differ.

**STOP FOR CONTROLLER REVIEW.**

### P7-T02 — Debugger parity PC/Android

**Model:** Tier B — `GPT-5.3-Codex` medium
**Prerequisite:** P7-T01 accepted
**Controller gate:** YES

Verify intended debug commands/features including restart, chapter navigation, unit editing, auto-level, teleport, items, world values, and platform UI integration.

Debugger disabled/enabled without commands must not alter logical game behavior.

**STOP FOR CONTROLLER REVIEW.**

### P7-T03 — Profiler observer-equivalence

**Model:** Tier C — `GPT-5.3-Codex-Spark`
**Prerequisite:** P7-T02 accepted
**Controller gate:** No

Verify profiler ON/OFF produces equivalent game state and preserves worker-thread isolation.

### P7-T04 — Save/load/restart UX regression sweep

**Model:** Tier B — `GPT-5.3-Codex` high
**Prerequisite:** P7-T03
**Controller gate:** YES

Run feature-level scenarios on PC and Android pathways.

**STOP FOR CONTROLLER REVIEW.**

---

# 16. PHASE 8 — REINTRODUCE / VALIDATE SAFE SHARED OPTIMIZATIONS

## Goal

Recover performance after semantics are stable, one optimization class at a time.

### P8-T01 — Cache/memoization audit

**Model:** Tier B — `GPT-5.3-Codex` high
**Controller gate:** YES

Criteria:

- correct invalidation;
- no dependence on mutable state invisible to cache keys;
- identical logical traces.

Remember existing LTCache invariant: invalidate after publishing mutable component state.

**STOP FOR CONTROLLER REVIEW.**

### P8-T02 — Render/cache/batching optimization audit

**Model:** Tier B — `GPT-5.3-Codex` high
**Controller gate:** YES

Keep output-equivalent optimizations shared.

**STOP FOR CONTROLLER REVIEW.**

### P8-T03 — Allocation/redundant-work optimization audit

**Model:** Tier B — `GPT-5.3-Codex` medium
**Controller gate:** YES

Measure before/after where practical.

**STOP FOR CONTROLLER REVIEW.**

### P8-T04 — Android-only performance retuning

**Model:** Tier A — `GPT-5.3-Codex` xhigh
**Prerequisite:** P8-T01..T03 accepted
**Controller gate:** YES

Use profiler evidence. Optimize only behind accepted platform boundaries.

No optimization is accepted solely on FPS improvement if behavioral trace changes.

**STOP FOR CONTROLLER REVIEW.**

---

# 17. PHASE 9 — FULL VALIDATION AND RELEASE CANDIDATE

### P9-T01 — Full PC regression matrix

**Model:** Tier B — `GPT-5.3-Codex` high
**Controller gate:** YES

Run:

- full unit tests;
- type checks where applicable;
- deterministic behavioral scenarios;
- representative project launches;
- save/load/restart flows;
- fast-forward and debugger checks.

No unexplained reference divergence.

**STOP FOR CONTROLLER REVIEW.**

### P9-T02 — Full Android regression/performance matrix

**Model:** Tier B — `GPT-5.3-Codex` high
**Prerequisite:** P9-T01 accepted
**Controller gate:** YES

Compare Android synchronization-point logical traces against PC.

Collect performance evidence:

- frame-time distribution;
- worst stalls for load/combat/phase/tilemap transitions;
- memory-sensitive paths where measurable;
- audio/resource behavior.

**STOP FOR CONTROLLER REVIEW.**

### P9-T03 — Architecture contamination audit

**Model:** Tier A — `GPT-5.3-Codex` xhigh
**Prerequisite:** P9-T02 accepted
**Controller gate:** YES

Search final code for:

- Android conditionals in gameplay-critical modules;
- staged/deferred fields in `GameState`;
- partial-state guards;
- worker-thread mutation of gameplay state;
- duplicate PC/Android gameplay implementations;
- yield/generator boundaries inside logical transactions;
- TODO/FIXME introduced during recovery.

Every remaining case requires justification.

**STOP FOR CONTROLLER REVIEW.**

### P9-T04 — Final release candidate review

**Model:** Tier A — `GPT-5.3-Codex` xhigh
**Prerequisite:** P9-T03 accepted
**Controller gate:** FINAL

Codex must not merge to `master` itself unless the user explicitly instructs it after controller approval.

Deliver:

- final commit range;
- architecture summary;
- preserved features list;
- removed/replaced staging list;
- known limitations;
- PC behavior-equivalence evidence;
- Android behavior-equivalence evidence;
- performance comparison;
- test results;
- recommended merge strategy.

**STOP FOR FINAL CONTROLLER APPROVAL.**

---

# 18. STOP CONDITIONS — APPLY TO ALL TASKS

Codex must immediately stop and report rather than improvise when any of these occurs:

1. Current model does not exactly satisfy the task model gate.
2. Required prerequisite task/gate is not approved.
3. Work is requested on `master` instead of the authorized recovery branch.
4. A proposed fix would intentionally change PC behavioral semantics.
5. A test indicates the PC reference itself contains a known later-fixed bug and the classification is unclear.
6. An optimization changes RNG consumption/order or gameplay action ordering.
7. An Android optimization requires shared core to expose/tolerate partial state.
8. Save compatibility cannot be maintained without a format/migration decision.
9. A task needs to edit protected project content to make an engine test pass.
10. Scope expands into a second major subsystem not named in the task.
11. Required tests cannot be run or their environment is unavailable.
12. Codex discovers evidence contradicting an assumption in this plan.
13. A destructive Git operation appears necessary.
14. Codex cannot verify its current model/reasoning level when the task has a model gate.

On stop, provide evidence and request controller guidance through the user.

---

# 19. CHANGE DISCIPLINE

## 19.1 Commit discipline

Prefer one conceptual change per commit.

Commit messages should use recovery-oriented prefixes where useful:

- `test(recovery): ...`
- `refactor(core): ...`
- `fix(core): ...`
- `perf(shared): ...`
- `perf(android): ...`
- `refactor(android): ...`
- `docs(recovery): ...`

Do not combine project content changes with engine recovery commits.

## 19.2 Diff discipline

Before finishing each task:

- inspect the complete diff;
- ensure no generated files were hand-edited incorrectly;
- ensure unrelated formatting churn is absent;
- ensure no debug prints/temp files remain;
- ensure tests target the invariant, not the implementation detail alone.

## 19.3 Test discipline

A regression test should fail for the broken semantic condition and pass for the recovered one.

Do not write only "no crash" tests when logical state can be asserted.

Because tests share the global `game` singleton, each new test touching `game` must seed/reset every state element it relies on.

---

# 20. PERFORMANCE ACCEPTANCE RULES

Performance is evaluated only after correctness for the affected task.

For a proposed optimization record, where feasible:

- workload/scenario;
- PC baseline;
- Android baseline;
- before/after median frame or operation time;
- p95/p99 or worst meaningful stall when available;
- semantic trace equality result;
- memory tradeoff if material.

A performance win with semantic divergence is a FAIL.

A small performance regression may be accepted temporarily during semantic recovery, but must be recorded for Phase 8.

---

# 21. CONTROLLER DECISION LOG

The controller should append decisions here when assumptions change.

| Date | Decision | Scope | Rationale |
|---|---|---|---|
| 2026-08-08 | Use `9314f54b` as initial PC behavioral reference | Core gameplay | Last clear pre-Android behavioral baseline before `52bd0403`; reference is behavioral, not a wholesale rollback target. |
| 2026-08-08 | Recovery starts from current HEAD `0821182a` | Entire repo | Preserve project content, later features, fixes, assets, and Android support. |
| 2026-08-08 | One shared gameplay core | Architecture | Avoid PC/Android behavioral forks and long-term divergence. |
| 2026-08-08 | Android may retain platform-specific streaming/scheduling only behind semantic boundaries | Android | Preserve Android performance without exposing partial gameplay state. |
| 2026-08-08 | Preserve fast-forward, PC/Android debugger, profiler, restart, save/load enhancements | Features | Explicit product requirements. |
| 2026-08-08 | Model-gated execution | Process | Spend strongest model tokens on architecture-critical tasks and Spark on narrow mechanical tasks. |

---

# 22. CURRENT EXECUTION STATE

**Current phase:** Phase 0

**Next authorized task:** `P0-T01` only.

No later task is authorized until the controller receives and reviews the required preceding reports.

**P0-T01 required model:** `GPT-5.3-Codex-Spark`.

If Codex is currently running any other model, it must stop and ask the user to switch to `GPT-5.3-Codex-Spark` before executing P0-T01.

---

# 23. SHORT FORM CODEX REMINDER

When working on this recovery:

1. Read `AGENTS.md` and `plan.md` first.
2. Work only on the authorized recovery branch/task.
3. Enforce exact model gate; mismatch means STOP.
4. PC gameplay semantics are authoritative unless controller approves a later correctness fix.
5. Preserve features and independent bugfixes.
6. Shared optimizations must be trace-equivalent.
7. Android-only optimization belongs behind platform policy and cannot expose partial gameplay state.
8. Do not self-advance through controller gates.
9. Report evidence, tests, risks, and commit SHA.
10. When uncertain about semantics, STOP and escalate; do not invent a new architecture.
