# LT-Maker - Animation Combat Flicker After EXP

**Document task:** `DOC-FLICKER-05`  
**Supersedes:** the `DOC-FLICKER-04` planning revision only  
**Repository:** `RobertFPY/lt-maker`  
**Planning branch:** `recovery/pc-core-semantics`  
**Primary production candidate:** `app/engine/combat/animation_combat.py`  
**Secondary code under review:** `app/engine/battle_animation.py`  
**Suspected introducing commit:** `fff0145d5f059f621e1d3b669cf1105e1017cccf`  
**Diagnosis:** `PARTIALLY CONFIRMED`  
**Execution readiness:** `BLOCKED`  
**Priority:** presentation correctness without gameplay-semantic or Android-performance regression
**Reviewed authority snapshot:** root `plan.md` SHA-256
`2C04F6F8B88F4E9E8BC555EB32F1D4A8EC2EC0DB2AB5617BDD18771BAAD978D5`; live
`recovery/controller_state.md` SHA-256
`2719310563A8DEFEA65C79DEAA4B8DE6B003999747B622E28C00001D21890D6A`

**Documentation authorization:** `DOC-FLICKER-05-2026-08-13` (user/controller;
expires at this report; documentation-only; uncommitted). It authorizes this
file only at base `c4c18a7c68f6fa7003d69ad13df6059fa412bc2d` and input SHA-256
`E05152356A83BCF311DEA58B3A323FA04BD1097E57E3BBD8EB67BB7015EDEA0C`.

This revision corrects the latest P0/P1 review findings:

1. Route A now follows the complete PLAN-V2-R3 reopen spine through Trace V2
   and `P-V2-P00`; this untracked candidate document cannot itself authorize a
   production task.
2. The supplied video is a hash-identified partial-participant signature. Exact
   decoding does **not** establish a full-black source frame; the video is not
   used to invent one as a required regression signature.
3. The primary oracle enters through the actual driver/state-machine path,
   including transparent EXP/skill pop, visible-state selection, repeat chains,
   visual update, draw-before-temp-state commit, `push_display`, and
   `update_display`. Direct `CombatState` calls are localization-only.
4. T01/T02/T04B/T05 now require causal frame mapping, complete immutable
   content-addressed input closure, transaction/fault coverage for cache mutations, lifecycle-aware
   pixel masks, a controller-pinned reviewer bundle, and exact reproduction of
   the supplied scenario.

It also removes duplicated acceptance and performance text. Root `plan.md`, the
indexed task packets, and immutable evidence manifests own those details.

---

# 0. Authority, Status, and Executable DAG

This file is a design and task-breakdown document. It grants no production,
test, Trace, Git, model-switch, phase-advance, or release authority.

The live controller currently authorizes no production recovery task. This
document remains candidate input only until the controller opens the root-plan
route and issues the required task packets.

## 0.1 Route A - recovery reopening

The normal recovery route is:

```text
P-V2-S00 Authority/provenance lock
    -> P-V2-B00 Historical acceptance and immutable oracle bootstrap
    -> P-V2-O01 Packet registry, validator, task index, coverage rows
    -> P-V2-D00 Document-topology migration or an enumerated isolated route
    -> P-V2-T01 Design Trace V2
    -> P-V2-T02 Implement Trace V2 and disprove observer effects
    -> P-V2-T03 Repeatability, PC recapture, immutable oracle lock
    -> P-V2-P00 Register hash-bound presentation child contract and graph edges
    -> FLICKER-T01A Reproduction and real-timeline evidence
    -> FLICKER-T01B Participant lifecycle and pair-ownership decision
    -> FLICKER-T02 Frozen red regression tests
    -> FLICKER-T03 Minimal presentation-atomic production fix
    -> FLICKER-T04A Mechanical verification
    -> FLICKER-T04B Independent semantic review
    -> FLICKER-T05 Runtime and optional performance characterization
```

`P-V2-S00`, `P-V2-B00`, `P-V2-O01`, `P-V2-D00`, `P-V2-T01` through
`P-V2-T03`, and `P-V2-P00` are defined only by root `plan.md`. This document
does not restate or weaken their model, evidence, validator, Trace, coverage,
presentation-contract, or acceptance contracts. `P-V2-P00` must register the
accepted child-plan hash at `recovery/presentation/<contract-id>.md` before a
flicker production task has authority.

The controller may replace only the `P-V2-D00` edge by an explicitly enumerated
isolated route under root `plan.md` Section 7.1.3. That exception still cannot
waive `P-V2-S00`, `P-V2-B00`, `P-V2-O01`, `P-V2-T01` through `P-V2-T03`,
`P-V2-P00`, an indexed validator-passing task packet, affected coverage-matrix
rows, frozen red evidence, or an immutable evidence manifest. A classification
outside this route requires a prior controller-approved revision of the root
plan and dependency graph; a child document has no opt-out authority.

## 0.2 Per-task execution contract

Every flicker task requires its own controller-approved
`recovery/tasks/<task-id>.md` packet.
Before execution, the packet must:

- satisfy root `plan.md` Section 7.1 completely;
- be present in `recovery/task_index.json`;
- pass the accepted deterministic packet validator;
- name exact affected semantic-coverage row IDs;
- name one immutable evidence-manifest output path;
- pin model/effort, base SHA, dirty baseline, allowlist, commands, exit codes,
  rollback, waivers, and result rules;
- record controller acceptance of every predecessor task.

No task self-advances. Completion always returns to the controller.

---

# 1. User-Visible Defect and Scope

Expected:

- living battle sprites remain continuously visible after the final attack when
  the locked lifecycle/reference says their pose is visible;
- they remain visible while EXP, level-up, or skill messages cover the scene
  when that reference frame expects participant pixels;
- they disappear only during the intended finish/leaving/fade sequence.

Observed from the supplied decoded source:

- the skill banner and both bodies remain visible through approximately 28.330 s;
- both bodies are fully visible at 28.350--28.383 s;
- UI/background remain visible while bodies are absent or below normal coverage
  at approximately 28.400--28.466 s;
- bodies visibly return at approximately 28.483 s.

The supplied contact sheet does not prove any full-black **source** frame.
“Full black” remains `UNCONFIRMED`; it may be investigated only if T01A produces
an exact decoded source frame and hash. These samples guide acquisition only;
T01A must lock frame index and PTS before a test can use them.

The supplied source video is external to the repository:

```text
PATH: C:\Users\ADMIN.DESKTOP-NG60QMN\Videos\Screen Recordings\Screen Recording 2026-08-11 105448.mp4
SHA-256: DC7E0CF81B9CD1A20A69149DAE56318BFF5C4AC32A09CDE2F88E724D795DF31C
OBSERVED DURATION: 48.234646 s
OBSERVED RASTER: 1920 x 1152
```

T01A must decode and record the following before the supplied symptom is called
confirmed:

```text
SOURCE VIDEO PATH + SHA-256 + FILE SIZE:
CONTAINER / CODEC / FPS / DECODER VERSION:
PROJECT FIXTURE + SHA-256:
CHAPTER / EVENT:
ATTACKER / DEFENDER / ITEMS:
TRANSFORM / PARTNER / DYING STATE:
PLATFORM / BUILD CLASS:
BUILD COMMIT + ARTIFACT SHA-256:
EXACT SOURCE FRAME INDEX / PTS FOR LAST-GOOD, ABSENT/LOW-COVERAGE, AND RESTORED FRAMES:
EXTRACTED FRAME PATHS + SHA-256:
HOST FRAME INDEX / TIMESTAMP / VIEWPORT / SCALE / WINDOW MODE:
STATE, POST-DRAW SURFACE, PRE-PRESENT FINAL SURFACE, AND PRESENT-CALL MAPPING FOR EVERY BAD FRAME:
```

The verified absent/low-coverage signature is the mandatory symptom. A
full-black signature is an optional independent hypothesis only after exact
source evidence exists; failure to reproduce it cannot fail a local flicker fix.
If the verified signature cannot be reproduced under the pinned fixture/build,
retain `PARTIALLY CONFIRMED` and make no production edit.

This defect is separate from the previously investigated Android freeze after
`fade_out`. Do not combine their fixes, instrumentation, tests, or verdicts.

Production scope is expected to remain:

```text
app/engine/combat/animation_combat.py
```

Test scope is expected to remain:

```text
app/tests/test_animation_combat_presentation_atomicity.py
app/tests/test_performance_profiler.py
```

`test_performance_profiler.py` is included only to remove the three obsolete
revert-state names from its source-string list. The new module owns the
behavioral presentation invariant.

Changing `app/engine/battle_animation.py`, project data, resources, Trace V1,
the comparator, manifest, normalizer, or goldens requires separate controller
authorization.

---

# 2. Verified Repository Facts

## 2.1 Provenance

- `29d1b65d8` and `69e26e931` stage other animation-combat work but do not
  introduce the post-EXP rebuild/pair render boundaries.
- `fff0145d5` splits the previously atomic post-EXP work into:

```text
revert_transform
-> rebuild_revert_animations
-> repair_revert_animations
-> initiate_revert_transforms
-> fade_out_wait
```

- `3ab40895e` restores authoritative combat transaction boundaries but retains
  this presentation staging.
- The staged post-EXP path exists on current `master` and
  `recovery/pc-core-semantics`.

Therefore `fff0145d5` is confirmed as the commit introducing the unsafe render
boundaries. Runtime evidence is still required to prove that those boundaries
are the cause of the supplied video.

## 2.2 Cache hits and misses can publish blank animation state

`battle_animation.get_battle_anim()` reaches `BattleAnimation.get_anim()`.

On a compatible registry hit, the cached object is reused and `clear()` sets:

```text
state = inert
current_frame = None
under_frame = None
over_frame = None
```

On a cache miss or different Revert resource, the new object is also initially
inert with empty drawable frame fields.

Consequences:

- a pending local variable is not necessarily non-mutating;
- a cache hit may clear the same object currently owned by the renderer;
- publishing the result may expose an inert or blank animation.

## 2.3 Pairing also invalidates drawable state

`BattleAnimation.pair()` selects Stand/RangedStand, resets the script, clears
all three drawable frame fields, and calls `reset_frames()`, which sets the
animation state to `run`.

The next normal `BattleAnimation.update()` reads the selected timeline until a
frame-bearing or waiting command is reached. The plan must not assume that one
update is sufficient for every real resource.

## 2.4 The production host may observe the early returns

The primary production path is:

```text
driver.update_game_state_for_frame()
-> driver.update_game_state()
-> StateMachine.update()
-> start/begin/input/update of top state
-> StateMachine.update_visuals() over visible states
-> StateMachine.draw() over visible states
-> CombatState.draw() -> AnimationCombat.draw()
-> StateMachine.process_temp_state() / repeat traversal
-> engine.push_display() -> engine.update_display()
```

