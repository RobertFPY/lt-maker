# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules.

## Current authorization

- Current phase: **Phase 2**
- Phase 1 harness: **ACCEPTED**
- P1-T02 trace harness: **ACCEPTED**
- P1-T03 scenario evidence and persisted Trace V1 goldens: **ACCEPTED**
- P2-T01 executor commit reviewed: `a32a8d7a8d070fec2fe8320115ac69f93fc0e562`
- P2-T01 controller result: **PARTIAL — R1 REQUIRED**
- Active task: **P2-T01-R1 only — correct exact Android destination-stack audit**
- Primary model: **GPT-5.6 Terra / high**
- Escalation target: **GPT-5.6 Sol / max**
- Escalation pre-authorized: **NO**
- P2-T02 implementation: **UNAUTHORIZED**
- Production gameplay/state-machine/save behavior changes during P2-T01-R1: **UNAUTHORIZED**
- Tests/goldens/project-data changes: **UNAUTHORIZED**
- Controller gate after P2-T01-R1: **YES — STOP FOR CONTROLLER REVIEW**

## Phase 1 acceptance record

Phase 1 remains accepted at the immutable Trace V1 fixture set under:

`app/tests/fixtures/recovery_traces/v1/`

The PC reference remains:

`9314f54b49f4552b5a3d023b4da0012ce7dfbc89`

No Phase 1 golden may be regenerated, changed, weakened, or replaced by recovery output.

## Controller review of P2-T01 commit `a32a8d7a...`

### Accepted portions

The commit is correctly bounded to a single audit document:

`recovery/p2_t01_state_restore_map.md`

It is a direct child of the controller authorization commit `d49abcf7e73a3e1f6fd99e70ba3b7709e54aa51e`; no production, test, golden, or project-data file is changed.

The following high-level findings are accepted:

- desktop `GameState.load` / `start_level` wrappers remain synchronous logical transactions because their iterators are exhausted in one call;
- Android `SaveLoadJob` performs background save-file reading only, then advances live `GameState` restore work over multiple main-thread frames;
- `prepare_for_load` tears down authoritative live fields before restore completion;
- `_staged_state_data` / `commit_staged_state` defer only the saved state stack, not the world mutation itself;
- Android title and in-chapter loaders hide normal input/map lifecycle while the singleton is nevertheless incrementally mutated;
- this is containment, not INV-03 atomicity;
- `chapter_start_snapshot`, restart slots, save format, aura re-derivation, debugger/profiler, fast-forward, and Android resource/audio policy are protected later behavior;
- `MapState`/transparent-map null guards and staged-state fields remain P2-T03 candidates only after P2-T02 proves the invalid partial state impossible.

The reported classification totals are internally consistent across 28 mapped surfaces:

- `KEEP-SHARED`: 10
- `KEEP-PLATFORM`: 1
- `REWRITE-PLATFORM`: 5
- `RESTORE-PC-SEMANTICS`: 6
- `REMOVE-WORKAROUND`: 2
- `KEEP-CORRECTNESS-FIX`: 4

### Blocking audit gap

The Android title-overworld transaction map is not exact.

Current `TitleLoadJobState._begin_post_load()` does this for `next_action == 'overworld'`:

`game.load_states(['overworld'])`

and returns `True`. The same update then calls `_complete_load()`, whose `next_action == 'overworld'` branch calls:

`game.load_states(['overworld'])`

again.

`StateMachine.load_states()` appends each requested state directly to `self.state`; it is not idempotent and is not a replacement operation.

Therefore the current Android title-overworld path appends **two** `overworld` state objects before queuing `title_wait`. The P2-T01 report currently describes only one installation and does not include this concrete current-state-stack divergence in its unresolved destination policy.

By contrast, current `InChapterLoadJobState` appends `overworld` once, and the PC-reference desktop title load/restart path restores the saved stack synchronously and then appends `overworld` once.

This matters directly to P2-T02 because its first design obligation is to define the exact destination stack before implementation. P2-T01 cannot be accepted while the audit omits a concrete duplicate append in that path.

