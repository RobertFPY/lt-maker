# P1-T01 — Deterministic Logical Trace Schema

Status: proposed design only.  No recorder, hook, gameplay code, or fixture is
implemented by this task.

Authority: P1-T01 in `plan.md`; controller state dated 2026-08-08.
Primary configuration: GPT-5.6 Terra / high.

## 1. Purpose and boundary

The recovery oracle compares *logical PC gameplay semantics* at completed,
deterministic synchronization points.  The behavioral reference is
`9314f54b49f4552b5a3d023b4da0012ce7dfbc89`, except a later correctness change
explicitly allowlisted by the controller.

This is not a render, audio, frame-time, profiler, thread, or UI test.  In
particular, Android staged/deferred restore is an implementation detail, not
the expected trace.  A staged path may emit the same checkpoint only when its
public logical transaction has completed.

Excluded from comparison:

- frame counts, host time, wall-clock time, frame IDs, and input event timing;
- pygame surfaces, render caches, animations, camera, fonts, and audio/music
  objects or playback positions;
- profiler samples, debugger UI state, thread IDs, object addresses, `repr`,
  temporary paths, and allocation order;
- platform-only presentation settings.

## 2. Trace V1 format

Each trace is UTF-8 JSON Lines.  It contains one `trace_header`, followed by
zero or more ordered `checkpoint` records.  Canonical JSON is compact,
`ensure_ascii=True`, mapping keys sorted recursively, and encoded as UTF-8.
Hashes are SHA-256 over that canonical encoding.

```json
{"kind":"trace_header","schema_version":1,"scenario_id":"chapter_start","reference_revision":"9314f54b49f4552b5a3d023b4da0012ce7dfbc89","runner_revision":"<commit>","platform_profile":"pc_reference","input_fixture_id":"chapter_start_v1","seed":12345,"serializer":"logical-trace-v1"}
{"kind":"checkpoint","sequence":0,"checkpoint_id":"level.load.complete","context":{"level_nid":"prologue"},"logical_state":{},"semantic_delta":{},"state_hash":"<sha256>","delta_hash":"<sha256>"}
```

`sequence` orders records but is not part of either hash.  `runner_revision`
and `platform_profile` are provenance, not logical equality fields.  All other
header fields must match the golden fixture exactly.

### 2.1 Checkpoint envelope

`checkpoint_id` is a stable boundary name.  `context` contains only the
minimal identity needed to diagnose the boundary (for example `level_nid`,
`event_nid` plus command ordinal, `unit_nid`, or a scenario-defined combat
ordinal).  It must not contain Python object IDs or display text.

`logical_state` is a complete normalized logical snapshot.  `semantic_delta`
contains ordered logical effects since the preceding checkpoint.  Both are
hashed independently.  A comparator first checks record identity and hashes,
then produces a field-level diff if either hash differs.

## 3. Required logical snapshot

The capture function must produce the following shape.  Fields unavailable in
a legitimate state are encoded as `null`, not omitted.  Collections marked
set-like are sorted by their canonical element encoding.

```text
logical_state
  state_stack
    active: [state NID, ...]              # bottom to top
    pending: [state NID, ...]             # queued temp-state transitions
  world
    mode: state-mode NID or null
    level_nid: active level NID or null
    overworld_nid: active overworld NID or null
    current_party: party NID or null
  turn
    turncount: integer or null
    phase: phase/team NID or null
    active_team: team NID or null
  units: [unit snapshot, ...]             # sorted by unit NID
  variables
    game: normalized game vars
    level: normalized level vars
  rng
    seed: initial seed
    combat_state: integer
    growth_state: integer
    other_state: integer
  board
    tilemap_nid: NID or null
    dimensions: [width, height] or null
    tile_grid_hash: SHA-256 or null
    occupancy: [[x, y, unit NID], ...]
    aura_sources: [[x, y, source ref], ...]
    fog_visible: [[x, y], ...]
    fog_visited: [[x, y], ...]
    bounds: normalized logical bounds
    regions: normalized region identities and logical positions
  events
    already_triggered: [event NID, ...]
    active: {event_nid, command_index, command_nid} or null
  completion
    save_restore: completion state or null
    restart: completion state or null
```

### 3.1 Unit, skill, and inventory snapshot

Each unit snapshot contains at least:

```text
nid, team, party, position, hp, mana, finished, dead,
statuses, skills, inventory
```

`position` is `null` or `[x, y]`.  `statuses` and `skills` contain their NID
and logical payload required to reconstruct their game effect.  `inventory`
preserves its semantic slot order and contains the item NID, durability/uses,
chapter uses, logical data, and nested subitems where applicable.

