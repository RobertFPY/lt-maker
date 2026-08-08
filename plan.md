# PC Core Semantics Recovery — Master Execution Plan

> **Status:** ACTIVE
> **Plan owner / controller:** ChatGPT (planner, reviewer, gatekeeper)
> **Executor:** Codex (implementation agent only)
> **Recovery branch:** `recovery/pc-core-semantics`
> **PC behavioral reference:** `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`
> **Recovery starting HEAD:** `0821182a717de2baaf52a699ee325241ffaddd03`
> **Android introduction / mixed-change landmark:** `52bd040317f16b7973602dd78e769ed990501549`
> **Model policy:** GPT-5.6 token-optimized execution policy v2
> **Policy date:** 2026-08-08

---

# 0. PURPOSE AND AUTHORITY

This file is the authoritative execution plan for restoring the gameplay core to the original PC semantics while preserving later features, correctness fixes, safe shared optimizations, and Android-specific optimizations that do not alter gameplay behavior.

Codex is an **executor**, not the project architect. Codex must not redesign this plan, widen task scope, skip gates, accept behavioral divergence for performance, or decide that a workaround is acceptable without controller approval.

The controller is responsible for:

- architecture and semantic decisions;
- selecting the active task;
- selecting the primary model/effort and escalation target;
- approving phase transitions;
- reviewing diffs, tests, traces, benchmarks, and regressions;
- deciding whether an optimization is behavior-preserving;
- deciding whether Android-only specialization is acceptable;
- deciding whether a workaround is removed, retained, or rewritten;
- approving escalation when a task exceeds the primary model's safe scope.

Codex is responsible for:

- reading repository instructions and this plan before every task;
- executing exactly one authorized task packet;
- staying inside the authorized scope;
- writing tests/diagnostics required by that task;
- running the specified verification;
- reporting evidence and unresolved risks;
- stopping at controller or escalation gates.

The user is the bridge between Codex and the controller when review or model switching is required.

---

# 1. MANDATORY CODEX SESSION PROTOCOL

Before editing any file, Codex must:

1. Read root `AGENTS.md` in full.
2. Read root `AGENTS.override.md` in full if present.
3. Read this entire `plan.md`.
4. Identify the exact authorized task ID.
5. Read the task's **PRIMARY MODEL**, **PRIMARY EFFORT**, and **ESCALATION TARGET**.
6. Detect and state the current model and reasoning effort.
7. Inspect `git status`, current branch, and current HEAD.
8. Verify prerequisites and controller gates.
9. Refuse recovery work directly on `master`.
10. Enforce the primary model/effort gate unless the controller explicitly authorized escalation for the current task.

Before implementation, print:

```text
TASK: <ID>
PRIMARY MODEL: <model>
PRIMARY EFFORT: <effort>
CURRENT MODEL: <detected model>
CURRENT EFFORT: <detected effort>
ESCALATION TARGET: <model + effort or NONE>
ESCALATION AUTHORIZED: YES | NO
BRANCH: <branch>
HEAD: <sha>
SCOPE: <files/modules>
INVARIANTS: <INV ids>
PREREQUISITES: <task ids / controller approvals>
```

If the current model or effort cannot be detected, STOP before editing.

## 1.1 Primary model gate

The primary model is the **cheapest model judged sufficient to start the task safely**.

Codex must start with the exact primary model and exact primary effort unless the controller explicitly authorized an escalation for this task.

A stronger model is **not automatically authorized**. If the task says `GPT-5.6 Terra / medium` and Codex is running `GPT-5.6 Sol / max`, STOP and request the primary configuration. This prevents unnecessary token expenditure.

On mismatch:

```text
MODEL GATE FAILED
Task: <ID>
Required primary: <model / effort>
Current: <model / effort>
Action: switch to the required primary configuration, or provide explicit controller escalation authorization.
```

Then STOP without edits.

## 1.2 Escalation gate

Codex must never self-escalate.

If an escalation condition is reached:

1. stop editing;
2. preserve current work without expanding scope;
3. run any safe diagnostics already authorized;
4. report the exact evidence;
5. request the task's escalation target;
6. wait for the user/controller to authorize the new model/effort.

Required output:

```text
MODEL ESCALATION REQUIRED
TASK: <ID>
PRIMARY: <model / effort>
REQUESTED ESCALATION: <model / effort>
TRIGGER: <named escalation condition>
EVIDENCE:
- ...
SAFE WORK COMPLETED:
- ...
UNRESOLVED:
- ...
ACTION: switch model/effort only after controller authorization.
```

