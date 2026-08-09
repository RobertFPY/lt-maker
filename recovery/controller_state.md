# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, model policy, and global escalation rules. Historical evidence remains in committed recovery reports and prior controller commits.

## Current authorization

- Current phase: **Phase 5**
- Phase 1 harness / immutable Trace V1 PC-reference goldens: **ACCEPTED**
- Phase 2 state-restore semantics: **ACCEPTED**
- Phase 3 combat lifecycle semantics: **ACCEPTED**
- Phase 4 tilemap/board/event atomicity: **ACCEPTED**
- P5-T01 save-format / compatibility audit: **ACCEPTED** at `f0abf0cb4f4aa05df9f6bff86a959f203d25553f`
- P5-T02 canonical transactional load API: **ACCEPTED** at `788d47c4dad8b9c2b4201fa50f58414bc5e98837`
- Active task: **P5-T03 only — Canonical restart contract**
- Primary model: **GPT-5.6 Terra / high**
- Escalation target: **GPT-5.6 Sol / max**
- Escalation pre-authorized: **NO**
- Phase 6+: **UNAUTHORIZED**
- Golden/reference fixture changes: **UNAUTHORIZED**
- Project-data / asset changes: **UNAUTHORIZED**
- Controller gate after P5-T03: **YES — STOP FOR CONTROLLER REVIEW**

## P5-T02 acceptance record

The controller accepts `788d47c4dad8b9c2b4201fa50f58414bc5e98837` (`fix(save): canonicalize load transaction`).

Accepted evidence:

- it is one direct descendant of the P5-T02 controller authorization commit `d9ed0367413e872de72873ac706e7bba648c68ec`;
- production changes stay within the authorized save/load/title/in-chapter/debugger surfaces; tests are bounded and no project data, Trace V1, comparator, manifest, or golden fixture changed;
- `save.load_game_data()` is the one authoritative main-thread load transaction used by desktop `load_game`/`GameState.load` and Android `SaveLoadJob` after worker-owned immutable read/unpickle;
- the transaction validates state-stack shape, controller compatibility, and explicit restart difficulty context before destructive hydration;
- saved S/Q stays local while `build_new` + `load_iter(..., replace_state_machine=True)` reconstruct registries/world/board/FOW/aura/events/controllers;
- phase/initiative compatibility is restored and the completed world validated before `install_state_machine()` publishes the final stack/destination exactly once;
- Android worker code never hydrates the singleton and no `load_iter` yield became a host-frame boundary;
- main-thread failure resets to a coherent title session; late restore/publication failure also restores Item/Skill UID globals and clears initiative progress rather than exposing a partial world;
- new initiative current-progress saves conditionally persist only bounded primitive compatibility state: phase current/previous team NIDs plus `unit_line`, `initiative_line`, and `current_idx`;
- non-initiative player-control, `start`, and overworld payloads do not receive the optional `controller_state` merely for symmetry, preserving default immutable save-payload traces;
- controller state validation rejects malformed/unknown/duplicate initiative units, mismatched lines, nonnumeric values, and invalid index bounds before final publication;
- legacy current-progress initiative payloads without exact tracker state fail explicitly rather than guessing or later dereferencing `None`;
- start/restart destinations rebuild chapter-start initiative state inside the same canonical transaction before publication;
- legacy `enemy_turn_change` context has a bounded compatibility restoration path using explicit `save_kind`, while new non-player saves persist exact phase current/previous state;
- Event/EventProcessor serialization remains intact; S3 stays `N/A — REFERENCE-UNSUPPORTED`;
- aura children remain derived/nonserialized; board/boundary/FOW/aura structures are rebuilt before publication; Phase-4 pending tilemap state is not save truth;
- SAVE_SLOTS and RESTART_SLOTS remain distinct contracts and route destination is explicit in `LoadTransactionContext`, not inferred from save kind inside the core API;
- immutable S1, S2, S4, S12, S17 disabled/debugger-idle/profiler-idle, and S18 were reported exact PASS; focused canonical/restore/Android/debugger/Event/save tests and compile/diff/show checks were reported PASS.

### Correction to prior P5-T01 reachability wording

Current `save.get_all_saves()` glob selects `*-turn_change-*` files and does **not** directly enumerate `*-enemy_turn_change-*` files. Therefore the earlier statement that Title Extras -> All Saves currently exposes enemy-turn-change files was too broad.

This does not invalidate P5-T02: the engine does create `enemy_turn_change` saves, and the explicit `save_kind == 'enemy_turn_change'` legacy restoration branch is bounded and safe if such a slot/context is supplied. Do not use the prior UI-reachability claim as evidence in later tasks unless source behavior changes.

## Accepted canonical load contract

Later tasks must preserve:

```text
immutable read/context
    -> compatibility validation
    -> one synchronous authoritative hydration transaction
    -> derived board/FOW/aura/controller reconstruction
    -> complete-world validation
    -> one S/Q + destination publication
    -> coherent loaded world
```

