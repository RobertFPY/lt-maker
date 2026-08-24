# P1-T01 — Deterministic Logical Trace Schema

Status: proposed design revision.  No recorder, hook, gameplay code, or
fixture is implemented by this task.

Authority: P1-T01-R1 in `recovery/controller_state.md`; controller review of
P1-T01 requested R1-R5 before P1-T02 can be considered.
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

This R1 amendment remains Schema V1 because no V1 fixture has been accepted or
generated. Once fixtures exist, any meaningful format or normalization change
must increment `schema_version`; fixtures are never rewritten to conceal a
regression.

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
    pending: [transition descriptor, ...] # normally required empty; see section 6.1
  world
    mode: state-mode NID or null
    level_nid: active level NID or null
    overworld_nid: active overworld NID or null
    current_party: party NID or null
  turn
    turncount: integer or null
    phase: phase/team NID or null
    active_team: team NID or null
  object_graph: {objects: [object record, ...]}
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
    execution_stack: [event frame, ...]   # active, then next-pop order
  completion
    save_restore: completion state or null
    restart: completion state or null
```

### 3.1 Stable object graph, aliases, and local references

The snapshot has an `object_graph` registry. Units, inventory slots, skills,
statuses, board aura sources, action records, hook observations, and event
frames refer to objects by `local_id`; they do not copy an object merely
because it appears at another logical path.

During one capture only, the serializer may use Python object identity to
deduplicate its graph. It must never emit that identity, an address, a hash,
or a raw UID into equality/hash output. It traverses roots in one documented
canonical order: normalized game roots; units by NID; each unit's inventory
and nested item slots; each unit's skill/status slots; board entries by
coordinate; then the active event frame and pending event frames in pop order.
For an object first reached at a path, it assigns:

```text
local_id = <kind>@<first canonical path>@<NID or stable kind discriminator>
```

The first canonical path is the identity choice. Later appearances of the
same runtime object emit the original `local_id`; a distinct object with the
same NID receives its own path-derived `local_id`. The registry is emitted as
canonical records such as:

```text
object_graph.objects
  - local_id: skill@units/amy/skills/0/aura_speed
    kind: skill
    nid: aura_speed
    logical_fields: {...}
    references: {source: skill@units/amy/skills/0/aura_parent}
```

This makes a shared Aura child observable as one `SkillObject` with multiple
references, while remaining independent of creation/allocation order. Cycles
must be represented by local references, never recursive object dumps. Any
UID is excluded unless a future controller-reviewed adapter names that UID as
a gameplay-semantic field and explains why a stable local reference cannot
represent it.

### 3.2 Unit, skill, and inventory snapshot

Each unit snapshot contains at least:

```text
nid, team, party, position, hp, mana, finished, dead,
statuses, skills, inventory
```

`position` is `null` or `[x, y]`. `statuses`, `skills`, and `inventory`
retain semantic slot order but contain `local_id` references into
`object_graph`. Their registry records carry NID and logical payload required
to reconstruct the game effect, including item durability/uses, chapter uses,
logical data, and nested subitems.

### 3.3 Variables and RNG

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

### 3.4 Board and tilemap identity

`tile_grid_hash` derives solely from canonical logical tile identities and
dimensions, never from a tilemap surface or cache.  Aura, occupancy, fog,
bounds, and regions use coordinate-sorted logical records. Aura sources use
`object_graph` local references, never Python identities. This makes tilemap,
board, aura, and fog mutations observable while allowing different rendering
or job scheduling implementations.

### 3.5 Event execution stack

The engine does not expose one nested-call stack: `EventState.event` owns the
active event, `EventManager.event_stack` is a LIFO queue of pending events,
and `all_events` retains all live events. Therefore `events.execution_stack`
normalizes executable order as: active `EventState.event` when present; then
pending `EventManager.event_stack` frames in next-`pop()` order; then any
still-live `all_events` frame not represented above, in canonical
insertion/provenance order and marked `role: "retained"`.

Every frame has `event_ref`, `event_nid`, normalized trigger identity,
`processor.command_ordinal`, `processor.command_nid`, and `role`. The
`event_ref` is an `object_graph` local reference, so repeated views of the
same runtime event remain aliases. If an event was enqueued while another
frame was active, it also has `caller_event_ref` and caller command ordinal.
That provenance is captured at enqueue time and survives normalization; when
the runtime provides no caller, including a legacy restored event, both fields
are explicitly `null`, never inferred.

Dialogue boxes, portrait state, render waits, and input waits stay excluded.
The ordered active/pending frames plus processor command identity/ordinal are
required so a save/load that resumes the wrong event or command differs.

## 4. Semantic deltas

`semantic_delta` is ordered and contains only completed gameplay effects:

```text
actions:          [normalized action, ...]
combat_playback:  [normalized playback effect, ...]
triggered_events: [event NID, ...]
hook_calls:       [ordered hook observation, ...]
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

### 4.1 Ordered gameplay-hook observations

`hook_calls` preserves every observed correctness-critical hook invocation in
the exact original order between checkpoints. Its list length is the call
count; entries are never sorted or coalesced. Each observation has:

```text
sequence: integer local to this delta
dispatcher: item | skill | combat | lifecycle
hook_name: stable dispatched hook name
subjects: {unit_ref, item_ref, skill_ref, source_ref, target_ref}
context: {combat_ordinal, action_ordinal, event_ref, command_ordinal, position}
lifecycle_phase: stable phase/checkpoint context
result: normalized gameplay-relevant result, or null
```

