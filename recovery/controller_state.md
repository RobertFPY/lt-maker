# Recovery Controller State

> This file is the live controller-gate state for the recovery program.
> `plan.md` remains authoritative for architecture, task definitions, model assignments, escalation conditions, invariants, and acceptance criteria.
> This file overrides only the stale/static `CURRENT EXECUTION STATE` section in `plan.md` when they disagree.

## Current authorization

- Current phase: Phase 1
- Last reviewed task: `P1-T02-R2`
- Last reviewed commit: `adc9ec753e6bf6623a31e013c762c10b01e53482`
- Review result: **ACCEPTED**
- `P1-T02` harness gate: **ACCEPTED after R2 escalation**
- Escalation used: **YES — ESC-08, GPT-5.6 Sol / high, controller-authorized**
- Next authorized task: **`P1-T03` only**
- P1-T03 primary: `GPT-5.6 Terra / high`
- P1-T03 escalation target: `GPT-5.6 Sol / max`
- Escalation pre-authorized: **NO**
- Controller gate after P1-T03: **YES — STOP FOR CONTROLLER REVIEW**
- Phase 2 remains **UNAUTHORIZED**.

## P1-T02-R2 controller review

Accepted evidence:

- Commit `adc9ec753e6bf6623a31e013c762c10b01e53482` changes only `app/engine/trace.py`, `app/tests/test_recovery_trace.py`, and a tiny read-only `get_growth_random_state()` accessor in `app/utilities/static_random.py`.
- `app/engine/state_machine.py` is unchanged by R2; the previously accepted optional recorder seam remains the only production lifecycle intrusion.
- No baseline failure, golden fixture, P1-T03 scenario, or broad combat/event/gameplay hook was introduced.
- Targeted recovery-trace + lifecycle validation was reported as 31/31 PASS; `compileall` and `git show --check` were reported clean.

### R2-1 — ACCEPTED

- Real `UnitObject`, `UnitSkill`, and `SkillObject` are exercised in acceptance tests.
- Unit capture includes current HP/mana/fatigue/guard, class/level/EXP/stats/growth/growth-points/WEXP, full eight-field `get_action_state()`, traveler, lead/built-guard, strike partner, equipment, inventory, and skill source/source-type state.
- `SourceType`/Enum values normalize to stable semantic values.
- Skill-source allocation UIDs are mapped to stable object-graph references where the referenced skill object is known.

### R2-2 — ACCEPTED

- Real `ItemObject`/`SkillObject` component/data payloads are normalized using primitives/containers/enums without `repr`.
- Parent/subitem/command-item and parent/subskill relationships use stable local references and preserve aliasing.
- Unsupported semantic component payloads fail with `TraceNormalizationError`.

### R2-3 — ACCEPTED

- Static-random seed, combat, growth, and other states are captured through read-only accessors.
- Acceptance test proves capture returns exact pre-capture values and leaves all RNG generator states unchanged.

### R2-4 — ACCEPTED

- Phase/team capture uses `PhaseController.get_current()` logical team identity instead of the raw numeric controller index.
- Regression test explicitly makes raw `current` differ from logical team NID.

### R2-5 — ACCEPTED

- Tile-grid hash is derived from per-coordinate logical terrain identity and stable layer NID, not surfaces or render objects.
- `TileMapObject.get_layer()` returns the stable layer NID used by the hash.
- Occupancy is derived from authoritative `unit_grid`.
- Aura coverage maps runtime skill UID to stable object-graph references rather than emitting UID.
- Fog visibility/visited state and logical regions are non-empty, deterministic trace fields in focused tests.

### R2-6 — ACCEPTED

- Comparator validates required header identity, ignores only approved provenance (`runner_revision`, `platform_profile`), preserves ordered record comparison, and reports a stable first field path with expected/actual values and nearby checkpoint context.
- Tests cover provenance-only equality plus header, checkpoint, context, logical-state, and semantic-delta divergence.

### R2-7 — ACCEPTED

- Action and combat-playback use separately injected semantic registries for raw objects.
- Mapped raw values normalize through adapters; unmapped values fail loudly.
- Pre-normalized records have an explicit `normalized_actions` / `normalized_combat_playback` path rather than accidental bypass.

### R2-8 — ACCEPTED

- `RoamInfo` has an explicit logical normalization adapter matching the current `GameState.save()` payload shape.
- Representative nested save payload covers mappings/lists/sets/tuples and `RoamInfo` and is hashed before filesystem I/O.
- Unknown unsupported objects still fail loudly.

## P1-T03 execution contract

Codex must execute only P1-T03 from `plan.md`: establish reviewed PC-reference golden scenarios using the accepted Trace V1 harness.

### Reference authority