## 1.3 Global escalation conditions

Escalation is justified only when at least one of these is true:

- **ESC-01 Reference ambiguity:** PC reference behavior cannot be determined unambiguously from code/tests/traces.
- **ESC-02 Nonlocal root cause:** a failure crosses a second correctness-critical subsystem not in the original bounded implementation.
- **ESC-03 Trace divergence:** deterministic logical traces diverge after a locally correct implementation and the cause is not presentation-only.
- **ESC-04 Competing semantics:** two plausible implementations produce different gameplay semantics.
- **ESC-05 Invariant failure:** the first safe implementation exposes a deeper invariant violation rather than a local coding defect.
- **ESC-06 Save compatibility conflict:** preserving old/current save behavior requires a format or migration decision.
- **ESC-07 Android boundary conflict:** the desired performance gain appears to require partial live gameplay state or changed gameplay ordering.
- **ESC-08 Repeated local failure:** one bounded repair plus one bounded correction still cannot satisfy the task's acceptance tests.
- **ESC-09 Unplanned architecture:** implementation requires a new cross-cutting abstraction or architectural choice not already approved.
- **ESC-10 Release reconciliation:** final evidence from multiple subsystems conflicts and requires global prioritization.

Do not escalate merely because a task is large, test execution is slow, or a stronger model is available.

## 1.4 Availability rule

If the required primary or authorized escalation model/effort is unavailable in the current Codex environment, STOP and report it. Do not choose a substitute yourself.

## 1.5 Branch rule

Recovery implementation must occur on:

`recovery/pc-core-semantics`

or a short-lived child branch explicitly authorized by the controller.

Never force-push, rewrite shared history, reset `master`, or perform a broad revert unless an active task explicitly authorizes it.

## 1.6 No autonomous phase advancement

Completing one task does not authorize another.

At every **CONTROLLER GATE**, Codex must stop after its report. The user/controller later supplies the next authorized task ID.

## 1.7 No silent substitutions

Codex must never silently:

- substitute a different model or effort;
- weaken a failing test;
- change acceptance criteria;
- update reference/golden behavior to match a regression;
- preserve an optimization merely because it improves FPS;
- remove a desired feature because recovery is difficult;
- modify project content/assets to make engine tests pass unless explicitly authorized;
- expand a local task into an architectural refactor.

---

# 2. GPT-5.6 TOKEN-OPTIMIZED MODEL POLICY

The allocation rule is:

```text
Luna  -> mechanical / deterministic / report / repetitive verification
Terra -> default coding workhorse for bounded engineering
Sol   -> semantic architecture, nonlocal debugging, high-blast-radius reconciliation
Ultra -> escalation only, not a default coding mode
```

Reasoning effort is a **budget**, not a prestige setting.

## 2.1 Luna

Use `GPT-5.6 Luna` when the task is deterministic, low-risk, and its desired output is already structurally known.

Typical use:

- baseline capture;
- running existing test matrices;
- report generation;
- profiler observer checks;
- repetitive tests following an approved pattern;
- mechanical documentation/cleanup.

Default efforts:

- `low` for deterministic collection/verification;
- `medium` when repository reasoning is needed but no semantic choice is allowed.

Luna must escalate rather than make architectural decisions.

## 2.2 Terra

Use `GPT-5.6 Terra` as the **default coder**.

Typical use:

- implementing an approved design;
- regression harnesses;
- compatibility audits;
- localized refactors with explicit contracts;
- feature preservation;
- Android adapters behind approved interfaces;
- performance/cache audits with clear invariants;
- semantic inventory where classification rules are already defined.

Default efforts:

- `medium` for routine bounded engineering;
- `high` for difficult bounded work or one sensitive subsystem.

Terra should be preferred over Sol whenever architecture is already frozen and the task can be verified by explicit tests/traces.

## 2.3 Sol

Use `GPT-5.6 Sol` only when the task requires semantic judgment with meaningful blast radius.

Typical use:

- authoritative `GameState` transaction semantics;
- combat lifecycle reconciliation;
- canonical load transaction semantics;
- ambiguous PC-vs-current behavior;
- Android scheduling boundaries that may leak partial state;
- nonlocal regression debugging;
- final architecture contamination/release reconciliation.

Default efforts:

