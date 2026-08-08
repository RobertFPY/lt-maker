# Recovery Controller State

> This file is the live controller-gate state for the recovery program.
> `plan.md` remains authoritative for architecture, task definitions, model assignments, escalation conditions, invariants, and acceptance criteria.
> This file overrides only the stale/static `CURRENT EXECUTION STATE` section in `plan.md` when they disagree.

## Current authorization

- Current phase: Phase 1
- Last reviewed task: `P1-T02-R1`
- Last reviewed commit: `d64fbdb3441b573823c6bdfc7b46b98c6e17b2be`
- Review result: **CHANGES REQUESTED**
- Escalation trigger encountered: **ESC-08 — Repeated local failure**
- Next authorized work: **`P1-T02-R2` only**
- Authorized model/effort: **`GPT-5.6 Sol / high`**
- This is the P1-T02 escalation target and is **explicitly authorized** for R2.
- No further self-escalation is authorized.
- `P1-T03` remains **UNAUTHORIZED**.
- Controller gate after P1-T02-R2: **YES — STOP FOR CONTROLLER REVIEW**.

## P1-T02-R1 controller review

Accepted progress in `d64fbdb3441b573823c6bdfc7b46b98c6e17b2be`:

- Scope remained bounded to `app/engine/trace.py` and `app/tests/test_recovery_trace.py`; the previously approved `StateMachine` seam was not changed.
- Unit capture now reads the real `UnitObject.current_hp/current_mana/current_fatigue/current_guard_gauge` fields.
- `_skills` / `UnitSkill` wrappers are consulted for source metadata instead of relying only on visible skills.
- Item/skill object graph records now include owner/data/component payload and nested parent/subitem/subskill/command relationships.
- RNG capture reads static-random seed/combat/growth/other state without intentionally drawing random values.
- Phase capture uses `get_current()` rather than the raw controller index.
- Occupancy now supports `GameBoard.unit_grid`.
- Header comparison ignores the two approved provenance fields: `runner_revision` and `platform_profile`.
- A bounded semantic adapter registry was introduced.
- No golden fixtures, P1-T03 work, baseline fixes, or broad production hooks were introduced.

P1-T02-R1 is **not accepted** because the harness still cannot safely serve as the P1-T03 behavioral oracle.

## Why ESC-08 applies

P1-T02 had one bounded implementation (`a036be233...`) followed by one bounded correction (`d64fbdb34...`), and the acceptance contract is still not satisfied. This matches `plan.md` ESC-08. The next correction therefore uses the task's authorized escalation target `GPT-5.6 Sol / high` rather than another Terra loop.

## Required P1-T02-R2 corrections

### R2-1 — Finish real UnitObject / UnitSkill serialization

The current revision still does not implement the full controller-required action/pair-up state and is not covered by a real-engine-shaped unit regression test.

Required:

- serialize the complete logical action state represented by `UnitObject.get_action_state()` (`finished`, attacked, traded, moved, rescued, dropped, taken, given), not only moved/attacked;
- include remaining gameplay-relevant pair-up/rescue state needed by the accepted contract (`traveler`, lead/built-guard state, and stable partner/source identity where present);
- normalize `SourceType` and other approved enums to stable semantic names/NIDs; `SourceType` is an `Enum` and must not fail generic normalization;
- when a skill source is an allocation UID that semantically references another runtime object (notably aura/source relationships), convert it to a stable object-graph reference where possible rather than hashing the raw UID;
- add tests using actual `UnitObject`/`UnitSkill`/`SkillObject` classes or fixtures that instantiate those exact runtime fields, including a non-default action state and a `SourceType` value.

### R2-2 — Finish item/skill component normalization with representative real objects

The object graph must serialize gameplay-relevant component values deterministically without `repr` and without silently dropping unsupported values.

Required:

- define the explicit normalization path for item/skill component values, including stable enum handling and nested logical containers;
- preserve parent/subitem/command-item and parent/subskill alias relationships by local reference;
- unsupported semantic component payloads must still fail loudly;
- add representative `ItemObject` and `SkillObject` tests that exercise component/data state, nested/shared relationships, durability/uses-like component state, and alias preservation.

Do not map every component type in the engine; implement the generic approved logical primitives/containers/enums plus explicit object adapters needed by the harness contract.

### R2-3 — Prove RNG capture is read-only

The implementation now reads static-random state, but no acceptance test proves it is non-consuming.

Add a regression test that:

- seeds static random;
- records seed/combat/growth/other internal states;
- captures a logical trace state;
- asserts the captured values exactly match the pre-capture values; and
- asserts all generators remain unchanged after capture.