When EXP/skill overlays are transparent, their pop/commit and the resulting
visible-state stack are part of the defect path. Returning `False` from
`AnimationCombat.update()` does not itself suppress drawing; the state machine
can still draw the combat underlay. Background, platforms, and UI are independent
of character frame fields. A direct `CombatState.update()`/`draw()` probe omits
the state-stack and host-present boundaries and is secondary localization only.

A valid character result is not equivalent to `current_frame is not None`.
Character pixels may come from `under_frame`, `current_frame`, or `over_frame`,
and may still become invisible through opacity, scaling, offset, clipping, or
blend behavior.

## 2.5 Dying/dead participants require a locked reference contract

`AnimationCombat.pair_battle_animations()` pairs every existing main and
partner animation. `BattleAnimation.pair()` can reactivate state and reset
drawable frames. Partner rebuilds do not have the same `is_dying` guard as main
participants, and cache-hit `clear()` can reset additional presentation state.

These are real lifecycle hazards, but they do not prove that the safe answer is
always to skip pairing. The accepted pre-`fff0145d5` path also paired existing
participants inside one atomic block, and a zero-opacity draw call is not a
visible resurrection.

T01B must therefore lock exact reference behavior before T02 freezes tests.

---

# 3. Root-Cause Hypothesis and Decision Outcomes

The unsafe presentation window begins in `rebuild_revert_animations`, not only
in `repair_revert_animations`:

```text
UPDATE A: revert_transform
    choose rebuild_revert_animations
    return before mutation

UPDATE B: rebuild_revert_animations
    get/reuse animations; a cache hit may clear a live object
    assign returned references as each lookup succeeds
    return before pair/update_anims

RENDER B:
    UI/background/platforms draw
    one or more living animations may be inert or blank

UPDATE C: repair_revert_animations
    pair existing animations and clear drawable frame fields
    return before update_anims

RENDER C:
    another blank character boundary may be exposed

UPDATE D: initiate_revert_transforms
    initiate required poses
    choose fade_out_wait
    common update_anims tail runs once

RENDER D:
    normal character pixels may return
```

Current diagnosis:

```text
REPOSITORY MECHANISM: CONFIRMED
INTRODUCING COMMIT: CONFIRMED - fff0145d5
MATCH TO SUPPLIED VIDEO: NOT YET CONFIRMED
OVERALL: PARTIALLY CONFIRMED
MASTER AFFECTED: YES
RECOVERY AFFECTED: YES
```

T01A must end with exactly one of these controller-review outcomes:

```text
A. LOCAL ONE-UPDATE PATH
    The real resource becomes visibly drawable after the one existing common
    update, and every locked bad source frame maps to a host-visible rebuild or
    pair boundary rather than final composition/present. Continue to T01B.

B. MULTI-UPDATE TIMELINE
   A valid resource intentionally needs more than one update. Stop. Request a
   separate design task for bounded non-mutating preparation/publication.

C. SECOND RENDERER OR STATE-MACHINE DEFECT
    A bad source frame is absent from the combat surface but exists on the
    pre-present/final surface, present boundary, compositor, or another state
    boundary; or an independently hash-locked full-black source frame is not
    explained by the local rebuild/pair timeline. Stop. Request a separate
    diagnosis task; do not widen the local fix.

D. SYMPTOM MISMATCH OR NO REPRO
   Reject or retain PARTIALLY CONFIRMED. No production edit.
```

T01A must construct a causal table for every locked bad frame. It maps source
frame index/PTS to the driver host-frame index, top and visible state stack,
transparent EXP/skill pop/repeat/commit status, `AnimationCombat` state,
cache/object identity mutation, combat-surface output, final pre-present output,
`push_display` input, `update_display` invocation/order, and next restored frame.
A plausible state name or matching screenshot is not causal evidence.

---

# 4. Presentation and Participant Invariants

For every approved living participant, the atomic presentation transaction is:

```text
obtain or reuse animation
-> publish the approved reference
-> establish approved pair ownership
-> select the intended Stand/Revert pose
-> run exactly one normal common animation update
-> CombatState.draw() produces the combat surface
-> compose the final surface
-> invoke the production-equivalent present boundary
```

No host-visible boundary may expose a cleared or partially initialized living
animation. Before intended finish/leaving, a participant expected visible by the
locked lifecycle mask must meet its reference mask/coverage rule on both combat
and final presented surfaces. A full-black final surface is independently
forbidden only when the locked scenario/reference expects a non-black frame.

For dying, dead, and inactive participants:

```text
dying -> match the locked reference fade mask and opacity window
dead -> zero pixels after locked terminal invisibility
inactive/missing -> zero pixels throughout
all -> preserve approved ownership/effect linkage
```

“Resurrection” means candidate pixels outside the locked reference-mask
tolerance, or any participant pixel after terminal invisibility. Draw invocation
alone is diagnostic evidence, not the final oracle.

## 4.1 Participant lifecycle matrix

T01B must replace every `TBD` before T02:

| Participant | Rebuild/publish | Call `pair()` | Pose/finish/leaving | Visible result |
|---|---|---|---|---|
| Living main | Valid animation only | Yes unless locked evidence rejects | Stand/Revert as characterized | Reference-visible frames meet mask |
| Dying main | TBD | TBD | Locked fade sequence | Reference mask/opacity window only |
| Dead main | TBD | TBD | Terminal invisibility | Zero pixels after terminal frame |
| Living partner | Valid active animation only | Yes unless locked evidence rejects | Characterized pose | Reference-visible frames meet mask |
| Dying/dead partner | TBD | TBD | Locked fade/terminal sequence | Reference mask/terminal-zero rule |
| Missing/inactive partner | No | No | None | Remain absent |
| Living lookup returns `False`/`None` | TBD fallback | TBD | TBD | No partial visible state |
| Mixed lookup results | Per participant | Per participant | Per participant | Successful sides remain valid; failed sides follow locked fallback |

