# P7-T01 Fast-forward equivalence evidence

## Contract and runner

Fast-forward OFF is the recovery semantic baseline.  ON must produce the same
Trace V1 records and terminal logical state; host frames, draws and host time
are intentionally not compared.

`FastForwardScenarioFrameDriver` is test-owned.  It retains each existing
scenario's state-readiness input script, holds the real `FAST_FORWARD` input,
and routes each outer frame through `driver.update_game_state_for_frame()`.
The first substep receives the real logical input; later substeps receive the
driver's empty-input path.  It does not alter scenario fixtures, checkpoints,
normalization, comparator behavior, or project data.

## ON/OFF matrix

| Coverage | Scenario / proof | Result |
| --- | --- | --- |
| Map combat, RNG/actions/playback/EXP | S5 | PASS |
| Simple combat and cleanup | S6 | PASS |
| Animation combat presentation lifecycle | S7 | PASS |
| Base combat/item use cleanup | S8 | PASS |
| Move, cancel, Wait and FOW | S13 | PASS |
| Phase transition | S15 | PASS |
| Event chain, interactive dialog/menu and game-over/restart | S18 | PASS |
| Speed invariance | S6 OFF vs 200%, 300%, 800% | PASS |
| Presentation fence / blocking state / repeat chain | existing focused driver and state-machine lifecycle tests | PASS |
| Debugger/profiler idle | immutable S17 disabled/debugger-idle/profiler-idle | PASS (observer baseline; no new observer command) |

Every paired scenario compared complete Trace V1 records with
`trace.compare_records()`.  Inputs were sent only at the existing scenario's
real readiness conditions (for example real Free/Move/Menu, game-over stasis,
and title menu readiness), never by matching host-frame number.

## Input-edge proof

`test_fast_forward_equivalence.py` proves raw SELECT, BACK, START, RIGHT,
TEXTINPUT and mouse-click transients are visible only to substep one; all later
substeps see an empty raw-event snapshot. Existing `test_fast_forward.py`
covers held directional state, repeat chains, blocking-state entry, and one
forced presentation draw.

## Result

No logical divergence was observed.  No production code was changed.  The only
runner change is the bounded test-owned outer-frame adapter required to reuse
the existing scenario readiness scripts for ON/OFF execution.
