# P4-T03 Android pending board policy

## Decision

**RETAIN** Android-only progressive preparation of a pending tilemap, board,
and boundary.  The retained work remains strictly off-world.  P4-T02's single
synchronous authoritative commit remains shared by desktop and Android.

## Profiling gate

Methodology:

- Host-only benchmark on the current Windows checkout; no Android device was
  connected or measured.
- Loaded existing `default.ltproj` resources without changing project data.
- Used `TileMapObject.from_prefab()` and fully consumed
  `GameBoard.build_iter()` with the same pending-tilemap terrain resolver used
  by `change_tilemap`.
- Three warm-up iterations, then 25 timed iterations per map with GC disabled
  only during the timed loop.  Values are milliseconds from
  `time.perf_counter_ns()`; total is tilemap preparation plus board build for
  the same iteration.
- The reference budget is `TilemapChangeJob.FRAME_BUDGET_NS = 4_000_000`
  (4 ms).  This is host evidence of main-thread stall risk, not Android-device
  latency or an Android FPS claim.

| Workload | Dimensions | Tiles | Tilemap median / p95 | Board median / p95 | Total median / p95 | Budget relation |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Prologue | 15 x 10 | 150 | 1.599 / 1.776 | 1.026 / 1.117 | 2.643 / 2.863 | below 4 ms |
| Magvel | 30 x 20 | 600 | 3.265 / 3.551 | 3.740 / 4.152 | 7.076 / 7.380 | 1.8x p95 budget |
| Chapter 14B | 29 x 31 | 899 | 8.095 / 11.147 | 6.422 / 7.292 | 14.662 / 18.341 | 4.6x p95 budget |

The medium and large representative maps exceed the retained 4 ms work budget
by a material margin even on the host.  Retaining pending-only preparation is
therefore justified to avoid a single 7--18 ms host preparation stall.  Actual
Android hardware may differ and requires later device profiling before making
any device-frame claim.

## Semantic barrier

`Event._android_tilemap_pending` is a narrow Event-local barrier, set only by
the Android `change_tilemap` path before the pending job is registered.

While it is true:

1. `Event.update()` advances only the `tilemap_change` pending callback; it
   retains all other callbacks without invoking them.
2. `game.movement.update()` does not run.
3. `Event.take_input()` returns before skip handling or input listeners run.
4. The event remains blocked by its existing tilemap completion predicate, so
   its processor cannot fetch the next command.
5. `EventState` may keep the prior rendered surface through `_defer_render`;
   debugger/profiler idle reads see only the coherent old live world.

The update that finishes pending validation/commit still suppresses movement,
because it began with the barrier active.  The callback then clears the barrier
and render deferral exactly once, after the accepted P4-T02 synchronous commit
has returned (or after its synchronous rollback and failed job state).  Normal
callbacks and movement resume on the following outer Event update.

This is not a generic lifecycle scheduler and does not introduce a second game
or pending-world graph.  It only makes the already suspended Android event
command opaque while its pending objects are built.

## Production changes

- `app/events/event.py`: added the Event-local pending barrier to suppress
  unrelated callbacks, movement, and input listeners during Android pending
  preparation.
- `app/events/event_functions.py`: set the barrier when creating the Android
  tilemap job and release it when that job reaches either complete or failed.
- No live commit generator, incremental AddGroupJob, StateMachine change,
  Trace V1 change, fixture change, or project-data change was introduced.

## Tests and evidence

`app/tests/test_tilemap_change_job.py` proves:

- repeated pending build operations leave the old tilemap/board/unit/region
  state unchanged;
- only tilemap pending work runs while the barrier is active;
- movement and gameplay input listeners cannot mutate the old world;
- the existing blocked predicate prevents next-command processing;
- final commit remains the P4-T02 synchronous callback with no commit iterator;
- success releases the barrier once and resumes normal lifecycle on the next
  outer update;
- pending-build failure and commit failure retain the P4-T02 old-world and
  synchronous-rollback guarantees;
- synchronous `add_group` remains covered by its bounded regression test.

Required immutable comparisons S12, S13, S14, S15, and S17
(disabled/debugger-idle/profiler-idle) are run against unchanged fixtures.

## Tradeoff and risks

- Benefit: medium/large host maps no longer require their full pending build in
  one Android host frame.
- Cost: an Android event ignores gameplay input and holds movement for the
  duration of pending construction; this is deliberate opacity, not a gameplay
  ordering change.
- `_defer_render` remains presentation-only.  It does not provide semantic
  safety without the Event-local barrier.
- No Android-device timing was collected.  The policy should be revisited with
  actual device p95/max-frame evidence in a separately authorized performance
  task, not by weakening this barrier.