Absent subjects are `null`; references use `object_graph` local IDs. The
observer records the invocation in the dispatcher/lifecycle path that actually
makes it. It must not call a hook again, replay a component, or evaluate a
lazy value merely to produce trace data. P1-T02 may introduce only a
test-owned observer seam around specifically approved dispatch points; it may
not broadly instrument production gameplay paths.

The hook adapter registry names every observed dispatcher/hook pair and its
subject/result normalization. An unknown or unmapped correctness-critical
observation raises `TraceNormalizationError`; it cannot be silently omitted.
A result is included only when gameplay-relevant, but the call itself is
always recorded so equal final state cannot hide a skipped, duplicated, or
reordered hook.

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

Identity is permitted only as an internal, capture-lifetime deduplication key
while constructing `object_graph`; it is discarded before normalization and
hashing. Object traversal and first-path selection must be deterministic so
the same alias graph produces identical local IDs in independent runs.

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
| `save.payload.captured` | Complete logical save payload captured before filesystem I/O | save serialization boundary |
| `restart.complete` | Restarted chapter is logically ready | public restart completion |
| `fast_forward.comparison.end` | Scripted scenario reaches its end state | test runner only |
| `debugger.observer.check` | Observer is enabled but has not made a logical mutation | test runner only |

The exact production call sites and recorder lifetime are P1-T02 work.  For
staged `GameState.load_iter`, tilemap jobs, and add-group jobs, intermediate
stages are deliberately not checkpoints.  A failed terminal job may be
recorded for diagnosis only when a scenario expects it; it is not an implicit
PC-semantic golden result.

### 6.1 Pending state-transition invariant

Every terminal synchronization checkpoint represents a committed logical
transaction. Its `state_stack.pending` is therefore required to be `[]`.
Before writing such a checkpoint, the recorder validates this invariant; a
non-empty queue raises `TraceInvariantError` and writes no golden-eligible
checkpoint. It must not normalize a partial transition as expected behavior.

An exception is possible only when the scenario contract names the exact
`checkpoint_id`, allowed ordered transition descriptors, and their
gameplay-semantic reason. The checkpoint record then includes
`pending_exception_id`; a comparator rejects any pending queue without that
same approved exception. Render/defer flags, presentation fences, Android
budget yields, and any other platform-only scheduling artifact are neither
transition descriptors nor eligible exceptions. If they reach `pending`,
capture fails rather than turning Android scheduling into golden state.

### 6.2 Save payload boundary

`save.payload.captured` is the sole save-write trace boundary. It occurs
immediately after the engine has assembled the complete in-memory logical
save payload and before it passes that payload to filesystem I/O. Its state
assertion describes the source game state and includes a canonical hash of the
normalized logical save payload in `context.save_payload_hash`. There is no
post-write checkpoint: write completion, paths, files, timestamps, buffering,
and callbacks are deliberately outside semantic equality. This replaces the
ambiguous `save.write.complete` name; no fixture may use that retired ID.

## 7. Proposed helper interfaces (not implemented)

```python
class TraceRecorder:
    def begin(self, scenario_id, metadata): ...
    def checkpoint(self, checkpoint_id, game, *, context=None, delta=None): ...
    def observe_hook(self, dispatcher, hook_name, *, subjects, context, phase,
                     gameplay_result=None): ...
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
- local-reference assignment is stable, semantic slot ordering is preserved,
  and one shared Aura child serializes as one object-graph record referenced by
  multiple unit skill slots rather than independent copies;
- event capture preserves an active frame, LIFO next-event order, processor
  command ordinal, and available caller provenance across normalization;
- terminal checkpoints reject unapproved pending state transitions, while a
  scenario-specific approved exception compares its exact queue;
- hook observations preserve invocation order and count, never invoke a hook
  twice, and fail on an unmapped correctness-critical hook; and
- `save.payload.captured` hashes the in-memory logical payload without any
  filesystem completion/timestamp dependency;
- volatile/render objects are excluded only through explicit adapters, while
  unsupported types fail loudly;
- comparator rejects header, checkpoint-order, context, state, and delta
  mismatches with a useful first-difference report; and
- recorder absence does not change behavior at an instrumented seam.

No baseline suite failure is in scope for this design task.

## 11. Risks requiring review before P1-T02

- Combat action/playback types are heterogeneous; each semantic type needs a
  deliberate adapter rather than a generic object dump. The same registry
  discipline is required for correctness-critical hook observations.
- Some state fields may be cache-derived.  An adapter must prove whether a
  field is a logical invariant or exclude it by named rationale.
- Event commands and asynchronous jobs need terminal-boundary placement that
  preserves their current completion semantics.
- Save data can carry legacy UID structures; local-reference normalization
  must preserve aliasing and containment relevant to gameplay.
- Global singletons and random generators need strict fixture setup/reset so
  trace tests remain deterministic.

## 12. P1-T01-R1 completion state

This revision adds the R1 ordered hook stream, R2 alias-preserving object
graph, R3 event execution stack, R4 pending-transition invariant, and R5
unambiguous pre-I/O save payload boundary. It intentionally does not implement
P1-T02 or modify gameplay code. Controller review is required before any
recorder or production hook is added.