Desktop is synchronous. Android may move immutable file I/O and presentation off the gameplay path, but authoritative hydration and publication use the same core transaction.

P5-T03 may call/refine this API but must not fork or weaken it. If canonical restart semantics require a non-bounded change to `load_game_data()` architecture, STOP under ESC-02 / ESC-09.

## P5-T03 — authorized scope

Execute **P5-T03 only** using **GPT-5.6 Terra / high**.

Escalation target: **GPT-5.6 Sol / max**, not pre-authorized.

PC behavioral reference:

`9314f54b49f4552b5a3d023b4da0012ce7dfbc89`

Required later correctness semantics may supersede a proven reference limitation, but do not change unrelated save/load behavior.

### Goal

Define and implement one canonical **restart-current-chapter** contract shared by title Restart Level, game-over restart routing, debugger-triggered restart, and save-slot restart material.

The restart source must represent a **pristine current-chapter start**, never an accidental mid-chapter progress save and never a stale prior-chapter restart point.

The canonical concept is the existing `GameState.chapter_start_snapshot`: complete in-memory save payload captured after chapter setup (party/board/regions/FOW/unit arrival/initiative setup) and before LevelStart or later chapter mutation.

Do not turn ordinary SAVE_SLOT current progress into restart truth.

### Required restart invariants

1. **SAVE_SLOTS and RESTART_SLOTS remain separate.**
   - SAVE_SLOT = current progress.
   - RESTART_SLOT = pristine restart material for that slot's current chapter.

2. `chapter_start_snapshot` remains the in-memory pristine source for a chapter entered in the current process.

3. A normal save made while a valid current-chapter snapshot exists must seed/update the destination slot's restart material from that pristine snapshot, not from the mid-chapter save being written.

4. Saving from slot A into slot B must associate B with the current chapter's pristine restart point. Do not blindly carry a stale prior-chapter restart file merely because `old_slot == A`.

5. If no in-memory snapshot exists (for example after loading older current-progress material), an existing restart slot may be carried only when source evidence establishes it is valid restart material for the same current chapter. Do not fabricate pristine state from current progress.

6. If exact pristine restart material cannot be established for a legacy/current-progress path, fail/disable that restart route explicitly rather than silently restart from the wrong chapter or a mid-chapter save. If choosing the legacy fallback requires new semantics beyond this rule, STOP under ESC-04 / ESC-06.

7. The Test Chapter first-save path must no longer seed RESTART_SLOT from the first mid-chapter save when `chapter_start_snapshot` is available. Use the pristine in-memory snapshot.

8. Restart after game over in the same process must target the current chapter start even if no mid-chapter save has occurred since chapter entry. Prefer a valid in-memory snapshot where the route can identify the current session/slot safely; persistent restart material remains the fallback for fresh-process/title loads.

9. Debugger restart continues to prefer the in-memory pristine snapshot and may override difficulty only through explicit restart context. It must not rebuild from current progress.

10. Normal title Restart Level uses persistent RESTART_SLOT semantics and the P5-T02 `RESTART_LEVEL` transaction; overworld restart continues to use the matching main overworld SAVE_SLOT as already established.

11. New-game/start behavior remains valid and must not produce duplicate or conflicting restart sources.

12. Restart must reconstruct chapter-start initiative state deterministically under the P5-T02 compatibility contract; it must not restore current-progress initiative tracker state.

13. LevelStart mutations must occur after the pristine boundary exactly as intended by restart. Snapshot capture must not move later merely to simplify persistence.

### Restart identity / validation

Before using an in-memory or persistent restart source, prove it belongs to the intended current chapter.

Use source-proven identity such as saved level NID / target level context and slot/session ownership. Do not compare opaque pickle bytes or infer chapter identity from current unit positions.

A persistent RESTART_SLOT written from `chapter_start_snapshot` should have metadata sufficient for menus/debugger routing to recognize it as restart/start material. Preserve mode/level/title data; do not store gameplay-authoritative restart state only in metadata.

If a stale restart file is detected for another chapter, do not silently carry or load it as current-chapter restart material.

### Persistence design constraints

Prefer bounded changes to existing save/restart helpers.

The authoritative restart payload should remain a normal engine save payload readable by the P5-T02 canonical load transaction. Do not create a second bespoke restart serialization format.

Do not serialize `chapter_start_snapshot` recursively inside ordinary main-save payloads merely to retain it across process restarts. Persistent RESTART_SLOT already exists for that purpose.

If the implementation passes an in-memory snapshot to the save I/O thread, copy/freeze it before the thread begins so later gameplay mutation cannot alter restart bytes.

Keep main-save and restart-file writes deterministic and slot-keyed. Do not merge their file names or menu concepts.

### Save I/O failure behavior

Do not make a successful current-progress SAVE_SLOT silently point at corrupt/partial restart material.

Use the narrowest existing transaction/copy semantics possible. If making main-save and restart-save persistence fully atomic would require a new cross-cutting filesystem transaction architecture, STOP under ESC-09 rather than inventing it in P5-T03.