- `high` for difficult cross-system implementation after architecture is known;
- `max` for architecture-critical reasoning/reconciliation;
- `ultra` only as an escalation target for unresolved, high-blast-radius conflicts.

## 2.4 Cost discipline

A task should be assigned to the lowest tier that can safely satisfy its acceptance tests.

Before upgrading model or effort, prefer:

1. narrowing scope;
2. using the existing behavioral trace;
3. adding a deterministic failing test;
4. comparing directly with `9314f54b`;
5. collecting targeted profiler or state evidence.

Only then escalate if a Section 1.3 condition applies.

---

# 3. NON-NEGOTIABLE SYSTEM INVARIANTS

These invariants override performance goals.

## INV-01 — One gameplay core

PC and Android share one authoritative gameplay implementation. Do not create separate gameplay engines.

## INV-02 — PC semantics are the behavioral reference

For systems that existed before Android work, `9314f54b` is the initial behavioral reference unless a later independent correctness fix or explicitly preserved feature supersedes it.

The reference is behavioral, not textual. Do not blindly copy old files.

## INV-03 — No observable partial gameplay state

Live gameplay code must never observe a half-restored or half-built state.

Forbidden examples include:

- restored map state while level/tilemap is missing;
- camera/map state active before the map is valid;
- board swapped before aura/fog/regions are valid;
- combat hooks split so unrelated logic observes an intermediate combat transaction.

## INV-04 — Android may optimize platform policy, not gameplay ordering

Android may differ in rendering, frame presentation, audio streaming, resource preload, memory/cache policy, filesystem/build integration, and background preparation that does not mutate authoritative gameplay state.

Android must not differ in combat solver semantics, action/event/RNG/hook ordering, logical state-machine transitions, or final logical state at synchronization points.

## INV-05 — Shared optimizations must be behavior-preserving

Shared optimizations require equivalent logical traces and output semantics.

## INV-06 — Fast-forward changes time, not outcomes

Identical seed/input with fast-forward ON and OFF must produce the same logical action trace and final game state. Only waits/presentation timing may differ.

## INV-07 — Debugger and profiler are observers

Enabling debugger/profiler without a mutating debug command must not change gameplay behavior, state ordering, RNG, or cache validity.

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
- **REWRITE-PLATFORM** — Android goal is valid but implementation contaminates core semantics.
- **RESTORE-PC-SEMANTICS** — current implementation alters gameplay/lifecycle semantics.
- **REMOVE-WORKAROUND** — workaround exists only because an invalid staged/partial state was introduced.
- **KEEP-CORRECTNESS-FIX** — later fix repairs a real invariant independent of Android.

---

# 5. HIGH-RISK COMMIT / SUBSYSTEM MAP

Strong keep candidates:

- `7735ca29` — hierarchical runtime profiling.
- `6631e736` — debugger/render-panel performance work, subject to parity tests.
- `97c58a63` — difficulty setup correctness fix.
- `a566ae6d` — Windows editor workspace fix.
- `d2bbd026` — Android profiler thread isolation.
- `9004c67b` — Android streamed battle music as platform behavior.
- Android build/config/tooling that does not alter gameplay semantics.
- Project content/resource changes.

High-risk recovery cluster:

- `cdd4be2a` — staged tilemap board rebuild.
- `6b96e2f1` — batched tilemap transition state.
- `78acb08a` through `fff0145d` — staged combat sequence.
- `390638ac` — camera guard during staged restore.
- `6bd9da4b` — map-safety guards for staged loading.
- `8306e1a9` — deferred saved state until level restore completes.

`52bd0403` is a mixed commit. Never revert it wholesale.

---

# 6. SYNCHRONIZATION POINTS

PC and Android logical state must match at synchronization points regardless of presentation timing.

Examples:

- after level load fully commits;
- before player control begins;
- after movement commits;
- after combat cleanup/state-stack handling completes;
- after an event command transaction completes;
- after tilemap change commits;
- after save restore commits;
- after chapter restart reaches playable state;
- after phase transition completes.

Compare logical state at synchronization points, not arbitrary render frames.

---

# 7. CODEX TASK REPORT FORMAT