Raw item and skill UIDs are not comparison identities: allocation order can
differ without semantic divergence.  The serializer derives a stable local
reference from deterministic traversal:

```text
(owner unit NID or global owner, category, slot/path, item-or-skill NID)
```

Relations use this reference.  A raw UID may be retained only in an
uncompared diagnostic attachment; it must never affect hashes or equality.

### 3.2 Variables and RNG

Game and level variables are recursively normalized and included by default.
The only permitted exclusions are an explicit, reviewed list of known
non-logical keys (for example trace diagnostics); no broad underscore-prefix
rule is allowed because underscore-prefixed variables can drive gameplay.
Each scenario declares additional required variable keys if its behavior
depends on them.

RNG records the seed and combat, growth, and other generator states.  The
existing `static_random` public accessors cover seed, combat, and other state;
P1-T02 may add a read-only capture seam for growth state if needed.  During a
combat terminal checkpoint, the normalized delta also records the combat's
initial and final random states where available.

### 3.3 Board and tilemap identity

`tile_grid_hash` derives solely from canonical logical tile identities and
dimensions, never from a tilemap surface or cache.  Aura, occupancy, fog,
bounds, and regions use coordinate-sorted logical records.  A source reference
uses NIDs/local references, never Python identities.  This makes tilemap,
board, aura, and fog mutations observable while allowing different rendering
or job scheduling implementations.

## 4. Semantic deltas

`semantic_delta` is ordered and contains only completed gameplay effects:

```text
actions:          [normalized action, ...]
combat_playback:  [normalized playback effect, ...]
triggered_events: [event NID, ...]
```

Action and playback adapters must be an explicit registry by engine action or
playback type.  Each adapter outputs primitives, NIDs/local references,
coordinates, amounts, and logical flags.  Unknown types fail trace generation
with a named normalization error; they may not fall back to `repr` or silently
disappear.  The registry will be extended only with a reviewed mapping when a
scenario reaches a new semantic type.

Event order is represented by `triggered_events` and the ordered completion of
event-command checkpoints.  Dialogue text, waiting-for-input state, and
visual transitions are excluded unless a command's logical effect changes one
of the required snapshot fields.

## 5. Normalization rules

The proposed `normalize(value)` accepts only serialization-safe logical data:

- primitives are retained; tuples become lists;
- mappings use normalized string keys and sorted keys;
- set-like collections become elements sorted by canonical encoding;
- lists retain order only when that order is semantically meaningful;
- enums become stable names; coordinates become two integer elements;
- known engine objects are converted by dedicated adapters; and
- unsupported objects raise `TraceNormalizationError`.

No value may be represented by `repr`, an address, an iteration order of an
unordered container, or an implicit Python object identity.  Hashing is
performed only after normalization.  The schema version increments for any
meaningful format or normalization change; existing golden fixtures are never
rewritten to hide a regression.

## 6. Synchronization-point catalog

P1-T02 may add recorder calls only at the following completed boundaries.  It
must not instrument render loops, every frame, every job yield, or per-path
movement steps.

| Checkpoint ID | Completed logical boundary | Proposed owner/seam |
| --- | --- | --- |
| `state.transition.commit` | State-machine queued transition has been applied | `StateMachine` after `process_temp_state` |
| `level.load.complete` | Level is usable and its state stack/board are committed | public level-start completion |
| `overworld.load.complete` | Overworld load is committed | public overworld-start completion |
| `player.control.ready` | Initial player-control state is logically ready | chapter-start completion |
| `movement.commit` | A movement action has logically arrived/finished | action completion seam |
| `combat.cleanup.complete` | Combat actions, hooks, cleanup, and terminal stack handling are complete | combat finalization seam |
| `event.command.complete` | One semantic event command completed without a pending async job | event processor completion seam |
| `event.transaction.complete` | A complete event transaction ended | event end seam |
| `tilemap.change.commit` | Tilemap/board replacement is final | `TilemapChangeJob` terminal commit only |
| `add_group.complete` | Group placement/removal command is final | `AddGroupJob` terminal completion only |
| `phase.transition.complete` | Phase/turn state is committed | phase state completion |
| `save.restore.complete` | Restore plus state-stack/level readiness is complete | public load completion, never an iterator yield |
| `save.write.complete` | State selected for serialization is complete | immediately before/after logical save capture |
| `restart.complete` | Restarted chapter is logically ready | public restart completion |
| `fast_forward.comparison.end` | Scripted scenario reaches its end state | test runner only |
| `debugger.observer.check` | Observer is enabled but has not made a logical mutation | test runner only |

