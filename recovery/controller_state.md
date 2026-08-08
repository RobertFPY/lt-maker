# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules.

## Current authorization

- Current phase: **Phase 2**
- Phase 1 harness / persisted Trace V1 PC-reference goldens: **ACCEPTED**
- P2-T01 audit/map: **ACCEPTED**
- P2-T01 base audit commit: `a32a8d7a8d070fec2fe8320115ac69f93fc0e562`
- P2-T01-R1 destination correction: **ACCEPTED** at `304c044fb90c975c68292ab61434274caaad99c5`
- Active task: **P2-T02 only — Restore authoritative PC state semantics**
- Primary model: **GPT-5.6 Sol / max**
- Escalation target: **GPT-5.6 Sol / ultra**
- Escalation pre-authorized: **NO**
- P2-T03: **UNAUTHORIZED**
- Phase 3: **UNAUTHORIZED**
- Golden/reference fixture changes: **UNAUTHORIZED**
- Project-data changes: **UNAUTHORIZED**
- Controller gate after P2-T02: **YES — STOP FOR CONTROLLER REVIEW**

## P2-T01 acceptance record

The controller accepts `recovery/p2_t01_state_restore_map.md` as the authoritative Phase-2 restore map after R1.

Accepted findings:

- PC-reference and current desktop load/start/restart wrappers remain synchronous logical transactions because iterator work is exhausted before normal lifecycle resumes.
- Android `SaveLoadJob` safely performs immutable file read/unpickle off the gameplay path, but then mutates the live `GameState` incrementally over multiple main-thread frames.
- `prepare_for_load` destroys/clears authoritative live world fields before the replacement world is complete.
- `_staged_state_data` and `commit_staged_state` defer only saved state-stack installation; they do not make world hydration atomic.
- Android opaque loaders suppress normal input/map lifecycle during restore, but that containment does not satisfy INV-03 because authoritative singleton fields are still partial between frames.
- `chapter_start_snapshot`, save/restart slot semantics, aura re-derivation, FOW/board ordering, RNG state, later correctness fixes, debugger/profiler, fast-forward, Android audio/resource policy, and project content are protected behavior.
- `MapState`/transparent-map guards and staged-state compatibility fields remain P2-T03 candidates only after P2-T02 proves the invalid partial state impossible.

R1 also locks the exact destination-stack evidence:

- desktop/reference normal, start, restart, and overworld paths are reference-shaped and synchronous;
- current Android normal-save path consumes staged `S/Q` through state-machine replacement;
- current Android start/restart/overworld paths leave `_staged_state_data` stale;
- current Android title-overworld path appends two distinct `overworld` states because `_begin_post_load()` appends once and `_complete_load()` appends again;
- `StateMachine.load_states()` is append-only, so the double append is real;
- source/history/tests provide no evidence that duplicate `OverworldFreeState` instances are an intended feature;
- the reference-shaped overworld target is exactly one destination installation.

The remaining question is implementation mechanics for bounded transaction-local `S/Q` storage, not gameplay semantics and not a reason to reopen P2-T01.

## P2-T02 — authorized implementation contract

Execute **P2-T02 only** using **GPT-5.6 Sol / max**.

Primary goal: restore one authoritative PC-shaped state/load transaction while preserving later independent features.

### Governing invariants

- **INV-01:** one shared gameplay core.
- **INV-02:** PC reference is behavioral, not textual.
- **INV-03:** no observable partial gameplay state.
- **INV-04:** Android policy must not alter gameplay/state ordering.
- **INV-05:** shared optimizations must remain behavior/trace equivalent.
- **INV-06:** fast-forward may alter time/presentation only.
- **INV-07:** debugger/profiler are observers unless a mutating command is explicitly invoked.
- **INV-08:** preserve intended later features/fixes.
- **INV-09:** project content is protected.
- **INV-10:** performance retention requires semantic proof.

### Controller-selected architecture direction

P2-T02 is **not** authorized to invent a cross-cutting pending `GameState` architecture.

Use the smallest bounded design that satisfies INV-03:

1. **Retain Android worker-side immutable save-file read/unpickle.** Worker code may return save data/error only; it must not mutate gameplay state.
2. **Stop frame-slicing authoritative `GameState` hydration.** Once save bytes are available, authoritative restore must execute on the main thread as one synchronous logical transaction while an opaque loader owns input/presentation.
3. **Do not publish partial world fields.** No normal `State.start/begin/update`, input handler, debugger observer, or map consumer may run between the first authoritative restore mutation and completion of the final destination stack.
4. **Keep saved `S/Q` transaction-local until needed.** Prefer a bounded local/job-owned payload over long-lived singleton `_staged_state_data`. Do not create a second persistent gameplay-world object graph unless an ESC-09 architecture decision is explicitly authorized.
5. **Install destination exactly once at the transaction boundary.** Preserve the reference-shaped destination semantics documented by P2-T01-R1; specifically eliminate the current Android title-overworld duplicate destination append.
6. **Treat start/restart/overworld as explicit destination policies, not generic staged-stack retention.** Do not leave stale saved-state payloads after the transaction completes.
7. **Keep desktop public semantics synchronous and reference-shaped.** Do not regress existing desktop `save.load_game`, `GameState.load`, restart, title, or in-chapter behavior.
8. **Defer progressive world/board hydration to later phases.** P2-T02 must not solve atomicity by expanding Phase-4 board/tilemap architecture. Existing synchronous wrappers may be used to regain semantic atomicity.