For each row, T01B must declare the oracle class and source identity:

```text
PC_REFERENCE | SUPERSEDING_CORRECTNESS | PROPERTY | COMPOSITE
```

It must also record before/after object identity, unit role/lifecycle predicate
(`LIVING`, `DYING`, `DEAD`, `INACTIVE`), animation state/pose, frame fields,
opacity, reference mask/opacity window or terminal-invisibility frame, visible
pixels and alpha-covered area, ownership/parent linkage, pair fields, first
update result, first draw result, combat-surface result, final pre-present
result, and present-call result.

If a living participant cannot be paired without changing a dying/dead
counterpart or effect/timing ownership, the local design is rejected.

## 4.2 Pair-field parity

If T03 introduces a local participant-aware helper, tests must prove the exact
approved values for:

```text
owner
partner_anim
parent
right
at_range
init_position
entrance_frames
entrance_counter
```

For the current `pair_battle_animations(0)` path, the expected parity candidate
is `entrance_frames == 14` and `entrance_counter == 0`; T01B must confirm it.

---

# 5. Preferred Local Fix

Proceed only after T01A returns `A. LOCAL ONE-UPDATE PATH` and T01B returns
`LOCAL FIX CONFIRMED` with no unresolved matrix cell.

Before selecting a one-file implementation, T01B must create the root-required
`recovery/transactions/<flicker-combat-publication-id>.json` transaction contract
and coverage rows. The controller assigns the stable ID and path in the packet;
the contract uses the complete root `plan.md` Section 7.5 schema, including
owner/generation token, immutable input snapshot, thread-affinity, validation,
linearization point, ordered mutations, cancellation/timeout, reentry, stale
result, shutdown/exception cleanup, compensation, and every fault point. A field
may be `NOT APPLICABLE` only with controller rationale.

The contract inventories and snapshots/restores every mutable effect of
`get_battle_anim()`/`BattleAnimation.get_anim()`/`clear()`/`pair()`: registry
mapping and identity; `unit`/`item`; pose/state; `processing`, script/loop/wait
state and frame counters; all drawable frames; ownership/parent/pair/position and
entrance fields; child effects; opacity/death opacity; blend/flash/background/
foreground/screen-dodge fields; static/pan/offset fields including Android
offset; every `AnimationCombat` participant reference; and the combat-level
state/timer fields changed by the transition. Fault tests must prove field-for-
field equality of the full old presentation snapshot after each pre-commit
failure, not only frame/ownership equality. The contract defines `PREPARE ->
VALIDATE -> COMMIT` and one linearization point.

A one-file fix is permitted only if T01B proves that all lookups can be validated
without mutating a currently drawable shared object, or that every pre-commit
mutation is private/reversible and compensation restores the exact old coherent
presentation on each injected lookup failure. If a cache-hit `clear()` mutates a
live registry object before all validation completes and cannot be compensated,
reject the one-file design: stop and request controller-approved scope for a
non-mutating acquisition/clone or registry transaction in `battle_animation.py`.

Preferred conceptual shape, conditional on that transaction proof:

```python
elif self.state == 'rebuild_revert_animations':
    # PREPARE/VALIDATE private candidate participants and fallbacks.
    # Do not publish or mutate a live drawable shared participant yet.
    # COMMIT approved references, ownership, pose, and compensation boundary.

    self.state = 'fade_out_wait'

    # No early return. The existing common update_anims() tail runs once.
```

Remove the standalone host-visible boundaries represented by
`repair_revert_animations` and `initiate_revert_transforms`, or prove an
equivalent single-host-update flow. Prefer one clear state over a drain loop.
No lookup exception or `False`/`None` result may leave a previously valid live
participant cleared, re-owned, or only partially paired.

The fix must preserve:

- the `last_update` and `fade_out_wait` timer boundary;
- solver, action, RNG, hooks, cleanup, EXP/WEXP, support and death ordering;
- state-stack, pair-up, strike-partner, arena and skip semantics;
- one shared PC/Android lifecycle;
- existing Android presentation policy behind accepted boundaries;
- exactly one common `update_anims()` call.

The current rebuild state already performs all `get_battle_anim()` lookups in
one update. Do not claim that these lookups are currently distributed across
multiple frames.

T03 adds no profiler scope. If existing or external observers cannot isolate
the transition, stop and request a separate `FLICKER-T03P` instrumentation task
with its own observer-equivalence test, allowlist, evidence and rollback.

Reject without new controller-approved evidence:

- Android-only rendering workarounds;
- retaining stale frame fields globally through `BattleAnimation.pair()`;
- drawing cached old sprite surfaces;
- calling `update_anims()` manually and again through the common tail;
- looping through multiple timeline updates or skipping waits;
- changing `BattleAnimation.get_anim()` caching or global pair semantics without
  the separately authorized transaction scope;
- hiding dying participants instead of preserving their locked lifecycle;
- testing only state names or only `current_frame`;
- changing Trace/goldens to accept the candidate.

If the atomic state exceeds a locked performance budget, stop. A staged fallback
requires a separately reviewed non-mutating prepare/clone contract followed by
one atomic publication and likely expands into `battle_animation.py`.

---

# 6. Test-First Contract and Evidence Custody

## 6.1 Real-resource timeline prerequisite

Before creating a fake, T01A records the first visible character result for:

- normal Stand and RangedStand;
- the real Revert resource in the reproduction;
- each active partner animation.

Evidence fields:

```text
PROJECT FIXTURE + SHA-256:
RESOURCE NID + SHA-256:
UNIT / CLASS / ITEM / DISTANCE:
POSE:
FIRST TIMELINE COMMANDS:
NORMAL UPDATES UNTIL FIRST VISIBLE CHARACTER BLIT:
WAIT / LOOP / EFFECT COMMANDS BEFORE FIRST BLIT:
EXPECTED LAYER / RECT / OPACITY:
EXPECTED ALPHA-COVERED AREA OR HASHED PIXEL MASK:
```

If one common update is insufficient, use outcome B from Section 3. Do not make
the fake manufacture a property absent from the real resource.

## 6.2 Sequencing test

At `state == 'rebuild_revert_animations'`, model:

- cache hit clearing the same live object;
- cache miss returning a new inert object;
- `False` and `None` lookup results;
- mixed left/right/partner results;
- every locked participant-matrix disposition.

For every ordered mutation/side-effect boundary, inject `False`, `None` where
applicable, and a raised exception: each lookup/clear; every participant-
reference publication; pair/ownership mutation; pose initiation; `self.state`/
`last_update` mutation; and the common `update_anims()` tail. A cache hit that
clears a currently drawn object must be mandatory fault coverage, not conditional
on a test's reachability guess. The test must prove one explicit disposition:

```text
PRE-COMMIT failure -> exact old coherent presentation remains drawable
POST-COMMIT failure -> exact new coherent presentation remains drawable
```

Before COMMIT it must assert restored registry/object identity, all mutable
presentation/combat-transition fields, ownership/effect fields, and visible
masks. After COMMIT it must assert a completed new coherent presentation, or a
controller-approved fail-stop before any present. “The exception did not occur in
happy path” is not coverage.

One `AnimationCombat.update()` must prove:

- publication precedes approved pairing;
- pairing precedes approved pose initiation;
- the common animation tail runs exactly once;
- state reaches `fade_out_wait`;
- `last_update` starts the intended wait interval;
- no gameplay, solver, action, cleanup, hook, or state-stack method runs.

The test must fail on the buggy code because the first call publishes cleared or
inert objects and returns, not merely because a state name exists.

## 6.3 Mandatory production driver/state-machine/present oracle

The primary regression test must execute:

```text
driver.update_game_state_for_frame()
-> driver.update_game_state()
-> StateMachine.update() through transparent EXP/skill return
-> visible-state visual update and draw
-> temp-state commit/repeat traversal
-> engine.push_display()
-> engine.update_display()
```

T02 must drive the actual state stack from the transparent EXP/skill state
through pop/repeat/transition commit to combat. A synthetic call sequence is
invalid unless the packet proves exact production ordering, including visible
state selection and commit timing. Capture for each host frame the state stack,
combat-surface output after draw, final surface supplied to `push_display`,
`update_display` call count/order, and host frame index/timestamp. Direct
`CombatState.update()`/`draw()` tests may localize a failure but cannot be the
primary RED/GREEN oracle.

Use one instrumentation method locked before red capture:

1. tagged deterministic character surfaces observed at normal `engine.blit`; or
2. an off-screen pixel oracle with unique participant colors and exact rects.

Classify participant/layer blits separately from background, platform, UI, and
effects. Account for opacity, scaling, offsets, clipping, transforms, and blend.
The final assertion must additionally use an exact participant mask or a
reference-locked minimum alpha-covered area/rect coverage. A shadow, foot, or
few surviving pixels does not count as a living participant being continuously
visible.

Red assertion:

```text
mutation_boundary_crossed
AND before_intentional_finish_or_leaving
AND (
    expected_living_visible_blits == 0
    OR living_participant_coverage < locked_minimum_coverage
    OR final_presented_surface_is_unexpectedly_full_black
)
```

Green assertion:

```text
for every presented frame before intentional finish/leaving:
    derive expected_living_visible from the locked lifecycle matrix/reference
    every expected_living_visible participant satisfies the locked in-bounds
    mask or minimum alpha-covered-area/rect-coverage result
    every living participant in a locked wait/effect/transform/revert/
    opacity-zero window satisfies that exact zero/opacity/effect rule
    every dying participant matches its locked fade mask/opacity window
    every dead/inactive participant is zero after terminal/missing boundary
    no candidate pixel occurs outside a locked lifecycle mask tolerance
    final pre-present output matches the observed present result under the
    locked composition/tolerance rule
    no frame expected non-black by the locked reference is unexpectedly full black
```

Required variants:

1. normal non-transform left/right;
2. characterized Transform/Revert;
3. cache hit;
4. cache miss;
5. lookup `False`;
6. lookup `None`;
7. mixed lookup results;
8. pair-up/partner;
9. dying main;
10. reachable dying/dead partner;
11. missing/inactive partner;
12. skip path.
13. the locked absent/low-coverage source-frame signature, including coverage below the accepted
    participant threshold rather than only zero blits;
14. an optional full-black signature only if T01A decodes, hashes, and locks an
    actual full-black source frame;
15. every cache-mutation failure/exception disposition from Section
    6.2.
16. living participants in each locked wait, effect, transform, revert, and
    opacity-zero invisible window.

Initialize every global `game` field used by the fixture and run the tests both
alone and with relevant existing modules to detect order dependence.

## 6.4 Replace the brittle profiler source-string check

Remove only these names from `test_performance_profiler.py`:

```text
rebuild_revert_animations
repair_revert_animations
initiate_revert_transforms
```

Keep all unrelated performance/staging coverage. Do not replace the removed
names with another source-string invariant.

## 6.5 Cryptographic test freeze

T02 acceptance must record:

```text
FROZEN PRESENTATION TEST PATH + SHA-256:
FROZEN PROFILER TEST PATH + SHA-256:
FROZEN TEST-ONLY DIFF/CONTENT MANIFEST + SHA-256:
FROZEN SOURCE-VIDEO / EXTRACTED-FRAME MANIFEST + SHA-256:
FROZEN PRODUCTION / IMPORTED SOURCE CLOSURE + SHA-256:
FROZEN PROJECT / RESOURCE / FIXTURE MANIFEST + SHA-256:
FROZEN DRIVER / STATE-MACHINE / RENDER-PRESENT SOURCE CLOSURE + SHA-256:
FROZEN RUNTIME / INTERPRETER / DEPENDENCY / CONFIG FINGERPRINT + SHA-256:
FROZEN BASE TREE / ALLOWED-PATH DIFF-CUSTODY RULE + SHA-256:
FROZEN TRANSACTION / PRESENTATION CONTRACTS + COVERAGE-ROW IDS + SHA-256:
RED COMMAND + EXPECTED NONZERO EXIT:
RED ASSERTION SIGNATURE:
RED RAW LOG PATH + SHA-256:
BASE SHA + DIRTY BASELINE:
CONTROLLER ACCEPTANCE ID + DATE:
```

The T02 closure contains actual immutable bytes, not merely paths/hashes. T01A
through T05 use an isolated, read-only, hash-pinned reference checkout/process
and a separate isolated candidate checkout/process; neither may overlap the dirty
working checkout. Every evidence manifest records both tree/process identities
and pre/post dirty-custody results. The closure includes relevant source, tests,
fixtures/resources, video/extracted frames, contracts, command scripts, raw RED
logs, tool binaries/configuration, and manifests. Before green, T03 adds the
immutable candidate tree or allowed-path diff bytes and SHA-256 to the closure;
that candidate identity is then frozen for T04A/T04B. T03 must recompute all
frozen source and manifest hashes before editing and again before reporting green.
T04A and T04B must recompute them independently.

Any mismatch invalidates the frozen-red custody chain. Stop and return to T02;
do not explain the mismatch away or continue with modified tests.

T03 may edit only its authorized production path. T02 test edits remain
forbidden during T03.

---

# 7. Verification Layers

Exact commands, environment, expected exit codes, raw-log paths, and hashes
belong in the active task packet. The minimum logical layers are below.

## 7.1 Focused recovery-branch verification

The recovery packet should include the existing transaction and performance
modules plus the new presentation module:

```powershell
utilities\enemy_event_generator\.python\python.exe -m unittest `
  app.tests.test_animation_combat_presentation_atomicity `
  app.tests.test_animation_combat_transaction_order `
  app.tests.test_combat_transaction_order `
  app.tests.test_performance_profiler
```

## 7.2 Master-port verification

Cross-branch port is a separate controller task. The reviewed `master` does not
contain the two recovery transaction modules, so a port packet must discover
and pin branch-appropriate tests instead of claiming nonexistent modules passed.

## 7.3 Static and broad verification

After focused green, the packet must pin:

- `py_compile` for changed production and test modules;
- `mypy app`, or an explicit controller waiver with the exact baseline failure;
- `git diff --check` when Git operations are authorized by that future packet;
- full unit discovery, with pre-existing failures separated by locked signature;
- the complete allowed-path diff and protected dirty-path verification.

Focused green is never reported as full-suite green.

## 7.4 Trace V2 semantic non-regression

S7-style animation combat coverage is supplementary historical Trace V1 custody;
it cannot prove the visual flicker is gone or supply PLAN-V2 product equivalence.
Every production flicker task must instead use the accepted Trace V2 oracle lock
required by root `plan.md` Sections 7.1.4, 7.2, 7.4, and 7.10. The host-frame
test and runtime capture prove presentation; Trace V2 protects ordered gameplay
semantics.

The active packet must use an accepted V2 oracle lock and approved isolated
checkout whose raw custody preflight passes, or report `BLOCKED`. Never normalize
or edit Trace V1/V2 inputs to make comparison pass. Runner, comparator, manifest,
fixture, environment, reference, candidate, and V1-custody identities come from
the accepted lock and active packet, not copied values in this document.

## 7.5 Runtime verification

Desktop fix-correctness must include matched baseline/candidate captures for:

- the exact supplied skill/EXP-to-animation-combat scenario, with the locked
  absent/low-coverage and restored-frame signature range, plus a full-black
  range only if T01A independently locks real source evidence;
- normal melee with EXP;
- Transform/Revert with EXP;
- no-EXP and skip timing;
- one dying side with EXP.

Extended scenarios include ranged, level-up/skill messages, pair-up, strike
partner, arena, fast-forward, and every reachable locked lifecycle row.

Capture method, frame rate, build/artifact identity, project fixture, input
script, source-video/frame manifest, first post-EXP host frame, present-boundary
capture, and reviewed frame range must be identical between baseline and
candidate. The candidate must show the locked supplied signature absent, not
merely pass a generic transform/no-transform capture.

Android runtime is required only when the active packet claims Android runtime
equivalence or release. An unavailable target reports that verdict `BLOCKED`
without erasing independently proved desktop fix correctness.

## 7.6 Performance authority without duplicated thresholds