At minimum, restart write/copy failure must be surfaced/logged and must not be disguised as a valid pristine restart point.

### Required caller audit / implementation surfaces

Audit and reconcile at minimum:

- `GameState._capture_chapter_start_snapshot` / `level_setup_iter`;
- `save.suspend_game`, `save_io`, `_save_io`;
- SAVE_SLOTS / RESTART_SLOTS refresh and metadata;
- `TitleRestartState` desktop + Android paths;
- game-over -> title -> Restart Level behavior;
- `RuntimeDebugger.restart_chapter`;
- Test Chapter path where `current_save_slot is None`;
- save-to-different-slot carry-forward behavior;
- overworld restart special case;
- P5-T02 `LoadTransactionContext` / `LoadDestination.RESTART_LEVEL` use.

Expected primary production surfaces are `app/engine/save.py`, `app/engine/game_state.py`, `app/engine/title_screen.py`, and `app/engine/runtime_debugger.py`, with narrow adjacent changes only if required.

Do not change Phase-3 combat or Phase-4 tilemap/event semantics.

### Required tests

Add/retain focused tests proving at minimum:

1. snapshot is captured after chapter setup/initiative creation and before LevelStart mutation;
2. normal save writes current progress to SAVE_SLOT and pristine snapshot to RESTART_SLOT;
3. first Test Chapter save uses pristine snapshot, not current mid-chapter progress;
4. save A -> save B gives B the current chapter pristine restart point;
5. stale prior-chapter restart material is not blindly carried into a new chapter;
6. when no snapshot exists, valid same-chapter persistent restart material can still be carried where source-proven;
7. invalid/missing pristine legacy restart material is not silently replaced by current progress;
8. Title Restart Level desktop uses current-chapter RESTART_SLOT through canonical `RESTART_LEVEL` load;
9. Android title restart uses the same restart source/transaction semantics with worker-only immutable read;
10. overworld Restart Level continues using the main overworld SAVE_SLOT;
11. game-over restart returns to the current chapter start and does not inherit death/mid-chapter mutations;
12. debugger restart prefers snapshot, applies requested difficulty explicitly, and does not use current progress;
13. initiative restart rebuilds chapter-start tracker (`current_idx`/lines) rather than current-progress tracker;
14. restart slot metadata remains slot-keyed and recognized as restart/start material;
15. SAVE_SLOTS and RESTART_SLOTS remain distinct after save/delete/check refresh;
16. P5-T02 canonical load tests remain green and no second restart-specific hydration algorithm is introduced.

### Immutable proof

Run at minimum:

- S1 new game first playable;
- S2 normal save/load;
- S4 restart;
- S12 aura lifecycle;
- S18 game-over/restart.

S3 remains N/A.

Do not regenerate any golden.

If correcting the proven Test Chapter/pristine restart bug necessarily changes one of the immutable reference scenarios, STOP under ESC-03/ESC-06 before changing fixtures. S4/S18 should remain reference-compatible unless the scenario specifically exercises a later intended correctness fix already accepted by the controller.

Also run:

- `app.tests.test_canonical_load`;
- `app.tests.test_atomic_restore`;
- restart/save/title tests;
- runtime debugger tests;
- game-over tests;
- initiative/phase restart tests;
- recovery trace/lifecycle/golden integrity;
- Android load tests relevant to restart routing.

Run broader unittest discovery and report existing baseline failures/native Windows termination without fixing unrelated failures.

Finally run:

- `python -m compileall -q app`
- `git diff --check`
- commit bounded P5-T03 implementation/tests
- `git show --check`
- `git status --short`

### Explicitly out of scope

Do not:

- begin Phase 6;
- redesign the P5-T02 canonical hydration/publication architecture;
- merge SAVE_SLOTS and RESTART_SLOTS;
- use current mid-chapter save bytes as a pristine restart fallback when a snapshot is available;
- invent pristine legacy state from current progress;
- serialize `chapter_start_snapshot` recursively inside ordinary saves;
- add a generic save schema migration framework;
- re-enable arbitrary S3 mid-event save/load;
- modify Trace V1/comparator/manifest/goldens;
- modify project data/assets;
- merge master.

## Escalation / stop rules

Primary: **GPT-5.6 Terra / high**.
Escalation target: **GPT-5.6 Sol / max**.
Pre-authorized: **NO**.

STOP on:

- **ESC-02** restart root cause crosses into unrelated architecture;
- **ESC-03** immutable trace divergence not removable by bounded implementation;
- **ESC-04** multiple plausible legacy restart semantics require a controller choice;
- **ESC-05** restart invariant cannot be satisfied atomically/coherently;
- **ESC-06** old/current save compatibility conflict requires inventing migration or pristine state;
- **ESC-08** repeated bounded failure;
- **ESC-09** safe restart requires new cross-cutting filesystem/load architecture.

Do not self-escalate.

## Gate status

**P5-T02 is ACCEPTED. P5-T03 is the only authorized task. Phase 6 and later remain blocked pending P5-T03 controller review.**