- Behavioral reference commit: `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`.
- The reference is a behavioral oracle, not a textual source to copy wholesale.
- Do not change expected/reference behavior to match the current recovery branch.
- Do not repair reference behavior during golden capture.
- A later correctness fix may differ from the reference only when already controller-approved or when Codex stops and reports the conflict for a controller decision.

### Reference capture method

Use an isolated temporary worktree/checkout or equivalent non-destructive reference environment. Do not reset, force-checkout, or rewrite the recovery branch.

The same accepted Trace V1 serializer/comparator contract must be used for reference and current capture. If the harness requires a compatibility overlay on the reference checkout, it must be instrumentation-only/test-owned and must not alter gameplay ordering, RNG consumption, state transitions, save behavior, combat behavior, event behavior, or project content. Document exactly what overlay is used and why it is observer-equivalent.

If the accepted harness cannot be applied to the reference without making a semantic/lifecycle choice, stop under the applicable ESC condition instead of inventing a golden.

### Minimum scenario matrix

P1-T03 must cover the plan's minimum scenarios and may split them into deterministic sub-scenarios where necessary:

1. New game to first playable map / player-control ready.
2. Existing save load.
3. Save/load during event where supported by the reference lineage.
4. Restart current chapter.
5. Standard map combat.
6. Simple combat.
7. Animation combat.
8. Arena/base combat where applicable.
9. Skill proc plus pre/post-combat hook ordering.
10. Item durability/uses and broken/unusable handling.
11. Promotion/class-change edge cases including class/level/EXP/stat state.
12. Aura propagation/teardown/load aliasing.
13. Fog-of-war move preview/cancel/wait semantics.
14. Tilemap change and board commit.
15. Phase transition.
16. Fast-forward OFF vs ON logical equivalence.
17. Debugger/profiler disabled vs enabled-idle observer equivalence.
18. Game-over/restart path.

Each scenario must declare deterministic input fixture identity, seed, required checkpoints, and any scenario-specific required variables/approved pending-transition exception. Do not use host frame count, wall time, audio playback state, render surfaces, profiler samples, or volatile UI state as equality criteria.

### Golden fixture rules

- Store versioned fixtures under the approved Trace V1 fixture location (or a clearly documented equivalent if existing test layout requires it).
- Include a manifest with schema version, behavioral reference revision, scenario/input identity, and fixture SHA-256.
- Golden files must be generated from the PC reference environment, never copied from the current recovery branch merely because it passes.
- Do not silently regenerate a golden after a mismatch.
- Do not add wildcard ignores, platform-wide ignores, or broad normalization exclusions.
- Any field-specific exception requires a named controller decision and supporting evidence.

### Current-branch validation

After reference fixtures exist, run the same deterministic scenarios on the recovery branch and compare them against the reference fixtures. A current-branch divergence is evidence, not permission to modify the golden.

P1-T03 may add scenario drivers, fixture-generation/test utilities, semantic action/playback adapters required by those scenarios, and minimal test-owned observer wiring at already-approved seams. It may not begin Phase 2 recovery fixes or broadly instrument gameplay systems.

### Escalation conditions

Stop and request `GPT-5.6 Sol / max` if any of the following occurs:

- **ESC-01:** reference behavior or fixture meaning cannot be determined unambiguously;
- **ESC-02:** scenario failure crosses a second correctness-critical subsystem and cannot be isolated within the harness/scenario layer;
- **ESC-03:** deterministic logical traces diverge after locally correct scenario/harness setup and the cause is not presentation-only;
- **ESC-04:** multiple plausible golden semantics exist;
- **ESC-05:** scenario capture exposes a deeper invariant violation rather than a harness defect;
- **ESC-06:** save/load scenario reveals a compatibility/format decision;
- **ESC-08:** one bounded P1-T03 repair plus one bounded correction still cannot satisfy the scenario acceptance;
- **ESC-09:** golden capture requires a new unapproved cross-cutting lifecycle abstraction.

Do not self-escalate. Stop editing, preserve safe evidence, report the exact scenario/checkpoint/trace divergence, and wait for controller authorization.

### Validation and report requirements

Run the targeted Trace V1 harness tests plus all P1-T03 scenario tests. Run relevant lifecycle tests touched by scenario wiring, `compileall`, and `git show --check`.

The P1-T03 task report must include:

- scenario-by-scenario PASS/FAIL status for all 18 minimum scenarios;
- reference capture method and any instrumentation-only overlay;
- fixture/manifest paths and hashes;
- current-branch comparison result per scenario;
- first divergent checkpoint/path for every failure;
- tests/commands run and results;
- files changed;
- escalation triggers encountered;
- commit SHA.

Do not report overall PASS if any required scenario is skipped, unsupported without documented controller disposition, or has an unresolved trace divergence.

## Gate status

`P1-T02` is **ACCEPTED**. `P1-T03` is the only authorized next task. Phase 2 remains blocked until P1-T03 is reviewed and accepted.
