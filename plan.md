# PC Core Semantics Recovery — Master Execution Plan

> **Status:** ACTIVE
> **Plan owner / controller:** ChatGPT (project planner, reviewer, gatekeeper)
> **Executor:** Codex (implementation agent only)
> **Recovery branch:** `recovery/pc-core-semantics`
> **PC behavioral reference:** `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`
> **Recovery starting HEAD:** `0821182a717de2baaf52a699ee325241ffaddd03`
> **Android introduction / mixed-change landmark:** `52bd040317f16b7973602dd78e769ed990501549`
> **Model policy version:** 2026-08-08 / GPT-5.6

---

# 0. PURPOSE AND AUTHORITY

This file is the authoritative execution plan for restoring the gameplay core to the original PC semantics while preserving later features, correctness fixes, safe shared optimizations, and Android-specific optimizations that do not alter gameplay behavior.

Codex is an **executor**, not the project architect. Codex must not redesign this plan, widen task scope, skip gates, accept behavioral divergence for performance, or decide that a workaround is acceptable without controller approval.

The controller is responsible for:

- defining and revising architecture;
- assigning the active task;
- assigning the exact model and reasoning effort for that task;
- approving each phase transition;
- reviewing diffs, tests, traces, benchmarks, and regressions;
- deciding whether an optimization is behavior-preserving;
- deciding whether Android-only behavior is an acceptable platform specialization;
- deciding whether a workaround is removed, retained, or rewritten;
- determining when the recovery can advance.

Codex is responsible for:

- reading repository instructions and this plan before every task;
- inspecting code and history only within the authorized task scope;
- implementing exactly the active task packet;
- writing tests and diagnostic tooling required by that task;
- running the specified verification commands;
- reporting evidence and unresolved risks;
- stopping whenever a controller gate or stop condition is reached.

The user is the bridge between Codex and the controller when controller review is required.

---

# 1. MANDATORY CODEX SESSION PROTOCOL

At the beginning of **every Codex session/task in this repository**, before editing any file, Codex must:

1. Read root `AGENTS.md` in full.
2. Read root `AGENTS.override.md` in full if present.
3. Read this entire `plan.md`.
4. Identify the exact authorized task ID.
5. State the required model and exact reasoning effort for the task.
6. Detect and state the current model and reasoning effort.
7. Inspect `git status`, current branch, and current HEAD.
8. Verify all task prerequisites and controller gates.
9. Refuse to work directly on `master` for recovery work.
10. Refuse to begin when the model/effort gate is not satisfied.

Before implementation Codex must print:

```text
TASK: <ID>
MODEL REQUIRED: <model>
EFFORT REQUIRED: <effort>
MODEL CURRENT: <detected model>
EFFORT CURRENT: <detected effort>
BRANCH: <branch>
HEAD: <sha>
SCOPE: <files/modules>
INVARIANTS: <INV ids>
PREREQUISITES: <task ids / controller approvals>
```

If Codex cannot determine its current model or current effort, it must STOP before editing and ask the user to resolve that condition.

## 1.1 Exact model gate

The model requirement in each task is exact.

If a task says `GPT-5.6 Terra`, running it with `GPT-5.6 Sol` is still a mismatch. Codex must not silently upgrade or downgrade models because the controller is deliberately allocating model cost and capability.

If the current model does not exactly match the required model:

```text
MODEL GATE FAILED
Required: <model>
Current: <model>
Action: switch to the required model and rerun this task.
```

Then STOP without edits.

## 1.2 Exact effort gate

The reasoning effort is also part of the task assignment.

This plan may use:

- `low`
- `medium`
- `high`
- `xhigh`
- `max`
- `ultra` where Codex exposes it

If the current effort differs from the exact required effort, Codex must STOP and request the required effort.

Do not interpret a higher effort as automatically authorized. The controller may intentionally choose a lower effort to reduce token usage and prevent unnecessary exploration on tightly specified tasks.

## 1.3 Availability rule

If a required model or effort is not selectable in the current Codex environment, STOP and report the unavailable requirement. Do not select a replacement model or effort yourself. The controller will revise the assignment if necessary.

## 1.4 Branch rule

All recovery implementation work must occur on:

`recovery/pc-core-semantics`

or a short-lived child branch explicitly authorized by the controller.

Never force-push, rewrite shared history, reset `master`, or perform a broad revert unless the active task explicitly authorizes it.

