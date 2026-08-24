# P7-T04 save/load/restart UX regression evidence

## Scope

This is a frontend-routing regression sweep only.  The accepted Phase-5
canonical transaction, save schema, restart-source precedence, and Android
worker ownership were not modified.

## Route inventory

| User-facing intent | Desktop route | Android route | Selected source/context |
| --- | --- | --- | --- |
| Title Load Game, current save | `TitleLoadState.take_input` -> `save.load_game` | `TitleLoadState._start_android_load` -> `SaveLoadJob` | selected `SAVE_SLOT`, `LoadDestination.SAVED` |
| Title Load Game, start/overworld save | same | same job/context factory | selected `SAVE_SLOT`, `START_LEVEL` or `OVERWORLD` |
| Title Restart Level, tactical | `TitleRestartState.take_input` -> `save.load_game` | same source -> `SaveLoadJob` | matching `RESTART_SLOT`, `RESTART_LEVEL` |
| Title Restart Level, overworld | same | same job/context factory | matching main `SAVE_SLOT`, `OVERWORLD` special case |
| Game over | `GameOverState` -> `title_start` -> Title Restart menu | same state route | no direct save/load; title restart validates source |
| Debugger Restart | shared controller -> `RuntimeDebugger.restart_chapter` | same semantic controller | matching in-memory snapshot first, then matching `RESTART_SLOT`; explicit difficulty |
| In-chapter Load | `load_save_slot` -> `save.load_game` | `InChapterLoadState` -> `SaveLoadJob` | selected `SAVE_SLOT`, destination from kind |

All authoritative paths converge on `save.load_game_data`.  `SaveLoadJob` is
limited to worker read/unpickle and calls the same transaction on the main
thread; title and in-chapter loader states are opaque presentation handoffs.

## Source and restart proof

The P7-T04 additions prove at the actual input-handler boundary that Title
Load chooses the selected current-progress `SAVE_SLOT` on both desktop and
Android routing paths.  The desktop context is `SAVED`; Android forwards the
same slot and then builds the matching `SAVED` context through its accepted
job seam.

Existing P5 contract tests plus this sweep prove the distinct restart cases:

- normal current-progress save and pristine restart payload remain distinct;
- tactical Title Restart selects only the matching `RESTART_SLOT` and uses
  `RESTART_LEVEL`;
- stale/wrong-chapter restart metadata is rejected before loading;
- the overworld exception selects its matching main `SAVE_SLOT`, never the
  restart payload;
- debugger chooses a matching `chapter_start_snapshot` before persistent
  fallback and carries the explicit difficulty context;
- Game Over only hands off to `title_start`; it cannot directly choose a
  mid-chapter `SAVE_SLOT` as restart truth.

## Atomicity and compatibility regressions

Existing `test_canonical_load` and `test_atomic_restore` cover one canonical
desktop/Android transaction, worker-only unpickle, one-time destination/S-Q
publication, invalid/legacy initiative failure before publication, and
failure reset.  `test_restart_contract`, initiative/phase canonical tests,
S12 aura, S13 FOW, and S14 tilemap contracts remain the accepted regression
proof.  No frontend bypass of `load_game_data` was found.

## Validation

The new title/game-over/overworld source tests pass in
`app.tests.test_restart_contract` (10 tests).  The focused P5/P7 batch passed
137 tests; the focused Phase-3/4/6/lifecycle/Trace V1/golden batch passed 131
tests.  Isolated recovery captures exactly matched immutable fixtures for S2,
S4, S5, S12, S13, S14, S16, S17 disabled/debugger-idle/profiler-idle, and
S18.  Capturing multiple scenarios in one Python process contaminated the
singleton aura registry before S12; its isolated capture passed exactly, so
this is recorded as the known shared-singleton test-isolation constraint, not
as a logical trace divergence.

Broader unittest discovery reproduced the known native Windows termination
`-1073740791` after pre-existing isolation failures.  It did not reach a
normal unittest summary.  This task's focused suites and isolated immutable
captures were green; the baseline was not repaired.

## Result

**PASS pending controller review:** no frontend routing defect was found and
no production code was changed.  This evidence does not claim visual or
device-file-picker parity; it proves source/context and canonical-transaction
parity only.