After each task:

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
ESCALATION TRIGGERS ENCOUNTERED:
COMMIT SHA:
NEXT ACTION: CONTROLLER REVIEW | NONE
```

Never claim PASS if required tests were skipped.

---

# 8. PHASE 0 — BASELINE, INVENTORY, SAFETY RAILS

## P0-T01 — Capture recovery baseline

**Primary:** `GPT-5.6 Luna / low`
**Escalation:** `GPT-5.6 Terra / medium`
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

Escalate only if repository state/history is inconsistent with the plan or baseline collection exposes unexplained structural divergence.

Acceptance:

- baseline report committed;
- no engine behavior changes;
- existing test failures recorded and categorized, not fixed.

## P0-T02 — Build post-reference semantic change inventory

**Primary:** `GPT-5.6 Terra / medium`
**Escalation:** `GPT-5.6 Sol / high`
**Prerequisite:** P0-T01
**Controller gate:** YES

Tasks:

- inspect changed engine/runtime files after `9314f54b`;
- classify changes using Section 4;
- identify mixed changes within commits;
- inventory `is_android_runtime`, render optimization gates, staged jobs, generators/yields, worker threads, and deferred commits;
- create `recovery/change_inventory.md`.

Escalate on ESC-01, ESC-02, ESC-04, or ESC-09.

Acceptance:

- every correctness-critical changed engine file classified;
- uncertain cases marked `NEEDS-CONTROLLER-DECISION`;
- no production behavior changes.

**STOP FOR CONTROLLER REVIEW.**

---

# 9. PHASE 1 — BEHAVIORAL REGRESSION HARNESS

## P1-T01 — Design deterministic trace schema

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
**Prerequisite:** Approved P0-T02
**Controller gate:** YES

Design synchronization-point tracing for:

- state stack nids;
- active level/overworld;
- unit logical state;
- positions, HP, mana, statuses, skills, inventory/durability;
- relevant game/level vars;
- RNG checkpoints where feasible;
- combat playback/action sequence;
- triggered event IDs/order;
- turn/phase;
- tilemap/board identity and invariants;
- save/load/restart completion state.

Do not use frame count, audio objects, surfaces, or volatile presentation state as equality criteria.

Escalate if trace design itself requires new core lifecycle semantics or reference behavior is ambiguous.

**STOP FOR CONTROLLER REVIEW.**

## P1-T02 — Implement trace/test harness

**Primary:** `GPT-5.6 Terra / medium`
**Escalation:** `GPT-5.6 Sol / high`
**Prerequisite:** Approved P1-T01
**Controller gate:** No

Implement approved design with minimal production intrusion.

Escalate if instrumentation changes lifecycle ordering or requires invasive cross-system hooks.

## P1-T03 — Establish PC-reference golden scenarios

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
**Prerequisite:** P1-T02
**Controller gate:** YES

Minimum scenarios:

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
17. Debugger disabled/enabled observer equivalence.
18. Game-over/restart.

Escalate on reference ambiguity, conflicting traces, or cross-subsystem invariant failure.

Do not modify expected PC behavior to make current code pass.

**STOP FOR CONTROLLER REVIEW.**

---

# 10. PHASE 2 — GAMESTATE AND STATE-MACHINE ATOMICITY

## P2-T01 — Audit GameState/load/state-restore delta

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
**Prerequisite:** Approved Phase 1 harness
**Controller gate:** YES

Focus:

- `app/engine/game_state.py`;
- state machine files;
- title/load jobs;
- chapter/overworld restore entry points;
- staged-state fields/commit paths;
- restart/save dependencies.

Deliver a function-level restore/re-port map before implementation.

Escalate on ESC-01, ESC-02, ESC-04, or ESC-09.

**STOP FOR CONTROLLER REVIEW.**

## P2-T02 — Restore authoritative PC state semantics

**Primary:** `GPT-5.6 Sol / max`
**Escalation:** `GPT-5.6 Sol / ultra`
**Prerequisite:** Approved P2-T01
**Controller gate:** YES

Requirements:

- no saved state stack becomes authoritative before required level/overworld structures exist;
- do not normalize invalid partial states with widespread null guards;
- restore one atomic logical transaction boundary;
- retain later save format/features independent of Android staging;
- retain restart intent;
- isolate Android progressive preparation outside live authoritative state.

Escalate to `ultra` only on ESC-02, ESC-03, ESC-04, ESC-05, ESC-06, ESC-08, or ESC-09.

Run targeted harness and full unit suite.

**STOP FOR CONTROLLER REVIEW.**

## P2-T03 — Remove obsolete staged-restore workarounds

**Primary:** `GPT-5.6 Terra / medium`
**Escalation:** `GPT-5.6 Sol / high`
**Prerequisite:** P2-T02 accepted
**Controller gate:** YES

Remove a guard only when tests prove the invalid staged condition is impossible. Keep independently useful defensive guards.

Escalate if removing a workaround reveals a nonlocal state invariant failure.

**STOP FOR CONTROLLER REVIEW.**

---

# 11. PHASE 3 — COMBAT LIFECYCLE SEMANTICS

## P3-T01 — Build combat lifecycle reference map

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
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

Escalate if class interactions make ordering ambiguous or the reference itself conflicts with later correctness fixes.

**STOP FOR CONTROLLER REVIEW.**

## P3-T02 — Restore Simple/Map combat transaction ordering

**Primary:** `GPT-5.6 Sol / max`
**Escalation:** `GPT-5.6 Sol / ultra`
**Prerequisite:** Approved P3-T01
**Controller gate:** YES

No yield/staging may expose an intermediate gameplay transaction to unrelated states. Preserve computational optimizations only when trace-equivalent.

Escalate to `ultra` only for unresolved cross-class/nonlocal trace divergence after one bounded correction.

**STOP FOR CONTROLLER REVIEW.**

## P3-T03 — Restore Base/Animation/Arena combat ordering

**Primary:** `GPT-5.6 Sol / max`
**Escalation:** `GPT-5.6 Sol / ultra`
**Prerequisite:** P3-T02 accepted
**Controller gate:** YES

Retain Android battle-music streaming as a platform implementation detail. Progressive animation/resource preparation is allowed only outside authoritative gameplay advancement.

Escalate to `ultra` only when shared class inheritance/order creates unresolved semantic conflict.

**STOP FOR CONTROLLER REVIEW.**

## P3-T04 — Combat feature/fix preservation sweep

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / high`
**Prerequisite:** P3-T03 accepted
**Controller gate:** YES