## 1.5 No autonomous phase advancement

Completing a task does not authorize starting another task.

At every **CONTROLLER GATE**, Codex must stop after producing its report. The user will provide the report to the controller and later return with the next authorized task ID.

## 1.6 No silent substitutions

Codex must never silently:

- substitute a different model or effort;
- weaken a failing test;
- change acceptance criteria;
- update golden/reference behavior to match a regression;
- preserve an optimization merely because it improves FPS;
- remove a feature because recovering it is difficult;
- modify project content/assets to make an engine test pass unless explicitly authorized;
- expand a local task into an architectural refactor.

---

# 2. GPT-5.6 MODEL AND EFFORT POLICY

The recovery uses the GPT-5.6 family available in Codex.

Capability/cost intent used by this plan:

- **GPT-5.6 Sol** — flagship. Use for architecture-critical reasoning, nonlocal debugging, semantic reconciliation, and tasks where a wrong decision can corrupt multiple gameplay subsystems.
- **GPT-5.6 Terra** — balanced capability/cost. Use for bounded engineering, implementation from an approved design, substantial test work, compatibility work, and localized refactors with explicit contracts.
- **GPT-5.6 Luna** — fastest and most cost-efficient. Use for narrow mechanical work, inventories, repetitive tests following an established pattern, report generation, and low-risk verification.

Reasoning effort is treated as a **budget**, not a prestige setting. Higher effort is reserved for uncertainty, nonlocal interactions, long-horizon planning, and high blast radius.

## 2.1 Tier S3 — frontier architecture

**Model:** `GPT-5.6 Sol`
**Effort:** `ultra`

Use only for the highest-risk implementation/reconciliation points:

- authoritative `GameState` transaction rewrite;
- core combat transaction restoration where several combat classes interact;
- canonical save/load transaction implementation;
- final release-candidate architecture reconciliation.

These tasks justify the maximum available Codex deliberation because a subtle mistake may survive normal unit tests and corrupt long gameplay sequences.

## 2.2 Tier S2 — architecture-critical analysis/refactor

**Model:** `GPT-5.6 Sol`
**Effort:** `max`

Use for:

- lifecycle/reference-map design;
- state-machine semantics;
- combat ordering analysis;
- tilemap/board atomicity;
- Android/platform boundary design;
- architecture contamination audit;
- Android scheduling changes touching synchronization boundaries.

## 2.3 Tier S1 — difficult but bounded cross-system work

**Model:** `GPT-5.6 Sol`
**Effort:** `high`

Use when architecture has already been approved but implementation still spans multiple sensitive modules, especially Android performance retuning after correctness is stable.

## 2.4 Tier T2 — substantial bounded engineering

**Model:** `GPT-5.6 Terra`
**Effort:** `high`

Use for:

- regression harness implementation from approved design;
- feature/fix preservation sweeps;
- save compatibility audits;
- Android backend/platform adapter implementation;
- feature equivalence suites;
- performance/cache audits with clear acceptance criteria.

## 2.5 Tier T1 — routine engineering with explicit contract

**Model:** `GPT-5.6 Terra`
**Effort:** `medium`

Use for:

- debugger parity checks;
- localized optimization audits;
- structured code/history classification where architecture is not being chosen;
- medium test/refactor tasks with stable patterns.

## 2.6 Tier L2 — careful mechanical work

**Model:** `GPT-5.6 Luna`
**Effort:** `medium`

Use for:

- baseline capture;
- profiler observer tests;
- repetitive test additions from a frozen pattern;
- inventories and reports requiring some repository reasoning but no architecture decisions.

## 2.7 Tier L1 — purely mechanical work

**Model:** `GPT-5.6 Luna`
**Effort:** `low`

Use only for deterministic renames, documentation formatting, generated report cleanup, or equivalent low-risk mechanical changes explicitly authorized by the controller.

---

# 3. NON-NEGOTIABLE SYSTEM INVARIANTS

These invariants override all performance goals.

## INV-01 — One gameplay core

PC and Android share one authoritative gameplay implementation. Do not create separate gameplay engines.

## INV-02 — PC semantics are the behavioral reference

For systems that existed before Android work, `9314f54b` is the initial behavioral reference unless a later independent correctness fix or explicitly preserved feature supersedes it.

The reference is behavioral, not textual. Do not blindly copy old files.

## INV-03 — No observable partial gameplay state