The exact production call sites and recorder lifetime are P1-T02 work.  For
staged `GameState.load_iter`, tilemap jobs, and add-group jobs, intermediate
stages are deliberately not checkpoints.  A failed terminal job may be
recorded for diagnosis only when a scenario expects it; it is not an implicit
PC-semantic golden result.

## 7. Proposed helper interfaces (not implemented)

```python
class TraceRecorder:
    def begin(self, scenario_id, metadata): ...
    def checkpoint(self, checkpoint_id, game, *, context=None, delta=None): ...
    def finish(self, output_path): ...

def capture_logical_state(game) -> dict: ...
def normalize(value, *, schema_version: int = 1): ...
def canonical_hash(value) -> str: ...
def capture_combat_delta(combat) -> dict: ...
def compare_trace(expected_path, actual_path, policy) -> ComparisonResult: ...
```

The recorder is test-owned/injected and inactive by default.  Boundary calls
must be guarded by recorder presence and must not alter state ordering,
scheduling, RNG consumption, action dispatch, or error handling.  P1-T02
must define its concrete dependency/lifecycle seam and unit-test no-recorder
behavior before adding any production hook.

## 8. Golden fixtures and comparison

P1-T03 will generate reviewed reference traces in a versioned test-fixture
directory, proposed as:

```text
app/tests/fixtures/recovery_traces/v1/<scenario>.jsonl
app/tests/fixtures/recovery_traces/v1/manifest.json
```

The manifest records the reference revision, scenario/input fixture identity,
schema version, and file SHA-256.  Golden traces are generated from the PC
reference checkout and reviewed as behavioral evidence, not updated from a
recovered build merely to make tests pass.

Comparator policy:

1. Validate schema, scenario ID, input fixture ID, and reference revision.
2. Require identical checkpoint count, ordered checkpoint IDs, and normalized
   context identity.
3. Compare state and delta hashes at each checkpoint.
4. On first mismatch, report JSON Pointer paths, expected/actual values, and
   the three preceding checkpoint identities/contexts.
5. Permit an exception only through a controller-reviewed, field-specific
   allowlist that names its correctness decision/commit.  Wildcard ignores,
   platform-wide ignores, and “update expected” behavior are forbidden.

Fast-forward tests run identical deterministic input with fast-forward off and
on.  They compare logical checkpoints and terminal state/delta, not the number
of host frames.  Debugger/profiler observer tests run an identical scenario
with the observer disabled and enabled-but-idle; the full logical trace must
remain equal.  A debugger command that deliberately mutates state is a
separate explicitly specified scenario.

## 9. Scenario contract for later phases

P1-T03 must cover the approved P1 scenario set: chapter start and player
control; normal movement; combat with solver/action/hook/cleanup; event
ordering; RNG-sensitive path; tilemap change; add-group; fog/aura/board
mutation; save/load; restart; overworld transition; fast-forward on/off;
debugger/profiler observer equivalence; victory/game-over return; and the
additional controller-approved coverage required by `plan.md`.

Each scenario declares deterministic inputs, seed, required checkpoints,
required variable keys, and reference fixture revision.  Scenario additions
require controller review; they do not relax an existing fixture.

## 10. Test plan for the harness

Before reference capture, P1-T02/P1-T03 tests must prove:

- normalization produces identical bytes/hash for equivalent mappings and
  set-like collections constructed in different orders;
- local UID remapping is stable and semantic slot ordering is preserved;
- volatile/render objects are excluded only through explicit adapters, while
  unsupported types fail loudly;
- comparator rejects header, checkpoint-order, context, state, and delta
  mismatches with a useful first-difference report; and
- recorder absence does not change behavior at an instrumented seam.

No baseline suite failure is in scope for this design task.

## 11. Risks requiring review before P1-T02

- Combat action/playback types are heterogeneous; each semantic type needs a
  deliberate adapter rather than a generic object dump.
- Some state fields may be cache-derived.  An adapter must prove whether a
  field is a logical invariant or exclude it by named rationale.
- Event commands and asynchronous jobs need terminal-boundary placement that
  preserves their current completion semantics.
- Save data can carry legacy UID structures; local-reference normalization
  must preserve aliasing and containment relevant to gameplay.
- Global singletons and random generators need strict fixture setup/reset so
  trace tests remain deterministic.

## 12. P1-T01 completion state

This document supplies the proposed Trace V1 contract, synchronization-point
catalog, normalization/hash policy, fixture strategy, comparison policy, and
test strategy.  It intentionally does not implement P1-T02 or modify gameplay
code.  Controller review is required before any recorder or production hook is
added.