Verify:

- cleanup ordering;
- durability/use costs;
- promotion cancel/finalization;
- skill cache invalidation;
- aura interactions;
- fast-forward behavior;
- combat-related debugger behavior.

Escalate if a failure requires changing combat lifecycle architecture rather than re-porting a bounded feature/fix.

**STOP FOR CONTROLLER REVIEW.**

---

# 12. PHASE 4 — TILEMAP / BOARD / EVENT ATOMICITY

## P4-T01 — Decompose staged tilemap optimization

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
**Prerequisite:** Phase 3 accepted
**Controller gate:** YES

Audit:

- `GameBoard.build_iter` and incremental helpers;
- `TilemapChangeJob`;
- batched tilemap transition;
- aura/terrain/fog/region rebuilding;
- event render deferral;
- commit ordering.

Classify computational optimization versus scheduling semantic change.

Escalate if the existing staged architecture prevents a clean classification.

**STOP FOR CONTROLLER REVIEW.**

## P4-T02 — Restore desktop atomic tilemap semantics

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
**Prerequisite:** Approved P4-T01
**Controller gate:** YES

Desktop preserves original synchronous logical behavior. Safe build/lookup optimizations remain shared only when trace-equivalent.

Escalate if board/tilemap/aura/fog ordering has ambiguous transactional boundaries.

**STOP FOR CONTROLLER REVIEW.**

## P4-T03 — Android-only progressive board preparation

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
**Prerequisite:** P4-T02 accepted
**Controller gate:** YES

Retain/implement only if profiling justifies it.

Required contract:

```text
LIVE OLD STATE
    -> build pending structures outside live world
    -> validate complete pending world
    -> one atomic logical commit
LIVE NEW STATE
```

Never point live `game` piecemeal at pending structures.

Escalate immediately on ESC-07 or if atomic commit requires new cross-cutting lifecycle architecture.

**STOP FOR CONTROLLER REVIEW.**

---

# 13. PHASE 5 — SAVE / LOAD / RESTART CONSOLIDATION

## P5-T01 — Save format and compatibility audit

**Primary:** `GPT-5.6 Terra / medium`
**Escalation:** `GPT-5.6 Sol / high`
**Prerequisite:** Phase 4 accepted
**Controller gate:** YES

Inventory/test:

- fields added since reference;
- event-state serialization;
- restart slots;
- chapter-start snapshot behavior;
- aura reconstruction;
- old/current save compatibility;
- Android load orchestration dependencies.

Escalate on ESC-06 or ambiguous legacy behavior.