Live gameplay code must never observe a half-restored or half-built state.

Forbidden examples:

- restored map state while level/tilemap is missing;
- camera/map state active before the map is valid;
- board swapped before aura/fog/regions are valid;
- combat hooks split so unrelated logic observes an intermediate combat transaction.

## INV-04 — Android may optimize platform policy, not gameplay ordering

Android may differ in:

- rendering strategy;
- frame presentation/skipping;
- audio streaming;
- resource preload;
- memory/cache policy;
- filesystem/build integration;
- background preparation that does not mutate authoritative gameplay state.

Android must not differ in:

- combat solver semantics;
- action ordering;
- event ordering;
- RNG consumption/order;
- skill/item hook ordering;
- logical state-machine transitions;
- final logical state at synchronization points.

## INV-05 — Shared optimizations must be behavior-preserving

An optimization belongs in shared core only when it preserves externally observable gameplay behavior and ordering.

Safe candidates include correctly invalidated memoization, redundant-work elimination, reduced allocations, equivalent algorithms, render culling/caching, draw batching that preserves order, and faster lookups/indexes.

## INV-06 — Fast-forward changes time, not outcomes

With identical seed/input, fast-forward ON and OFF must produce the same logical action trace and final game state. Only waits/presentation timing may differ.

## INV-07 — Debugger and profiler are observers

Enabling debugger/profiler without issuing a mutating debug command must not alter gameplay behavior, state ordering, RNG, or cache validity.

## INV-08 — Feature preservation

Preserve intended later features and legitimate fixes, including at minimum:

- fast-forward / speed controls;
- debugger functionality on PC and Android;
- runtime profiling;
- restart game/chapter functionality;
- save/load enhancements;
- later independent gameplay correctness fixes;
- Android build support;
- accepted Android audio/resource behavior.

## INV-09 — Project content is protected

Game data, resources, animations, portraits, levels, events, classes, items, skills, and unrelated editor improvements are not rollback targets.

## INV-10 — Evidence before optimization retention

A performance change that cannot demonstrate semantic equivalence remains disabled/rejected from shared core until proved safe.

---

# 4. RECOVERY CLASSIFICATION

Every post-reference engine change must be classified as one of:

- **KEEP-SHARED** — behavior-preserving optimization, feature, or bugfix useful on both platforms.
- **KEEP-PLATFORM** — platform-specific implementation preserving shared gameplay semantics.
- **REWRITE-PLATFORM** — Android goal is valid but current implementation contaminates core semantics; keep the goal and rewrite behind a platform boundary.
- **RESTORE-PC-SEMANTICS** — current implementation alters gameplay/lifecycle semantics; restore core ordering and re-port independent features/fixes.
- **REMOVE-WORKAROUND** — workaround exists only because an invalid staged/partial state was introduced; remove after proving the invalid state is impossible.
- **KEEP-CORRECTNESS-FIX** — later fix repairs a real invariant independent of Android and must survive recovery.

---

# 5. HIGH-RISK COMMIT / SUBSYSTEM MAP

## Strong keep candidates

- `7735ca29` — hierarchical runtime profiling.
- `6631e736` — debugger/render-panel performance work, subject to debugger-preservation tests.
- `97c58a63` — difficulty setup correctness fix.
- `a566ae6d` — Windows editor workspace fix.
- `d2bbd026` — Android profiler thread isolation.
- `9004c67b` — Android streamed battle music as platform-specific behavior.
- Android build/config/tooling that does not alter gameplay semantics.
- Project content/resource changes.

## High-risk recovery cluster

- `cdd4be2a` — staged tilemap board rebuild.
- `6b96e2f1` — batched tilemap transition state.
- `78acb08a` through `fff0145d` — staged map/simple/base/animation combat sequence.
- `390638ac` — camera guard during staged restore.
- `6bd9da4b` — map-safety guards for staged loading.
- `8306e1a9` — deferred saved state until level restore completes.

Do not automatically revert these commits. Decompose them into semantic changes, safe optimizations, features, and workaround fixes.

## Mixed commit warning

`52bd0403` is a large mixed commit. Never revert it wholesale. Audit by subsystem and file intent.

---

# 6. SYNCHRONIZATION POINTS

PC and Android logical state must match at synchronization points regardless of presentation timing.

Examples:

