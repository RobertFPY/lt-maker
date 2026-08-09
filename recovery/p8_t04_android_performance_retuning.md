# P8-T04 Android-only performance retuning

**Task/revision:** P8-T04 at `a65dbceebec8b43ecb13f300ca8bf453d1462ebe`.
**Result:** **PASS — NO ADDITIONAL PRODUCTION RETUNE JUSTIFIED.**

## Measurement environment

This checkout has host Python/pygame evidence only. `adb` is installed, but
`adb devices -l` did not return a device/daemon result within the bounded
probe and was terminated; there is no Android-device frame-time distribution,
heap measurement, or profiler capture for this task. Consequently no FPS or
device performance claim is made, and no numeric work budget or cache capacity
is changed.

Existing P8-T03 host evidence remains supporting-only: title smoke removes 300
prefill passes (about 3,289 Smoke updates in its deterministic harness) with a
31-run median of roughly 878 us to 32 us. It is an already accepted baseline,
not retuned here.

## Android policy inventory and decisions

| Candidate | Owner/capability | Current knob/value | Baseline evidence and expected benefit | Risk/trace coverage | Decision |
| --- | --- | --- | --- | --- | --- |
| Pending tilemap preparation | `work_budget.tilemap_prepare_budget`, `TilemapChangeJob`; CAP-WORK-BUDGET | Android enabled, `deadline_ns=4_000_000`; desktop disabled/zero. | Existing P4/P6 tests prove only pending TileMap/GameBoard/Boundary work yields. A new deadline could trade jank for longer opaque load. | Event-local barrier blocks movement/input/next command; commit/rollback are synchronous. S14 protects transaction. No device evidence. | **KEEP-AS-IS.** |
| Tilemap barrier/render deferral | `Event._android_tilemap_pending`; CAP-WORK-BUDGET correctness boundary | Existing Event-local pending flag and `_defer_render`. | Not a throughput knob; it protects old-world visibility while pending work runs. | Changing it would expose partial board/unit/region/aura/FOW or alter Event order. | **REJECT-SEMANTIC-RISK.** |
| Highlight/title/menu/settings/Sound Room/info/debugger caches | Owner-local CAP-RENDER-CACHE | Existing revision/key invalidation; title/settings/Sound Room retain local static surfaces. | P8-T02 tests prove cache hit/miss/fallback behavior, but this task has no Android hit-rate, rebuild count, or memory distribution proving a capacity/enabling change. | Menu/input/observer semantics and S13/S17 are protected. | **DEFER-NO-DEVICE-EVIDENCE.** |
| Unit menu content cache | Unit-menu CAP-RENDER-CACHE | `OrderedDict` cap 4. | Current cap is bounded; no evidence that evictions cause Android jank or that a larger cap benefits representative navigation. | Larger cache increases memory and must retain selection/invalidation contract. | **DEFER-NO-DEVICE-EVIDENCE.** |
| Animation-combat UI layers | `AnimationCombat` CAP-RENDER-CACHE | Health/gauge/bar-strip caps 8; name cap 4; arrow cap 6. | Existing cache keys/invalidation and owner tests are accepted. No device hit/miss, allocation, or memory capture justifies capacity retune. | S7/S8/S16 protect combat/fast-forward. Source-frame cache remains rejected. | **DEFER-NO-DEVICE-EVIDENCE.** |
| Streamed music/preload/flush | `SoundController`; CAP-AUDIO/CAP-RESOURCE | Existing streamed-success and cached fallback; caller owns music NID/order. | No device decode/preload stall distribution. | A changed preload/flush lifetime can alter backend failure/timing; P6 contract protects fallback. | **KEEP-AS-IS.** |
| Title smoke seed | `particles.seed_title_smoke`; CAP-RENDER-CACHE/presentation | Accepted direct settled Smoke construction. | P8-T03 already proved bounded work reduction and presentation-only contract. | Must not reopen distribution contract or require pixel identity. | **KEEP-AS-IS.** |
| Empty Event overlay skip | `Event._draw_overlay_if_present`; CAP-RENDER-CACHE | Skip `to_surf` only when no renderable content. | Existing owner test is structural/presentation evidence. | Must not become Event scheduling or hide non-empty overlay. | **KEEP-AS-IS.** |
| MockCombat/BattleAnimation visual progression | Android presentation paths | Draw-owned visual counters move with accepted Android simulation presentation path. | Preserves effects under deferred intermediate draws; no new measured isolated reduction. | Retuning crosses fast-forward/combat presentation lifetime. | **REJECT-SEMANTIC-RISK.** |
| Battle source frames | `BattleAnimation.get_image`; not an approved cache | Always copy source before draw-specific transforms. | P8-T03 found no complete immutable layer or device bottleneck proof. | Flash/dodge/opacity/grayscale/tint/blend/child effects are mutable/time-dependent. | **REJECT-SEMANTIC-RISK.** |
| GC-REGION | `GameState.get_region_under_pos` | Not certified safe. | Explicitly not a performance candidate. | Pre-publication invalidation gap. | **REJECT-SEMANTIC-RISK.** |
| Styled text cache | tagged text/font registry | Existing cache only; isolated `FONT['convo']` baseline fails. | No valid test environment for allocation/hit/miss claim. | Cannot certify output fallback. | **DEFER-NO-DEVICE-EVIDENCE.** |

## Profiler and semantic boundary

Current scopes distinguish `tilemap_change.*`, `combat_frame_fetch`, combat UI
build/blit, title particles, Event overlay, input/update/present, and sound.
They are observers, not knobs. No current profiler capture identifies a new
Android-only owner-local bottleneck whose before/after result exceeds noise.

No production retune was made. Therefore the following stay exact:

* no Event command deadline, command batching, action batching, or gameplay
  worker work;
* off-world tilemap work only, with the existing barrier and one live commit;
* canonical load/restart publication, combat lifecycle, fast-forward input
  edges, debugger commands, and profiler observer behavior;
* cache keys, invalidation, bounded capacities, stream fallback, and title
  smoke behavior.

## Validation record

Focused isolated P8/Phase 3–7/recovery suites and the immutable Trace V1 gate
are run for this task and recorded in the task report. Full discovery is also
run only to document the unchanged component-registry/import-isolation/native
Windows baselines. No golden, schema, project-data, asset, or production file
is changed.

## Deferred evidence needed for a future retune

Any later numeric tilemap budget or cache-capacity retune needs representative
Android-device profiler distributions, repeated before/after samples, bounded
memory/hit-miss evidence, owner fallback tests, and exact Trace V1 comparison.
The current host-only evidence is insufficient for those decisions.