**STOP FOR CONTROLLER REVIEW.**

## P5-T02 — Canonical transactional load API

**Primary:** `GPT-5.6 Sol / max`
**Escalation:** `GPT-5.6 Sol / ultra`
**Prerequisite:** Approved P5-T01
**Controller gate:** YES

Implement one authoritative core load transaction. Android may prepare expensive resources around it but may not redefine when logical restore becomes visible.

Escalate to `ultra` only on unresolved save-format/lifecycle conflict, nonlocal invariant failure, or competing semantic designs.

**STOP FOR CONTROLLER REVIEW.**

## P5-T03 — Canonical restart contract

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
**Prerequisite:** P5-T02 accepted
**Controller gate:** YES

Preserve:

- restart current chapter;
- intended difficulty selection;
- Test Chapter edge cases;
- game-over restart;
- debug-triggered restart.

Define pristine chapter-start state explicitly and prevent accidental mid-chapter inheritance.

Escalate if restart semantics require changes to the canonical load transaction.

**STOP FOR CONTROLLER REVIEW.**

---

# 14. PHASE 6 — PLATFORM POLICY BOUNDARY

## P6-T01 — Define runtime capability interfaces

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
**Prerequisite:** Phase 5 accepted
**Controller gate:** YES

Prefer narrow capabilities over a giant platform abstraction.

Candidate boundaries:

- audio/music backend;
- resource load/preload policy;
- render/cache policy;
- frame-work budget policy;
- filesystem/build handling.

Do not spread new `if is_android_runtime()` branches through gameplay-critical modules.

Escalate if the boundary affects authoritative gameplay lifecycle or requires a new cross-cutting architecture.

**STOP FOR CONTROLLER REVIEW.**

## P6-T02 — Migrate Android audio/resource policy

**Primary:** `GPT-5.6 Terra / medium`
**Escalation:** `GPT-5.6 Sol / high`
**Prerequisite:** Approved P6-T01
**Controller gate:** No

Keep Android streamed battle music where correct; implement approved interfaces without changing gameplay ordering.

Escalate if resource policy unexpectedly mutates/advances live gameplay state.

## P6-T03 — Migrate accepted Android scheduling policy

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
**Prerequisite:** P6-T02
**Controller gate:** YES

Only migrate scheduling behavior already approved as safe. Any scheduling requiring gameplay core to tolerate partial state is rejected/redesigned.

Escalate immediately on ESC-07.

**STOP FOR CONTROLLER REVIEW.**

---

# 15. PHASE 7 — USER-FACING FEATURE PRESERVATION

## P7-T01 — Fast-forward equivalence suite

**Primary:** `GPT-5.6 Terra / medium`
**Escalation:** `GPT-5.6 Sol / high`
**Prerequisite:** Phase 6 accepted
**Controller gate:** YES

Compare identical seed/input with fast-forward ON/OFF. Actions, RNG outcomes, combat, XP, durability/costs, skills/statuses, events, and final state must match. Only presentation timing may differ.

Escalate if divergence is nonlocal or appears inside restored combat/state-machine semantics.

**STOP FOR CONTROLLER REVIEW.**

## P7-T02 — Debugger parity PC/Android

**Primary:** `GPT-5.6 Luna / medium`
**Escalation:** `GPT-5.6 Terra / high`
**Prerequisite:** P7-T01 accepted
**Controller gate:** YES

Verify intended debug operations including restart, chapter navigation, unit editing, auto-level, teleport, items, world values, and platform UI integration. Debugger enabled but idle must be observer-equivalent.

Escalate if fixing a debugger defect requires gameplay-core semantic changes.

**STOP FOR CONTROLLER REVIEW.**

## P7-T03 — Profiler observer-equivalence

**Primary:** `GPT-5.6 Luna / low`
**Escalation:** `GPT-5.6 Terra / medium`
**Prerequisite:** P7-T02 accepted
**Controller gate:** No

Verify profiler ON/OFF state equivalence and worker-thread scope isolation.

Escalate if instrumentation changes shared state or thread/lifecycle ordering.

## P7-T04 — Save/load/restart UX regression sweep

**Primary:** `GPT-5.6 Terra / medium`
**Escalation:** `GPT-5.6 Sol / high`
**Prerequisite:** P7-T03
**Controller gate:** YES

Run feature-level scenarios on PC and Android pathways.

Escalate if failure traces point back to canonical load/restart architecture rather than UX integration.