- after level load fully commits;
- immediately before player control begins;
- after movement commits;
- after combat cleanup/state-stack handling completes;
- after an event command transaction completes;
- after tilemap change commits;
- after save restore commits;
- after chapter restart reaches playable state;
- after phase transition completes.

Compare logical behavior at these points, not arbitrary render frames.

---

# 7. CODEX TASK REPORT FORMAT

After implementation Codex must report:

```text
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

# 8. PHASE 0 — BASELINE, INVENTORY, SAFETY RAILS

## P0-T01 — Capture recovery baseline

**Model:** `GPT-5.6 Luna`
**Effort:** `medium`
**Tier:** L2
**Risk:** Low
**Controller gate:** No

Tasks:

- verify recovery branch ancestry and starting reference;
- record Python/runtime/dependency versions;
- record current full test-suite result;
- inventory Android/runtime flags;
- inventory profiling controls;
- list engine files changed between `9314f54b` and recovery starting HEAD;
- create `recovery/baseline.md`;
- do not modify engine behavior.

Acceptance:

- baseline report committed;
- no engine behavior changes;
- existing test failures recorded and categorized, not fixed in this task.

## P0-T02 — Build post-reference semantic change inventory

**Model:** `GPT-5.6 Terra`
**Effort:** `medium`
**Tier:** T1
**Prerequisite:** P0-T01
**Controller gate:** YES

Tasks:

- inspect all changed engine/runtime files after `9314f54b`;
- classify changes using Section 4;
- identify mixed changes within commits;
- inventory `is_android_runtime`, render optimization gates, staged jobs, generators/yields, worker threads, and deferred commits;
- create `recovery/change_inventory.md`.

Acceptance:

- every correctness-critical changed engine file classified;
- uncertain cases marked `NEEDS-CONTROLLER-DECISION`;
- no production behavior changes.

**STOP FOR CONTROLLER REVIEW.**

---

# 9. PHASE 1 — BEHAVIORAL REGRESSION HARNESS

## P1-T01 — Design deterministic trace schema

**Model:** `GPT-5.6 Sol`
**Effort:** `max`
**Tier:** S2
**Prerequisite:** Controller approval of P0-T02
**Controller gate:** YES

Design trace schema for synchronization-point comparison. Capture:

- state stack nids;
- active level/overworld;
- units and relevant logical fields;
- positions, HP, mana, statuses, skills, inventory/durability;
- relevant game/level vars;
- RNG checkpoints where feasible;
- combat playback/action sequence;
- triggered event IDs/order;
- turn/phase;
- tilemap/board identity and invariants;
- save/load/restart completion state.

Do not compare volatile surfaces/audio objects or frame timings as gameplay equality criteria.

Deliver design and proposed helper APIs/tests only.

**STOP FOR CONTROLLER REVIEW.**

## P1-T02 — Implement trace/test harness

**Model:** `GPT-5.6 Terra`
**Effort:** `high`
**Tier:** T2
**Prerequisite:** Approved P1-T01
**Controller gate:** No

Implement the approved harness with minimal production intrusion.

## P1-T03 — Establish PC-reference golden scenarios

**Model:** `GPT-5.6 Sol`
**Effort:** `max`
**Tier:** S2
**Prerequisite:** P1-T02
**Controller gate:** YES

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
16. Fast-forward ON vs OFF.
17. Debugger disabled/enabled observer-equivalence.
18. Game-over/restart path.

Do not modify expected PC behavior to make current code pass.

**STOP FOR CONTROLLER REVIEW.**

---

# 10. PHASE 2 — GAMESTATE AND STATE-MACHINE ATOMICITY

## P2-T01 — Audit GameState/load/state-restore delta

**Model:** `GPT-5.6 Sol`
**Effort:** `max`
**Tier:** S2
**Prerequisite:** Approved Phase 1 harness
**Controller gate:** YES

Focus on:

- `app/engine/game_state.py`;
- state machine files;
- title/load jobs;
- chapter/overworld restore entry points;
- staged-state fields/commit paths;
- restart/save feature dependencies.

Deliver a function-level restore/re-port map before implementation.

**STOP FOR CONTROLLER REVIEW.**

## P2-T02 — Restore authoritative PC state semantics

**Model:** `GPT-5.6 Sol`
**Effort:** `ultra`
**Tier:** S3
**Prerequisite:** Approved P2-T01
**Controller gate:** YES

Requirements:

- no saved state stack becomes authoritative before required level/overworld structures exist;
- do not normalize invalid partial states by adding widespread null guards;
- restore one atomic logical transaction boundary;
- retain later save format/features independent of Android staging;
- retain restart feature intent;
- isolate Android progressive preparation outside live authoritative state.

Run targeted harness and full unit suite.

**STOP FOR CONTROLLER REVIEW.**

## P2-T03 — Remove obsolete staged-restore workarounds

**Model:** `GPT-5.6 Terra`
**Effort:** `high`
**Tier:** T2
**Prerequisite:** P2-T02 accepted
**Controller gate:** YES

Remove a guard only when tests prove the invalid staged condition is impossible. Keep genuinely useful defensive guards and document their independent invariant.

**STOP FOR CONTROLLER REVIEW.**

---

# 11. PHASE 3 — COMBAT LIFECYCLE SEMANTICS

## P3-T01 — Build combat lifecycle reference map

**Model:** `GPT-5.6 Sol`
**Effort:** `max`
**Tier:** S2
**Prerequisite:** Phase 2 accepted
**Controller gate:** YES

Compare reference/current behavior for:

- `SimpleCombat`;
- `MapCombat`;
- `BaseCombat`;
- `AnimationCombat`;
- arena paths;
- solver initialization/advancement;
- pre-combat hooks;
- action generation/application;
- playback;
- cleanup hooks;
- broken/unusable checks;
- EXP/promotion transitions;
- state-stack handling;
- `end_combat` ordering;
- transform animation preparation;
- battle music preparation.

Separate gameplay work from presentation/resource work.

**STOP FOR CONTROLLER REVIEW.**

## P3-T02 — Restore Simple/Map combat transaction ordering

**Model:** `GPT-5.6 Sol`
**Effort:** `ultra`
**Tier:** S3
**Prerequisite:** Approved P3-T01
**Controller gate:** YES

No yield/staging may expose an intermediate gameplay transaction to unrelated states. Preserve computational optimizations only when trace-equivalent.

**STOP FOR CONTROLLER REVIEW.**

## P3-T03 — Restore Base/Animation/Arena combat ordering

**Model:** `GPT-5.6 Sol`
**Effort:** `ultra`
**Tier:** S3
**Prerequisite:** P3-T02 accepted
**Controller gate:** YES

Retain Android battle-music streaming as platform implementation detail. Android progressive animation/resource preparation is allowed only outside authoritative gameplay transaction advancement.

**STOP FOR CONTROLLER REVIEW.**

## P3-T04 — Combat feature/fix preservation sweep

**Model:** `GPT-5.6 Terra`
**Effort:** `high`
**Tier:** T2
**Prerequisite:** P3-T03 accepted
**Controller gate:** YES

Verify preservation of:

- cleanup ordering;
- durability/use costs;
- promotion cancel/finalization semantics;
- skill cache invalidation;
- aura interactions;
- fast-forward behavior;
- combat-related debugger behavior.

**STOP FOR CONTROLLER REVIEW.**

---

# 12. PHASE 4 — TILEMAP / BOARD / EVENT ATOMICITY

## P4-T01 — Decompose staged tilemap optimization

**Model:** `GPT-5.6 Sol`
**Effort:** `max`
**Tier:** S2
**Prerequisite:** Phase 3 accepted
**Controller gate:** YES

Audit:

- `GameBoard.build_iter` and incremental helpers;
- `TilemapChangeJob`;
- batched tilemap transition state;
- aura/terrain/fog/region rebuilding;
- event render deferral;
- commit ordering.

Classify computational optimization versus scheduling semantic change.

**STOP FOR CONTROLLER REVIEW.**

## P4-T02 — Restore desktop atomic tilemap semantics

**Model:** `GPT-5.6 Sol`
**Effort:** `max`
**Tier:** S2
**Prerequisite:** Approved P4-T01
**Controller gate:** YES

Desktop preserves original synchronous logical behavior. Safe lookup/build optimizations may remain shared only when trace-equivalent.

**STOP FOR CONTROLLER REVIEW.**

## P4-T03 — Android-only progressive board preparation

**Model:** `GPT-5.6 Sol`
**Effort:** `max`
**Tier:** S2
**Prerequisite:** P4-T02 accepted
**Controller gate:** YES

Implement/retain only if profiling justifies it.

Required contract:

```text
LIVE OLD STATE
    -> build pending structures outside live world
    -> validate complete pending world
    -> one atomic logical commit
