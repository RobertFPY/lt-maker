# Recovery Controller State

> This file is the live controller-gate state for the recovery program.
> `plan.md` remains authoritative for architecture, task definitions, model assignments, escalation conditions, invariants, and acceptance criteria.
> This file overrides only the stale/static `CURRENT EXECUTION STATE` section in `plan.md` when they disagree.

## Current authorization

- Current phase: Phase 1
- Last reviewed task: `P1-T02`
- Last reviewed commit: `a036be233df0d5d80ee960f2bee9480f639c0876`
- Review result: **CHANGES REQUESTED**
- Next authorized work: **`P1-T02-R1` only**
- Primary: `GPT-5.6 Terra / medium`
- Escalation target: `GPT-5.6 Sol / high`
- Escalation pre-authorized: **NO**
- `P1-T03` remains **UNAUTHORIZED**
- Controller gate after P1-T02-R1: **YES — STOP FOR CONTROLLER REVIEW**

## Accepted parts of P1-T02

- Commit scope is limited to `app/engine/trace.py`, the optional trace-recorder seam in `app/engine/state_machine.py`, and `app/tests/test_recovery_trace.py`.
- `StateMachine.trace_recorder` is `None` by default and the callback occurs after `temp_state` is cleared; the no-recorder path is structurally minimal.
- Canonical JSON/SHA-256 helpers, pending-transition rejection, save-payload checkpoint ID, shared-object dedup concept, event active/pending ordering concept, and test-owned hook observer are directionally consistent with the accepted Trace V1 design.
- No PC-reference golden fixture was generated or blessed.
- No baseline failure was repaired.
- No model escalation was used.

## Why P1-T02 is not accepted yet

The current harness passes synthetic `SimpleNamespace` tests but does not yet capture several authoritative runtime surfaces correctly. These gaps can create false equality or false divergence in P1-T03, so golden capture is blocked.

### R1 — Make unit serialization match real `UnitObject`

`UnitObject` stores mutable gameplay values as `current_hp`, `current_mana`, `current_fatigue`, and `current_guard_gauge`; the harness currently reads `hp`, `mana`, `fatigue`, and `guard_gauge`, which can become `None` on real units.

Revise unit capture to use actual runtime/save semantics and include the controller-required mutable fields: class, level, EXP, base stats, growths/growth points where relevant, WEXP, current HP/mana/fatigue/guard, full action state, traveler/pair-up state, equipment, inventory ordering/content, and skill source metadata.

Do not use only `unit.skills` for source metadata. Source/source-type lives on `UnitSkill` wrappers in `_skills`; preserve the semantic relation without hashing raw runtime UID/address values. Aura-child handling must remain compatible with the alias graph contract.

Add tests using real or engine-shaped `UnitObject` semantics so invented attribute aliases cannot hide runtime mismatches.

### R2 — Make item/skill object-graph adapters engine-compatible

`ItemObject` and `SkillObject` carry logical state in `data`, owner/initiator fields, subitem/subskill relationships, command-item relationships, and component values. Direct attributes such as `uses` may be component objects rather than normalized primitives.

Implement explicit normalization/adapters for the gameplay-relevant object payload needed by Trace V1 scenarios. Preserve nested/shared relationships with local references. Unknown unsupported semantic component payloads must fail loudly; do not use `repr` and do not silently drop them.

Add representative real-object tests for item durability/uses, nested items, skill data/source relationships, and alias preservation.

### R3 — Capture real RNG state without consuming RNG

The current snapshot only reads optional `game._trace_rng`; normal `GameState` does not populate it. Trace V1 requires deterministic RNG state.

Capture the existing static-random seed, combat state, growth state, and other state through read-only access/seams. Capturing must not advance any generator. Add a test proving capture leaves all RNG states unchanged while returning their exact values.

### R4 — Correct phase/team capture

`PhaseController.current` is an integer index in the normal non-initiative path; the logical team NID comes from `get_current()`.

Trace `phase`/`active_team` using logical team identity rather than the raw integer controller index. Add a regression test for this API shape.

### R5 — Implement required board/tilemap/aura/fog/region state instead of placeholders

The current harness reads `board.units`, but real `GameBoard` uses `unit_grid`; it also emits empty `aura_sources`, `fog_visible`, and `regions`, and omits the required logical `tile_grid_hash`.

Implement the Trace V1 board contract using actual engine structures or deterministic logical derivations:

- tilemap NID/dimensions and canonical logical tile-grid hash;
- board occupancy from the authoritative board/unit-grid state (not a synthetic `board.units` map);
- aura source/coverage identity needed to detect aura corruption;
- fog visibility/visited state needed by the approved FOW scenarios;
- bounds and logical region identities/positions.

Do not serialize surfaces/render caches. Add focused tests that would fail if these fields were hard-coded empty.

### R6 — Fix comparator semantics and diagnostics

Trace V1 defines `runner_revision` and `platform_profile` as provenance, not logical-equality fields. The current comparator canonical-compares the entire header, so a PC-reference trace and recovered trace can fail solely because those provenance values differ.

Implement the accepted comparison policy:

- validate required schema/scenario/input/reference identity fields;
- ignore only explicitly designated provenance fields for logical equality;
- require ordered checkpoint identity/context compatibility;
- compare state/delta hashes and normalized content;
- report a useful first field-level difference (JSON Pointer or equivalent stable path) plus nearby checkpoint context as specified by the trace schema.

Add tests proving provenance-only differences pass and semantic/header identity differences fail.

### R7 — Provide explicit action/playback normalization registry seam

Trace V1 requires explicit semantic adapters for actions and combat playback, with unknown types failing loudly. Passing already-normalized dictionaries directly into `delta` is not a sufficient registry contract.

Implement a bounded registry/adapter seam that P1-T03 can extend per scenario without broad production instrumentation. Include tests for one mapped semantic type and one unmapped type. Do not attempt to map every engine action/playback type in this revision.

### R8 — Validate save-payload normalization against real logical payload shape

`save.payload.captured` must hash the complete in-memory logical save payload before I/O. Ensure the normalization path can handle the actual logical payload structures needed by `GameState.save()` without relying on filesystem metadata or arbitrary object `repr`.

A focused representative save-payload test is sufficient; do not run or bless P1-T03 golden scenarios.

## P1-T02-R1 constraints

- Modify only the trace harness/tests and the already-approved minimal recorder seam if strictly necessary.
- Do not add broad production gameplay hooks.
- Do not generate/bless PC-reference golden fixtures.
- Do not start P1-T03.
- Do not fix baseline failures.
- Preserve default no-recorder behavior exactly.
- Prefer real engine objects/APIs in regression tests where practical; synthetic fixtures must mirror actual attribute names and structures.
- Run the targeted recovery-trace tests, relevant state-machine lifecycle tests, and `compileall`/`git show --check` as applicable.
- No escalation is currently required. Escalate only if fixing these bounded harness defects requires a new production lifecycle seam or an unresolved semantic choice.

## Gate status

`P1-T02` is **not accepted**. `P1-T03` remains blocked until P1-T02-R1 is reviewed and accepted.