**STOP FOR CONTROLLER REVIEW.**

---

# 16. PHASE 8 — SAFE SHARED OPTIMIZATION REINTRODUCTION

Correctness must already be stable before optimizing.

## P8-T01 — Cache/memoization audit

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / high`
**Controller gate:** YES

Criteria:

- correct invalidation;
- no hidden mutable-state dependence absent from cache keys;
- identical logical traces.

Preserve the LTCache invariant: invalidate after publishing mutable component state.

Escalate if cache correctness depends on nonlocal lifecycle semantics.

**STOP FOR CONTROLLER REVIEW.**

## P8-T02 — Render/cache/batching optimization audit

**Primary:** `GPT-5.6 Terra / medium`
**Escalation:** `GPT-5.6 Sol / high`
**Controller gate:** YES

Keep output-equivalent optimizations shared.

Escalate if render optimization changes logical update scheduling or state visibility.

**STOP FOR CONTROLLER REVIEW.**

## P8-T03 — Allocation/redundant-work audit

**Primary:** `GPT-5.6 Terra / medium`
**Escalation:** `GPT-5.6 Sol / high`
**Controller gate:** YES

Measure before/after where practical and require trace equality.

Escalate only if optimization requires changing shared lifecycle boundaries.

**STOP FOR CONTROLLER REVIEW.**

## P8-T04 — Android-only performance retuning

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
**Prerequisite:** P8-T01 through P8-T03 accepted
**Controller gate:** YES

Use profiler evidence. Optimize only behind accepted platform boundaries. No optimization is accepted solely on FPS improvement if behavioral traces differ.

Escalate on ESC-07, nonlocal regressions, or conflict between performance target and semantic invariants.

**STOP FOR CONTROLLER REVIEW.**

---

# 17. PHASE 9 — FULL VALIDATION AND RELEASE CANDIDATE

## P9-T01 — Full PC regression matrix

**Primary:** `GPT-5.6 Luna / medium`
**Escalation:** `GPT-5.6 Terra / high`
**Controller gate:** YES

Run:

- full unit tests;
- applicable type checks;
- deterministic behavioral scenarios;
- representative project launches;
- save/load/restart flows;
- fast-forward/debugger checks.

No unexplained reference divergence.

Escalate only to diagnose failures; do not use Terra merely to run known tests.

**STOP FOR CONTROLLER REVIEW.**

## P9-T02 — Full Android regression/performance matrix

**Primary:** `GPT-5.6 Terra / medium`
**Escalation:** `GPT-5.6 Sol / high`
**Prerequisite:** P9-T01 accepted
**Controller gate:** YES

Compare Android synchronization-point traces against PC. Collect frame-time distribution, major stalls, memory-sensitive paths where measurable, and audio/resource behavior.

Escalate on unexplained semantic divergence or platform-boundary conflict.

**STOP FOR CONTROLLER REVIEW.**

## P9-T03 — Architecture contamination audit

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
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

Escalate if remaining contamination requires architecture-level reconciliation rather than local cleanup.

**STOP FOR CONTROLLER REVIEW.**

## P9-T04 — Final release candidate review

**Primary:** `GPT-5.6 Sol / max`
**Escalation:** `GPT-5.6 Sol / ultra`
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

Escalate to `ultra` only on ESC-10 or unresolved high-blast-radius conflicts across multiple accepted subsystems.

**STOP FOR FINAL CONTROLLER APPROVAL.**

---

# 18. UNIVERSAL STOP CONDITIONS

Codex must stop and report rather than improvise if:

1. current model/effort does not match the task's primary configuration and no explicit escalation is authorized;
2. required model/effort cannot be detected or is unavailable;
3. a prerequisite/controller gate is not approved;
4. recovery work is requested directly on `master`;
5. a proposed fix intentionally changes PC behavioral semantics without approval;
6. the PC reference contains a later-fixed bug and classification is unclear;
7. an optimization changes RNG/action/event/hook ordering;
8. an Android optimization requires partial live gameplay state;
9. save compatibility requires an unapproved migration/format decision;
10. protected project content would be edited only to make an engine test pass;
11. scope expands into another major subsystem;
12. required tests cannot be run;
13. evidence contradicts an assumption in this plan;
14. a destructive Git operation appears necessary;
15. a Section 1.3 escalation condition is reached.

---

# 19. CHANGE DISCIPLINE

## Commit discipline

Prefer one conceptual change per commit.

Suggested prefixes:

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
- verify tests assert invariants, not only implementation details.

## Test discipline

A regression test should fail for the broken semantic condition and pass for the recovered one. Prefer state assertions over "does not crash" tests.

Because tests share the global `game` singleton, every new test touching `game` must initialize/reset each state element it relies on.

---

# 20. PERFORMANCE ACCEPTANCE RULES

Correctness is evaluated before performance.

Where feasible record:

- workload/scenario;
- PC baseline;
- Android baseline;
- before/after median operation/frame time;
- p95/p99 or worst meaningful stall;
- semantic trace equality;
- material memory tradeoff.

A performance win with semantic divergence is a FAIL.

A temporary performance regression may be accepted during semantic recovery but must be recorded for Phase 8.

---

# 21. TOKEN-BUDGET ACCEPTANCE RULES

The model allocation itself is part of project efficiency.

For each task report, Codex must state whether escalation was needed.

Rules:

- Do not use Sol for deterministic execution that Luna/Terra can verify.
- Do not use `ultra` as a default task setting.
- Do not re-read large unrelated files after the task scope is established.
- Prefer targeted file/function diffs over whole-repository exploration.
- Prefer one failing deterministic test over broad speculative debugging.
- Prefer direct baseline-vs-current comparisons over reconstructing behavior from memory.
- Stop after the task acceptance criteria are met; do not perform opportunistic refactors.
- Reuse approved harnesses and reports rather than regenerating equivalent analysis.
- If a task can be split into a cheap evidence-gathering subtask and an expensive reasoning subtask, gather evidence first.

The controller may downgrade future task assignments when earlier phases reduce uncertainty.

---

# 22. CONTROLLER DECISION LOG

| Date | Decision | Scope | Rationale |
|---|---|---|---|
| 2026-08-08 | Use `9314f54b` as initial PC behavioral reference | Core gameplay | Last clear pre-Android behavioral baseline before `52bd0403`; behavioral reference only. |
| 2026-08-08 | Recovery starts from current HEAD `0821182a` | Entire repo | Preserve project content, later features, fixes, assets, and Android support. |
| 2026-08-08 | One shared gameplay core | Architecture | Prevent PC/Android behavioral forks. |
| 2026-08-08 | Android specialization only behind semantic boundaries | Android | Preserve Android performance without partial live gameplay state. |
| 2026-08-08 | Preserve fast-forward, PC/Android debugger, profiler, restart, save/load enhancements | Features | Explicit product requirements. |
| 2026-08-08 | GPT-5.6 Luna/Terra/Sol policy | Process | Luna for mechanical work, Terra as default coder, Sol for semantic architecture/nonlocal debugging. |
| 2026-08-08 | Replace fixed strongest-model assignment with primary + escalation gates | Process | Start with the cheapest safe model; escalate only on evidence-defined conditions. |
| 2026-08-08 | `ultra` is escalation-only | Process | Avoid excessive token use on tasks with already-approved architecture. |

---

# 23. CURRENT EXECUTION STATE

**Current phase:** Phase 0

**Next authorized task:** `P0-T01` only.

No later task is authorized until required preceding reports are reviewed.

**P0-T01 primary:** `GPT-5.6 Luna / low`

**P0-T01 escalation target:** `GPT-5.6 Terra / medium`

No escalation is pre-authorized.

If Codex is running another configuration, it must stop and ask the user to switch to `GPT-5.6 Luna / low` before P0-T01.

---

# 24. SHORT FORM CODEX REMINDER

1. Read `AGENTS.md`, `AGENTS.override.md`, and `plan.md`.
2. Execute only the authorized task.
3. Start with the task's exact primary model/effort.
4. Stronger is not automatically better: unauthorized extra model cost is a gate failure.
5. Escalate only on a named evidence-based condition and STOP before switching.
6. Terra is the default coder; Sol is reserved for semantics/nonlocal architecture.
7. `ultra` is escalation-only.
8. PC gameplay semantics remain authoritative unless the controller approves a later correctness fix.
9. Preserve intended features and independent bugfixes.
10. Shared optimizations must be trace-equivalent.
11. Android optimization cannot expose partial gameplay state.
12. Do not self-advance through controller gates.
13. Report evidence, tests, risks, escalation triggers, and commit SHA.
14. Stop when acceptance criteria are met; do not opportunistically refactor.
