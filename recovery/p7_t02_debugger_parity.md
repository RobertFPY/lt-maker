# P7-T02 Debugger parity evidence

## Scope and semantic boundary

P7-T02 was executed with GPT-5.6 Luna / medium.  The shared semantic boundary
is `RuntimeDebuggerController.dispatch(op, args)`.  The desktop HTTP adapter
creates a `PendingCommand` and waits; `RuntimeDebuggerService.update()` drains
that queue and dispatches on the game thread.  `AndroidDebuggerState._run()`
dispatches the same operation shape directly.  No production debugger code was
changed.

The accepted contract is logical parity, not visual UI parity:

```text
same initial logical state + same op/args
    -> same controller validation/result/mutation/state transition
```

## Operation coverage

| Area | Shared controller operation(s) | Evidence |
| --- | --- | --- |
| Unit inspect/focus | `inspect_unit`, `focus_unit` | existing controller and Android selection tests |
| Unit fields | `set_field` for level/EXP/HP/mana/fatigue/guard/movement/position/stats/growths/caps/WEXP | `RuntimeDebugger.editable_fields` and dispatch tests; paired Android routing test |
| Unit progression | `max_unit`, `auto_level_unit` | runtime debugger/controller tests and Android mapping source |
| Items | `give_item` with optional `uses` | existing controller/runtime tests and paired Android routing test |
| Teleport/pick | `teleport`, `begin_pick_position` | controller implementation and Android action mapping; invalid destination is covered by runtime debugger tests |
| Batch | `max_players`, `max_enemies`, `enemy_hp`, `enemy_ai` | controller implementation and desktop hotkey mapping |
| World | `set_money`, `set_turn_count`, `set_turnwheel`, `set_weather` | controller implementation; paired `set_weather` route |
| Chapter/restart | `complete_chapter`, `go_chapter`, `restart_chapter` | existing runtime restart tests; Android confirmation mapping; P5 canonical-load suite |
| Event | `event_command`, `event_suggestions` | controller validation/catalog implementation; paired `event_command` route |

The Android route does not duplicate the operation implementation.  Its
`_activate()` method only translates drawer actions into the controller's
operation names and arguments.  Desktop Ctrl+1/2/3/4/5/0 is mapped by
`driver.check_runtime_debugger()` to `max_selected`, `max_players`,
`max_enemies`, `enemy_hp`, `enemy_ai`, and `complete_chapter`; the controller
owns the resulting mutation.

## Desktop service and threading

The test-owned local HTTP proof submits a real `/api/command` request.  Before
the game-thread `update()`, the controller has not been called.  One update
dispatches the queued operation once, signals the waiting request, and returns
the result.  A dispatch exception is converted to one failed result; a second
service update does not repeat it.  Snapshot polling calls `build_snapshot()`
without dispatching a gameplay command.

This preserves:

- no HTTP-thread gameplay mutation;
- one queue item -> one controller dispatch;
- timeout/error cannot replay a completed mutation;
- idle snapshot/catalog reads remain observer-only.

## Android frontend and touch/text behavior

`AndroidDebuggerState.blocks_fast_forward` remains `True`.  `begin()` installs
the real raw-touch consumer with UP/DOWN/LEFT/RIGHT passthrough, and `end()`
releases it.  `close_after` inserts the drawer pop before a queued Event
transition, preserving the accepted Event ordering.  Native editor Save,
Cancel/error handling and pygame text-input fallback remain in the existing
state; a consumed native result clears its request ID so a later poll cannot
submit the same command twice.

The parity tests exercise representative unit (`set_field`), world
(`set_weather`), and event (`event_command`) operations through Android
`_run()` and through the desktop service queue, comparing the exact operation
and argument pair sent to the shared controller.

## Observer and restart contracts

`build_snapshot()` and catalog construction read game state for presentation;
they do not dispatch gameplay operations.  S17 disabled/debugger-idle/
profiler-idle remains the accepted hybrid observer contract and was rerun
through the immutable recovery suites.  Restart remains in
`RuntimeDebugger.restart_chapter()` and P5's canonical load path: snapshot
first, matching `RESTART_SLOT` fallback only, explicit difficulty, chapter-start
initiative rebuild, and Android touch release before replacement.  No P5 code
was changed.

## Validation matrix

| Validation | Result |
| --- | --- |
| New debugger parity tests | PASS, 9 tests |
| Existing debugger/controller/Android tests | PASS |
| Focused combined debugger + fast-forward + canonical-load + atomic-restore + lifecycle tests | PASS, 121 tests |
| Recovery trace/golden integrity (including immutable fixture contracts) | PASS, 40 tests |
| Android/runtime + sound/platform/profiler/tilemap policy tests | PASS, 62 tests |
| Focused debugger/controller/Android tests | PASS, 44 tests |
| `python -m compileall -q app` | PASS |
| `git diff --check` | PASS |

`app.tests.test_debug_platform_routing` remains a known baseline import-order
failure when run in this checkout: `text_renderer`/`text_funcs` form a partial
circular import (`cannot import name 'text_width'`).  It is unrelated to the
P7-T02 files and was not changed.

No Trace V1 schema, normalizer, comparator, manifest, golden, save/restart,
combat, tilemap, or project-data change was made.  No debugger-specific parity
defect with an unambiguous production fix was found.

The accepted immutable scenario captures for S2, S4, S5, S16, S17 disabled /
debugger-idle / profiler-idle, and S18 remain unchanged; the recovery trace and
golden integrity gate passed without regenerating them.  Direct PC/reference
recapture was not needed because P7-T02 made no production or runner semantic
change.

## Known limits

This task provides deterministic source-level and local HTTP/threading proof;
it does not claim Android-device/JNI visual or touch hardware coverage.  The
native editor path is covered through the existing Android bridge tests and
the duplicate-submit guard; device IME behavior remains an external runtime
validation concern.

## Result

PASS — shared controller semantics and the bounded desktop/Android routing
contracts are covered.  Production changes: none.