Root `plan.md` Section 20 is the sole authority for Android performance
qualification. This document intentionally copies no run count, device matrix,
statistical method, absolute budget, relative ceiling, thermal rule, observer
rule, sampling threshold, or exception policy.

The active T05 packet must import the then-current Section 20 contract verbatim
by identity/hash and pin its product-specific values before candidate
measurement. If this document and root `plan.md` ever differ, root `plan.md`
wins and the task stops until its packet is corrected.

WSA/emulator evidence remains characterization only. Missing physical devices,
same-device paired baseline, raw samples, p99-equivalent evidence, pre-locked
absolute budgets, or the required uncertainty decision reports Android
performance qualification `BLOCKED`, never PASS.

Verdicts remain independent:

```text
FIX CORRECTNESS
DESKTOP RUNTIME
ANDROID RUNTIME EQUIVALENCE
ANDROID PERFORMANCE QUALIFICATION
MERGE / RELEASE
```

---

# 8. Controller Task Matrix

Every task is sequential, uses the complete root `plan.md` Section 7.1 packet
contract (summarized in this document's Section 0.2), and
ends at a controller gate. Sections 3–7 own the detailed acceptance rules; this
matrix does not repeat them.

| Task | Primary recommendation | Owned output | Advance condition |
|---|---|---|---|
| `FLICKER-T01A` | Luna / low | Reproduction, decoded absent/low-coverage signature, real driver/state-machine/present timeline, custody preflight | Section 3 outcome A only |
| `FLICKER-T01B` | Terra / high | Lifecycle matrix, oracle classes, pair/effect ownership, registry transaction/compensation decision | `LOCAL FIX CONFIRMED`; no `TBD`; one-file scope proven or rejected |
| `FLICKER-T02` | Terra / high | Red production-pipeline tests and complete immutable input closure | Controller accepts red evidence, actual bytes, and hashes |
| `FLICKER-T03` | Terra / high | Minimal presentation-atomic fix, only if transaction scope remains local | Frozen tests green and unchanged; no stop trigger |
| `FLICKER-T04A` | Luna / medium | Mechanical/static/full-suite/Trace V2 evidence | Required non-waived checks have expected results |
| `FLICKER-T04B` | Controller-pinned model / effort | Independent read-only semantic and presentation verdict | `APPROVE` only |
| `FLICKER-T05` | Luna / medium | Matched runtime evidence for the supplied scenario and authorized performance evidence | Independent PASS/BLOCKED/FAIL verdicts |

Task-specific escalation targets:

- T01A: Terra / medium only for repository or evidence inconsistency; no
  lifecycle-semantic decisions.
- T01B: Sol / high only for named nonlocal lifecycle, symmetric-pair,
  effect-ownership, competing-oracle, or API ambiguity.
- T03: Sol / high only for named nonlocal, semantic, performance-boundary, or
  API-contract conflict. Stop before expanding scope.
- T05 unexplained failure requires a separately authorized Terra / high task.

T02 code authority is limited to the two test modules in Section 1. T03 code
authority is limited to `app/engine/combat/animation_combat.py` only after T01B
proves a private/reversible transaction; otherwise it is rejected and a separate
scope decision is required. Test edits are forbidden. T04A, T04B, and T05 are
evidence/report-only.

## 8.1 Independent T04B contract

- Reviewer is not the T03 author and uses a separate fresh-context session.
- Reviewer has no production or test write authority.
- Packet pins reviewer model/effort, reviewer identity/session separation, and
  the exact input hashes before T03 starts; the controller cannot select them
  after seeing the candidate result.
- Reviewer receives a read-only isolated checkout or immutable content-addressed
  bundle containing actual bytes for the accepted packet, base/candidate tree or
  diff, T01A video/extracted frames, T01B lifecycle/oracle sources, complete
  frozen source/test/resource/config closure, transaction/presentation contracts,
  raw RED/GREEN/T04A logs, present-boundary evidence, tool binaries/versions, and
  every manifest required to recompute their hashes.
- Reviewer independently recomputes every closure member and stops with
  `REQUEST CHANGES` on a missing byte, hash mismatch, ambiguous base/candidate
  identity, or an input outside the frozen manifest. Hash lists without the
  reviewable underlying bytes do not satisfy this contract.
- Report records reviewer/model/effort/session identity, input hashes, and
  timestamp.
- Verdict is exactly `APPROVE` or `REQUEST CHANGES` with ranked findings.

The reviewer must not fix findings. Changed inputs invalidate the review and
return control to the controller for a newly authorized task.

## 8.2 Required P-V2-P00 registration completion

This candidate document is not itself registerable as
`recovery/presentation/<contract-id>.md`. Before P-V2-P00 can register a
hash-bound child contract, the controller-authored completion task must supply
the exact contract ID, affected semantic-coverage row IDs, and Section 20
workload IDs, together with every root Section 7.10 field. The registration task
must bind those fields, this source-child-plan SHA, and graph edges before any
flicker packet is executable. A later task packet may not infer or silently fill
them from this prose.

## Cross-branch and Git disposition

No flicker task authorizes checkout/mutation of `master`, cherry-pick, merge,
rebase, stage, commit, push, tag, clean, reset, or history rewrite. Each requires
separate explicit controller/user authorization.

---

# 9. Universal Stop and Escalation Conditions

Stop without expanding scope when:

- branch, task, packet, model/effort, base SHA, dirty baseline, validator,
  coverage rows, oracle lock, or controller authorization does not match;
- the video does not match the rebuild/pair timing;
- a valid resource requires more than one normal update before visible output;
- a second renderer/state-machine defect contributes materially;
- a participant matrix cell, oracle class, ownership rule, or fallback remains
  unresolved;
- living pairing requires unapproved mutation of a dying/dead counterpart;
- a dying participant diverges from its locked fade mask/opacity window, or a
  dead/inactive participant emits pixels after its terminal/missing boundary;
- the fix requires global cache/pair API changes or another production module;
- frozen source, diff/content manifest, red-log, candidate-diff, or evidence
  hashes do not match;
- Trace inputs or accepted oracle identities drift;
- semantic traces diverge;
- a required test, tool, artifact, runtime, or device is unavailable;
- the local fix breaches a locked performance boundary;
- any unauthorized or protected path changes.

Escalation report:

```text
TASK:
TRIGGER:
EVIDENCE + HASHES:
SAFE WORK COMPLETED:
UNRESOLVED:
REQUESTED MODEL/EFFORT OR CONTROLLER DECISION:
GIT / DIRTY-WORKTREE DISPOSITION:
```

No task may weaken tests, semantics, performance gates, oracle custody, or
scope to avoid a stop condition.

---

# 10. Final Acceptance and Report

The final controller reviews the indexed packets, accepted predecessor SHAs,
coverage rows, immutable evidence manifests, frozen tests, candidate diff,
independent review, runtime captures, waivers, rollback anchors, and Git status.

Minimum final report:

```text
TASK RESULT: PASS | PASS WITH APPROVED EXCEPTIONS | PARTIAL | FAIL | BLOCKED
FIX CORRECTNESS: PASS | PASS WITH APPROVED EXCEPTIONS | PARTIAL | FAIL | BLOCKED
DESKTOP RUNTIME: PASS | PASS WITH APPROVED EXCEPTIONS | PARTIAL | FAIL | BLOCKED
SEMANTIC RECOVERY: PASS | PASS WITH APPROVED EXCEPTIONS | PARTIAL | FAIL | BLOCKED
ANDROID RUNTIME EQUIVALENCE: PASS | PASS WITH APPROVED EXCEPTIONS | PARTIAL | FAIL | BLOCKED
ANDROID PERFORMANCE QUALIFICATION: PASS | PASS WITH APPROVED EXCEPTIONS | PARTIAL | FAIL | BLOCKED
MERGE / RELEASE: AUTHORIZED | AWAITING AUTHORIZATION | BLOCKED

AUTHORITY ROUTE: RECOVERY REOPEN | ISOLATED EMERGENCY
TASK PACKETS / INDEX / VALIDATOR:
BASE / FINAL SHA:
DIRTY BASELINE / FINAL DIRTY PATHS:
ROOT CAUSE / INTRODUCING COMMIT:
LOCAL DESIGN VERDICT:
PARTICIPANT MATRIX / ORACLE RESULT:
PAIR / EFFECT OWNERSHIP RESULT:

FILES CHANGED:
BEHAVIOR CHANGED:
BEHAVIOR INTENTIONALLY UNCHANGED:

FROZEN TEST SOURCE / DIFF / RED-LOG HASHES:
SOURCE VIDEO / EXTRACTED FRAME / PRESENT-BOUNDARY MANIFEST HASHES:
RED / GREEN / HOST UPDATE-DRAW-PRESENT RESULTS:
FOCUSED / FULL / STATIC RESULTS:
TRACE V1 CUSTODY / TRACE V2 ORACLE RESULT:
ORACLE / RUNNER / COMPARATOR / MANIFEST / GOLDEN IDENTITIES:

DESKTOP CAPTURE RESULT:
SUPPLIED-SCENARIO FRAME-SIGNATURE RESULT:
ANDROID RUNTIME RESULT:
ANDROID PERFORMANCE CONTRACT IDENTITY:
ANDROID RAW EVIDENCE / DEVICE MATRIX RESULT:

WAIVERS:
KNOWN RISKS:
ROLLBACK ANCHOR / VERIFICATION:
ESCALATION USED: YES | NO
INDEPENDENT REVIEWER / INPUT HASHES / VERDICT:
COMMIT OR AUTHORIZED UNCOMMITTED DISPOSITION:
NEXT ACTION: CONTROLLER REVIEW | NONE
```

Never collapse verdicts. `FIX CORRECTNESS: PASS` does not imply semantic
recovery, Android runtime, Android performance, merge, or release approval. A
child-plan report may report `MERGE / RELEASE` only as `AWAITING AUTHORIZATION`
or `BLOCKED`; only a separate controller decision after matching root-plan
P9-T04-R3/P9-T05 closure can record `AUTHORIZED`. A task is not PASS when a
required non-waived check was skipped, blocked, or unavailable.

---

# 11. Engineering Principle

Performance staging may separate expensive preparation, but it must not publish
a partially initialized presentation object to a renderer.

For this defect, the atomic boundary begins when `get_battle_anim()` may clear
or replace a live animation, not only when `pair()` runs:

```text
prepare or mutate
-> publish
-> establish approved pair ownership
-> select intended pose
-> first valid normal advancement
-> draw combat surface
-> compose final surface
-> present
```

Presentation atomicity is participant-aware:

```text
living participant -> drawable whenever its locked lifecycle/reference expects pixels
dying/dead participant -> exact locked lifecycle and ownership,
                          reference fade mask then terminal zero pixels
```

Frame-field presence is diagnostic evidence. The final automated oracle is the
visible result produced by the normal host update/draw/present pipeline, backed
by an unchanged cryptographically frozen red test, source-video/frame evidence,
and an independently reviewed candidate diff.