A tiny read-only `get_growth_random_state()` seam in `app/utilities/static_random.py` is authorized if it improves correctness/encapsulation. It must not alter RNG behavior.

### R2-4 — Prove phase/team API semantics

Add a regression test where the phase controller's raw `current` value differs from its logical `get_current()` team NID. The trace must contain the logical team NID.

### R2-5 — Complete board/tilemap/aura/fog/region capture

The current `tile_grid_hash` hashes only tilemap NID + dimensions, while `aura_sources`, `fog_visible`, and `regions` are still hard-coded empty. This fails Trace V1.

Required:

- derive `tile_grid_hash` from deterministic logical tile/terrain identity for every coordinate, not only NID/dimensions;
- keep occupancy from authoritative `unit_grid`;
- serialize aura coverage/source identity from `aura_grid` / `known_auras` (mapping runtime skill UIDs back to stable skill/object-graph identity, never exposing the UID itself);
- serialize logical fog visibility plus `previously_visited_tiles` using existing board/fog semantics without mutating state;
- serialize logical region identity/type/position/size or equivalent gameplay-relevant region geometry from the game/level region structures;
- add focused tests with non-empty aura, fog, regions, and terrain/tile identities; the tests must fail if those fields regress to placeholders.

Do not serialize surfaces, render caches, opacity textures, or presentation-only data.

### R2-6 — Finish comparator policy and diagnostics

Ignoring provenance is only part of the accepted comparator contract.

Required:

- explicitly validate required header identity (`schema_version`, `scenario_id`, `input_fixture_id`, `reference_revision`, serializer as applicable);
- ignore only the approved provenance fields;
- require ordered checkpoint ID/context compatibility;
- compare state and delta hashes/content;
- on mismatch, report a stable first field-level path (JSON Pointer or equivalent) with expected/actual values and nearby checkpoint identity/context;
- add tests for provenance-only equality, header identity mismatch, checkpoint-order/context mismatch, and nested logical-state/delta mismatch diagnostics.

### R2-7 — Integrate semantic registries into action/playback delta normalization

A standalone generic `SemanticRegistry` is not sufficient if `TraceRecorder` still accepts arbitrary already-normalized action/playback lists.

Required:

- provide distinct or clearly typed action/playback registry paths owned/injected by the test harness;
- when raw semantic action/playback objects are supplied, normalize them only through the registered adapter;
- unmapped raw action/playback types fail loudly;
- already normalized primitive trace records, if supported, must follow one explicit documented path rather than bypassing adapter validation accidentally;
- tests must show one mapped action, one mapped playback, and unmapped failures.

Do not broadly instrument production combat in R2.

### R2-8 — Validate representative GameState.save payload normalization

`GameState.save()` includes logical structures that are not plain JSON primitives, including `RoamInfo` in the save payload. The current `canonical_hash()` path cannot normalize arbitrary dataclass engine objects.

Required:

- add an explicit logical adapter for the known save-payload object(s) required by the current `GameState.save()` shape, including `RoamInfo` (`roam`, `roam_unit_nid`);
- add a representative save-payload regression test shaped from the actual `GameState.save()` contract, including nested mappings/lists/sets/tuples and `RoamInfo`;
- prove `save.payload.captured` hashes that logical payload before I/O and does not include file paths, timestamps, or filesystem completion state;
- unsupported unknown engine objects must continue to fail loudly.

A full golden/save scenario is still P1-T03 and is not authorized here.

## P1-T02-R2 scope and constraints

- Primary work remains `app/engine/trace.py` and `app/tests/test_recovery_trace.py`.
- `app/utilities/static_random.py` may receive only a tiny read-only RNG-state getter if needed.
- Do not change `app/engine/state_machine.py` unless a new issue is first reported to the controller; its existing optional seam is already accepted.
- Do not add broad event/combat/gameplay hooks.
- Do not generate or bless PC-reference golden fixtures.
- Do not start P1-T03.
- Do not fix baseline failures.
- Preserve default no-recorder runtime behavior exactly.
- Use real engine classes/APIs in acceptance tests where practical; do not let invented aliases in `SimpleNamespace` stand in for an engine API under test.
- Run targeted recovery-trace tests, relevant state-machine lifecycle tests, `compileall`, and `git show --check`.
- Report each R2-1 through R2-8 as PASS/FAIL with the test/evidence that supports it.
- If Sol/high discovers an unresolved semantic choice, invasive new lifecycle seam, or another global ESC condition, STOP and report it; do not self-escalate further.

## Gate status

`P1-T02` is **not accepted**. `P1-T03` remains blocked until P1-T02-R2 is reviewed and accepted.