### Required behavior by destination

Use `recovery/p2_t01_state_restore_map.md` as the exact source-level map.

At minimum preserve/restore:

- normal save: restored saved state stack `S` and pending `Q` become authoritative only with a complete restored world;
- Load Game `kind == 'start'`: preserve reference-shaped start-level destination and title handoff;
- Restart Level start save: preserve restart-slot semantics and chapter rebuild intent;
- overworld load/restart: install exactly one `overworld` destination state;
- in-chapter normal/start/overworld paths: no stale staged payload and no loader state surviving as unintended gameplay state;
- failure/abort: never leave a half-restored live world. Use a clean, deterministic recovery path without weakening save compatibility.

Do not change save bytes/schema, slot kinds, restart-file naming, or Test Chapter/restart compatibility behavior merely to simplify atomicity.

### Protected later behavior

Must preserve:

- `chapter_start_snapshot` intent and pristine capture point before `LevelStart` mutation;
- restart game/chapter functionality and `RESTART_SLOTS` behavior;
- aura child re-derivation / teardown correctness;
- FOW, regions, unit arrival, controller/event/RNG ordering;
- independent save metadata/legacy correctness fixes;
- fast-forward behavior under INV-06;
- debugger/profiler observer semantics under INV-07;
- Android streamed battle music and unrelated Android resource/render policy;
- project data/assets/resources.

### Authorized production surfaces

P2-T02 may modify only restore/state-orchestration production code required by the accepted P2-T01 map, primarily:

- `app/engine/game_state.py`
- `app/engine/save.py`
- `app/engine/title_screen.py`
- `app/engine/general_states.py`
- `app/engine/state_machine.py` only if a minimal explicit state-machine installation helper is necessary; preserve existing append semantics of `load_states()` for unrelated callers
- narrowly adjacent restore/reset code only when directly required by the transaction and reported explicitly

Tests may be added/updated only to prove the P2-T02 transaction. Do not modify Trace V1 semantics, comparator semantics, manifest, or committed golden JSONL bytes.

### Required implementation proof

Add focused tests that prove at minimum:

1. normal restore exposes no partial authoritative state between loader updates;
2. saved state stack is not installed before required world structures are complete;
3. Android title normal save reaches the same logical result as the PC-reference golden contract;
4. Android title start/restart uses one final destination policy and leaves no stale staged payload;
5. Android title overworld installs exactly one `OverworldFreeState`;
6. Android in-chapter normal/start/overworld paths leave no loader/staged residue beyond the intended destination;
7. failure/abort cannot expose a half-restored map;
8. `chapter_start_snapshot`, restart slots, aura/FOW/RNG ordering remain intact;
9. existing desktop load/restart behavior remains unchanged;
10. no change to immutable Phase-1 fixture hashes.

### Validation order

Run targeted restore/state-machine/title/in-chapter tests first.

Then run the immutable Phase-1 semantic evidence relevant to this task, at minimum S1, S2, S4, S12, S18, and the full recovery trace/lifecycle/golden suite.

Then run the broader unit suite required by `plan.md`. Existing unrelated baseline failures must be reported, not silently repaired in P2-T02.

Also run:

- `python -m compileall -q app`
- `git diff --check` before commit
- `git show --check` after commit

Do not alter expected goldens after a mismatch.

### Explicitly out of scope

Do not:

- begin P2-T03 or remove map/camera/null guards merely because the new transaction appears safe;
- redesign board/tilemap progressive construction beyond what is strictly required to stop live partial publication;
- repair combat/event/tilemap semantics assigned to later phases;
- revert `52bd0403` or `0821182a` wholesale;
- change save schema/slot semantics;
- change project data/assets;
- weaken Trace V1/comparator/golden expectations;
- merge to `master`.

## Escalation and stop rules

P2-T02 escalation target is **GPT-5.6 Sol / ultra**, but it is **not pre-authorized**.

STOP and request controller authorization on any applicable P2-T02 escalation trigger, especially:

- **ESC-02** nonlocal root cause crossing another correctness-critical subsystem;
- **ESC-03** deterministic Trace V1 divergence that cannot be resolved as a bounded implementation/test defect;
- **ESC-04** competing plausible gameplay semantics;
- **ESC-05** invariant failure;
- **ESC-06** save compatibility conflict;
- **ESC-08** repeated local failure;
- **ESC-09** need for a new cross-cutting architecture or persistent pending-world abstraction.

Do not self-escalate.

## Gate status

**P2-T01 is ACCEPTED. P2-T02 is the only authorized task. P2-T03 and Phase 3 remain blocked until P2-T02 receives controller review.**