This is a bounded audit/documentation defect, not a production repair request and not a reason to escalate model tier.

## P2-T01-R1 — authorized correction

Resume P2-T01 only using **GPT-5.6 Terra / high**.

May change only:

`recovery/p2_t01_state_restore_map.md`

Do not modify production code, tests, Trace V1, manifest/goldens, save data, or project data.

### Required corrections

1. Correct the Android title save-load transaction map to show the exact current overworld behavior:
   - `_begin_post_load()` appends `overworld` once;
   - `_complete_load()` appends `overworld` a second time;
   - then `title_wait` is queued/processed.

2. Correct the function/classification rows for `TitleLoadJobState` and any destination-policy row so the duplicate append is explicit and classified. Treat provenance as evidence only; do not repair it in P2-T01-R1.

3. Add an explicit destination-stack matrix covering at minimum:
   - PC-reference desktop normal save load;
   - current desktop normal save load;
   - PC-reference/current desktop `kind == 'start'` load/restart;
   - PC-reference/current desktop `kind == 'overworld'` load/restart;
   - current Android title normal save;
   - current Android title `start`/`restart_level`;
   - current Android title `overworld`;
   - current Android in-chapter normal save;
   - current Android in-chapter `start`;
   - current Android in-chapter `overworld`.

For each row record:
   - saved stack payload from `s_dict['state']`;
   - whether/when it is installed;
   - whether `_staged_state_data` is consumed or left stale;
   - every explicit destination state append/replacement in order;
   - final committed stack shape before the next normal lifecycle update.

4. Compare the title-overworld path against PC reference `9314f54b...` and state whether the double append is:
   - a demonstrated current Android divergence/workaround defect, or
   - required by some later intended feature.

Do not infer intent from comments. Use exact source/history and existing tests/evidence.

5. Update the unresolved-controller-decision section so it no longer treats saved-stack policy as a vague retain/discard question. State the exact reference-shaped target for each save kind as far as the source establishes it, and isolate any truly unresolved case.

6. Correct the wording that calls P2-T02 “already-authorized”. P2-T02 is plan-defined as `GPT-5.6 Sol / max` but remains controller-blocked until P2-T01 is accepted.

### Controller direction for the later P2-T02 design

Do **not** invent a cross-cutting pending `GameState` abstraction during R1.

The controller's default P2-T02 direction, subject to final R1 review, is:

- keep Android worker-side immutable save-file read/unpickle and unrelated resource preparation;
- stop time-slicing authoritative `GameState` hydration across frames;
- perform authoritative world restore on the main thread as one synchronous logical transaction while an opaque loader owns input/presentation;
- hold the saved destination stack non-authoritatively until required world structures are complete, then install the final state machine/destination at the transaction boundary;
- do not preserve `_staged_state_data` as a long-lived singleton field if a bounded local transaction payload can replace it;
- defer any future progressive board/world hydration to later phases unless it can be proven to build outside authoritative live state and publish atomically.

This direction intentionally favors semantic recovery over retaining a frame-budget optimization whose current implementation mutates live gameplay state.

R1 must not implement this direction.

## Validation for R1

Run without modifying tests:

- `python -m unittest app.tests.test_recovery_trace app.tests.test_state_machine_lifecycle app.tests.test_recovery_golden`
- `git diff --check`
- commit only `recovery/p2_t01_state_restore_map.md`
- `git show --check`

Report the corrected destination-stack matrix, the exact title-overworld conclusion, validation results, and commit SHA.

Then **STOP FOR CONTROLLER REVIEW**.

## Escalation

P2-T01-R1 escalation target remains **GPT-5.6 Sol / max**, not pre-authorized.

STOP on ESC-01, ESC-02, ESC-04, or ESC-09. Do not self-escalate.

## Gate status

**Phase 1 remains ACCEPTED. P2-T01 is PARTIAL pending R1. P2-T02 remains UNAUTHORIZED.**