LIVE NEW STATE
```

Never point live `game` piecemeal at pending structures.

**STOP FOR CONTROLLER REVIEW.**

---

# 13. PHASE 5 — SAVE / LOAD / RESTART CONSOLIDATION

## P5-T01 — Save format and compatibility audit

**Model:** `GPT-5.6 Terra`
**Effort:** `high`
**Tier:** T2
**Prerequisite:** Phase 4 accepted
**Controller gate:** YES

Inventory/test:

- fields added since reference;
- event-state serialization;
- restart slots;
- chapter-start snapshot behavior;
- aura reconstruction requirements;
- save compatibility expectations;
- Android load orchestration dependencies.

**STOP FOR CONTROLLER REVIEW.**

## P5-T02 — Canonical transactional load API

**Model:** `GPT-5.6 Sol`
**Effort:** `ultra`
**Tier:** S3
**Prerequisite:** Approved P5-T01
**Controller gate:** YES

Implement one authoritative core load transaction. Android may prepare expensive resources around it but may not redefine when logical restore becomes visible.

**STOP FOR CONTROLLER REVIEW.**

## P5-T03 — Canonical restart contract

**Model:** `GPT-5.6 Sol`
**Effort:** `max`
**Tier:** S2
**Prerequisite:** P5-T02 accepted
**Controller gate:** YES

Preserve:

- restart current chapter;
- intended difficulty selection behavior;
- Test Chapter edge cases;
- game-over restart;
- debug-triggered restart.

Define pristine chapter-start state explicitly and prevent accidental mid-chapter state inheritance.

**STOP FOR CONTROLLER REVIEW.**

---

# 14. PHASE 6 — PLATFORM POLICY BOUNDARY

## P6-T01 — Define runtime capability interfaces

**Model:** `GPT-5.6 Sol`
**Effort:** `max`
**Tier:** S2
**Prerequisite:** Phase 5 accepted
**Controller gate:** YES

Prefer narrow capabilities over a giant platform abstraction.

Candidate boundaries:

- audio/music backend;
- resource load/preload policy;
- render/cache policy;
- frame-work budget policy;
- filesystem/build path handling.

Do not spread new `if is_android_runtime()` branches through gameplay-critical modules.

**STOP FOR CONTROLLER REVIEW.**

## P6-T02 — Migrate Android audio/resource policy

**Model:** `GPT-5.6 Terra`
**Effort:** `high`
**Tier:** T2
**Prerequisite:** Approved P6-T01
**Controller gate:** No

Keep Android streamed battle music where correct; implement approved interfaces without changing gameplay ordering.

## P6-T03 — Migrate accepted Android scheduling policy

**Model:** `GPT-5.6 Sol`
**Effort:** `max`
**Tier:** S2
**Prerequisite:** P6-T02
**Controller gate:** YES

Only migrate scheduling behavior already approved as safe. Any scheduling requiring gameplay core to tolerate partial state must be rejected/redesigned.

**STOP FOR CONTROLLER REVIEW.**

---

# 15. PHASE 7 — USER-FACING FEATURE PRESERVATION

## P7-T01 — Fast-forward equivalence suite

**Model:** `GPT-5.6 Terra`
**Effort:** `high`
**Tier:** T2
**Prerequisite:** Phase 6 accepted
**Controller gate:** YES

Compare identical seed/input with fast-forward ON/OFF. Must match actions, RNG outcomes, combat, XP, durability/costs, skills/statuses, events, and final state. Only presentation timing may differ.

**STOP FOR CONTROLLER REVIEW.**

## P7-T02 — Debugger parity PC/Android

**Model:** `GPT-5.6 Terra`
**Effort:** `medium`
**Tier:** T1
**Prerequisite:** P7-T01 accepted
**Controller gate:** YES

Verify intended debug operations including restart, chapter navigation, unit editing, auto-level, teleport, items, world values, and platform UI integration. Debugger enabled but idle must be observer-equivalent.

**STOP FOR CONTROLLER REVIEW.**

## P7-T03 — Profiler observer-equivalence

**Model:** `GPT-5.6 Luna`
**Effort:** `medium`
**Tier:** L2
**Prerequisite:** P7-T02 accepted
**Controller gate:** No

Verify profiler ON/OFF state equivalence and worker-thread scope isolation.

## P7-T04 — Save/load/restart UX regression sweep

**Model:** `GPT-5.6 Terra`
**Effort:** `high`
**Tier:** T2
**Prerequisite:** P7-T03
**Controller gate:** YES

Run feature-level scenarios on PC and Android pathways.

**STOP FOR CONTROLLER REVIEW.**

---

# 16. PHASE 8 — SAFE SHARED OPTIMIZATION REINTRODUCTION

Correctness must already be stable before optimizing.

## P8-T01 — Cache/memoization audit

**Model:** `GPT-5.6 Terra`
**Effort:** `high`
**Tier:** T2
**Controller gate:** YES

Criteria:

- correct invalidation;
- no hidden mutable-state dependence absent from cache keys;
- identical logical traces.

Preserve the existing LTCache invariant: invalidate after publishing mutable component state.

**STOP FOR CONTROLLER REVIEW.**

## P8-T02 — Render/cache/batching optimization audit

**Model:** `GPT-5.6 Terra`
**Effort:** `high`
**Tier:** T2
**Controller gate:** YES

Keep output-equivalent optimizations shared.

**STOP FOR CONTROLLER REVIEW.**

## P8-T03 — Allocation/redundant-work audit

**Model:** `GPT-5.6 Terra`
**Effort:** `medium`
**Tier:** T1
**Controller gate:** YES

Measure before/after where practical and require trace equality.

**STOP FOR CONTROLLER REVIEW.**

## P8-T04 — Android-only performance retuning

**Model:** `GPT-5.6 Sol`
**Effort:** `high`
**Tier:** S1
**Prerequisite:** P8-T01 through P8-T03 accepted
**Controller gate:** YES

Use profiler evidence. Optimize only behind accepted platform boundaries. No optimization is accepted solely on FPS improvement when behavioral trace changes.

**STOP FOR CONTROLLER REVIEW.**

---

# 17. PHASE 9 — FULL VALIDATION AND RELEASE CANDIDATE

## P9-T01 — Full PC regression matrix

**Model:** `GPT-5.6 Terra`
**Effort:** `high`
**Tier:** T2
**Controller gate:** YES

Run:

- full unit tests;
- applicable type checks;
- deterministic behavioral scenarios;
- representative project launches;
- save/load/restart flows;
- fast-forward/debugger checks.

No unexplained reference divergence.

**STOP FOR CONTROLLER REVIEW.**

## P9-T02 — Full Android regression/performance matrix

**Model:** `GPT-5.6 Terra`
**Effort:** `high`
**Tier:** T2
**Prerequisite:** P9-T01 accepted
**Controller gate:** YES

Compare Android synchronization-point traces against PC. Collect frame-time distribution, major stalls, memory-sensitive paths where measurable, and audio/resource behavior.

**STOP FOR CONTROLLER REVIEW.**

## P9-T03 — Architecture contamination audit

**Model:** `GPT-5.6 Sol`
**Effort:** `max`
**Tier:** S2
**Prerequisite:** P9-T02 accepted
**Controller gate:** YES

Search final code for:

- Android conditionals in gameplay-critical modules;
- staged/deferred fields in `GameState`;
- partial-state guards;
- worker-thread mutation of gameplay state;
- duplicate PC/Android gameplay implementations;
- yield/generator boundaries inside logical transactions;
- recovery TODO/FIXME markers.

Every remaining case requires justification.

**STOP FOR CONTROLLER REVIEW.**

## P9-T04 — Final release candidate review

**Model:** `GPT-5.6 Sol`
**Effort:** `ultra`
**Tier:** S3
**Prerequisite:** P9-T03 accepted
**Controller gate:** FINAL

Codex must not merge to `master` unless the user explicitly instructs it after controller approval.

Deliver:

- final commit range;
- architecture summary;
- preserved feature list;
- removed/replaced staging list;
- known limitations;
- PC behavior-equivalence evidence;
- Android behavior-equivalence evidence;
- performance comparison;
- full test results;
- recommended merge strategy.

**STOP FOR FINAL CONTROLLER APPROVAL.**

---

# 18. UNIVERSAL STOP CONDITIONS

Codex must immediately stop and report rather than improvise if any of the following occurs:

1. Current model does not exactly match the task model gate.
2. Current effort does not exactly match the task effort gate.
3. Required model/effort cannot be detected.
4. Required model/effort is unavailable.
5. A prerequisite/controller gate is not approved.
6. Recovery work is requested directly on `master`.
7. A proposed fix intentionally changes PC behavioral semantics without controller approval.
8. A test shows the PC reference contains a later-fixed bug and classification is unclear.
9. An optimization changes RNG consumption/order or gameplay action ordering.
10. An Android optimization requires shared core to expose/tolerate partial state.
11. Save compatibility requires a migration/format decision outside the task.
12. A task would edit protected project content only to make an engine test pass.
13. Scope expands into another major subsystem not named in the task.
14. Required tests cannot be run.
15. Evidence contradicts an assumption in this plan.
16. A destructive Git operation appears necessary.

On stop, provide evidence and request controller guidance through the user.

---

# 19. CHANGE DISCIPLINE

## Commit discipline

Prefer one conceptual change per commit. Suggested prefixes:

- `test(recovery): ...`
- `refactor(core): ...`
- `fix(core): ...`
- `perf(shared): ...`
- `perf(android): ...`
- `refactor(android): ...`
- `docs(recovery): ...`

Never combine project content changes with engine recovery commits.

## Diff discipline

Before finishing each task:

- inspect the complete diff;
- ensure generated files were not hand-edited incorrectly;
- remove unrelated formatting churn;
- remove temporary debug output/files;
- verify tests assert invariants rather than implementation details only.

## Test discipline

A regression test should fail for the broken semantic condition and pass for the recovered one. Prefer state assertions over "does not crash" tests.

Because tests share the global `game` singleton, every new test touching `game` must initialize/reset each state element it relies on.

---

# 20. PERFORMANCE ACCEPTANCE RULES

Correctness is evaluated before performance for each affected task.

Where feasible record:

- workload/scenario;
- PC baseline;
- Android baseline;
- before/after median frame or operation time;
- p95/p99 or worst meaningful stall;
- semantic trace equality result;
- material memory tradeoff.

A performance win with semantic divergence is a FAIL.

A temporary performance regression may be accepted during semantic recovery but must be recorded for Phase 8.

---

# 21. CONTROLLER DECISION LOG

| Date | Decision | Scope | Rationale |
|---|---|---|---|
| 2026-08-08 | Use `9314f54b` as initial PC behavioral reference | Core gameplay | Last clear pre-Android behavioral baseline before `52bd0403`; behavioral reference only, not wholesale rollback. |
| 2026-08-08 | Recovery starts from current HEAD `0821182a` | Entire repo | Preserve project content, later features, fixes, assets, and Android support. |
| 2026-08-08 | One shared gameplay core | Architecture | Prevent long-term PC/Android behavioral forks. |
| 2026-08-08 | Android specialization only behind semantic boundaries | Android | Preserve Android performance without partial live gameplay state. |
| 2026-08-08 | Preserve fast-forward, PC/Android debugger, profiler, restart, save/load enhancements | Features | Explicit product requirements. |
| 2026-08-08 | Replace obsolete GPT-5.3-Codex/Spark assignment with GPT-5.6 Sol/Terra/Luna model+effort gates | Process | Allocate Sol to high-blast-radius reasoning, Terra to bounded engineering, Luna to low-risk mechanical work. |
| 2026-08-08 | Exact model AND exact effort are controller gates | Process | Prevent both underpowered execution and unnecessary token expenditure. |

---

# 22. CURRENT EXECUTION STATE

**Current phase:** Phase 0

**Next authorized task:** `P0-T01` only.

No later task is authorized until required preceding reports are reviewed.

**P0-T01 required model:** `GPT-5.6 Luna`

**P0-T01 required effort:** `medium`

If Codex is running any other model or effort, it must STOP and ask the user to switch to exactly `GPT-5.6 Luna` with `medium` effort.

---

# 23. SHORT FORM CODEX REMINDER

1. Read `AGENTS.md`, `AGENTS.override.md`, and `plan.md` first.
2. Work only on the authorized recovery branch/task.
3. Enforce exact GPT-5.6 model and exact effort; mismatch means STOP.
4. PC gameplay semantics are authoritative unless controller approves a later correctness fix.
5. Preserve intended features and independent bugfixes.
6. Shared optimizations must be trace-equivalent.
7. Android-only optimization belongs behind platform policy and cannot expose partial gameplay state.
8. Do not self-advance through controller gates.
9. Report evidence, tests, risks, and commit SHA.
10. If semantics are unclear, STOP and escalate instead of inventing architecture.
