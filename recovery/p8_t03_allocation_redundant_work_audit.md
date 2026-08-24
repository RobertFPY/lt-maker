# P8-T03 allocation/redundant-work audit

**Task/revision:** P8-T03 at `88a4ac57d11502302b10160bdd3ddea654685c03`.
**Reference:** `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`.
**Scope:** audit plus deterministic title-smoke contract test. No production,
Trace V1, project-data, or asset change was made.

## Method and excluded work

Fresh source inventory covered `copy_surface`, `Surface.copy`, conversion,
scaling, tint/translucency, repeated composition/layout, particle startup,
combat UI, damage/transient visuals, and profiler-labelled work. A source hit
is not itself a defect: candidates below have an explicit owner and lifetime.

`GC-REGION` is excluded. It remains not certified safe; this task neither
reads, benchmarks, changes, nor reuses it. Styled-text allocation is also
deferred because its isolated `FONT['convo']` baseline cannot provide valid
optimization proof.

## Candidate inventory

| Owner | Hot path/frequency and work | Mutable inputs/lifetime/output | Measurement and possible reduction | Risk, trace coverage, decision |
| --- | --- | --- | --- | --- |
| `particles.MapParticleSystem.prefill` / `seed_title_smoke` | Title initialization only. Desktop calls `update()` 300 times; Android samples settled Smoke ages directly. | Owner is TitleStart/TitleSelect title-particle system. Output is presentation-only Smoke population, with exact abundance and normal later update/draw lifetime. Inputs are bounds, abundance, and presentation RNG. | 31 deterministic runs (seeds 1701–1731, warmed/repeated harness): prefill median 878,300 ns, 300 system updates, 3,289 Smoke updates and 134 resets; seed median 31,700 ns, zero updates and 16 resets. Both produce 11 Smoke particles. | Static combat/growth/other RNG state is unchanged; source contains no Event, GameState, state-stack, input, save, or action access. S17/S18 plus title owner tests protect observer/state behavior. **KEEP-PLATFORM — PRESENTATION/RESOURCE POLICY.** |
| `BattleAnimation.get_image` and `draw` | Every visible battle frame copies the source, then may scale, flash, screen-dodge, opacity-convert, grayscale, tint, blend, partial-blend, and composite children/background. | Frame source is shared; output depends on frame, left/right orientation, entrance counter, flash, opacity, blend/partial blend, current time/flicker skill state, dodge, palette/effect state, offsets, and children. | `combat_frame_fetch` profiler scope exists, but no stable immutable pre-transform layer covers all paths. Existing evidence does not establish a sustained hot-path bottleneck. | Copy protects source from later mutable/draw-specific transforms. S7/S8/S16 cover lifecycle/fast-forward. **REJECT — MUTABLE/ORDERING/LIFECYCLE RISK.** No frame cache. |
| `animation_combat.py` bars/gauges/names/tints/arrows | Repeated combat UI composition during animation draw. | Owner-local bounded caches use display identity, HP/gauge/tint/frame inputs; cached output is a surface only. | P8-T02 owner tests already prove hit/miss and bounded invalidation. This task found no unmeasured new reduction beyond existing caches. | No solver/action/RNG/hooks/cleanup write. S7/S8/S16 exact. **NO-OPPORTUNITY.** |
| `mock_combat.py` damage numbers/visual animations | Draw-deferred Android transient visuals progress from update. | Presentation objects only; timing is tied to the accepted fast-forward presentation policy. | No safe allocation reduction isolated without changing visual lifetime. | Moving it again would cross the P7 fast-forward boundary. **REJECT — MUTABLE/ORDERING/LIFECYCLE RISK.** |
| `highlight.py`, `menus.py`, settings/info/unit-menu caches | Per-draw static highlight/table/layout/text composition. | Local revision/layout/visible-unit keys; dynamic cursor/selection remains uncached. | Existing P8-T02 tests cover bounded cache hit/miss/invalidation. No new repeated allocation lacking an owner-local cache contract was found. | S13/S14 and UI tests protect FOW/selection. **NO-OPPORTUNITY.** |
| `bmpfont`, dialog/tagged text, UI framework layout | Repeated glyph/text/layout surface construction. | Text/font/effect inputs may be mutable through loaded font registry and dialog state. | Styled-text isolated tests fail before trustworthy hit/miss measurement (`KeyError: 'convo'`). | No new cache or lifetime extension can be certified. **DEFER — INSUFFICIENT PROOF.** |
| `sound.py` preload/flush and streamed preview | Resource lookup/backend preparation, not gameplay work. | P6-owned audio/resource lifetime and caller-owned music selection. | Already bounded by P6 policy; no new repeated-work measurement warranted. | Must not change Event/combat/title ordering. **KEEP-PLATFORM — PRESENTATION/RESOURCE POLICY.** |
| Profiler labels/counters | Diagnostic scopes and counter collection. | Profiler-owned state only. | No production allocation target: changing counters would not prove gameplay benefit. | P7-T03 observer contract applies. **NO-OPPORTUNITY.** |
| Commented styling decorators/demo/template cache strings | Not active runtime behavior. | No runtime owner. | No work measured. | **DEAD/UNUSED.** |

## Title smoke presentation contract and proof

The accepted title contract is intentionally distribution-based, not a pixel
golden. With title particles enabled, either path must create only `Smoke`,
retain exactly `system.abundance` particles, and keep every live particle in
the normal smoke lifetime envelope (`x <= WINWIDTH`, `y >= -32`). Its source
spawn bounds remain the title bounds; subsequent ordinary `update()` and
`draw()` own removal and rendering. Exact positions may differ.

`app.tests.test_title_smoke_seed` proves fixed density/family/envelope,
unchanged static seed/combat/growth/other RNG state, and that seed performs no
prefill update while `prefill()` performs exactly 300. `seed_title_smoke` uses
Python presentation `random`, as does desktop prefill; this is deliberately
separate from engine `static_random`. Source inspection confirms it touches
only the passed particle system and does not dispatch Event commands, mutate
gameplay/state-stack/input/save state, or affect title music/navigation.

The measured removal is meaningful: 300 whole-system passes and thousands of
particle updates are replaced by bounded direct construction. It is therefore
retained as **KEEP-PLATFORM — PRESENTATION/RESOURCE POLICY**. No pixel identity
claim or screenshot golden is required or added.

## Battle-frame transform proof

`get_image` copies the stored source before optional horizontal flip. `draw`
then derives frame-specific surfaces through entrance scaling; flash and
screen-dodge caches; opacity/translucency; grayscale; time-dependent skill
flicker tint; background blend; and partial blend. Several helpers copy/fill
their input, while some hold a previous transformed result (`flash_image` and
`screen_dodge_image`). The result can depend on current draw state, current
time, unit skill state, palette/effect ownership, child effects, and blend
state. No complete immutable key can be proved cheaply for every path, so a
source-frame cache is rejected rather than guessed.

## Semantic boundary and validation

No candidate is permitted to batch Event commands, actions, combat cleanup,
live tilemap/load publication, or input/fast-forward substeps. The existing
P4 off-world tilemap barrier remains the only progressive preparation path.

Focused suites passed when isolated: title-smoke seed, cache memoization,
Android performance/render, animation-combat ordering, tilemap job, canonical
load, fast-forward, debugger parity, profiler observer, recovery trace, and
golden integrity. Running them as one combined process reproduces the known
shared component-registry `_Uses.tag` pollution; isolated runs pass.

Immutable Trace V1 comparator passes: S5, S7, S8, S12, S13, S14, S15, S16,
S17 disabled/debugger-idle/profiler-idle, and S18. It ignores only approved
header provenance (`runner_revision`, `platform_profile`); all logical records
match the locked fixture. S2/S4 were not needed: production title/load/restart
code was not changed.

## Remaining risks and controller boundary

Host timing is a sanity measurement only, not device profiling. Title smoke is
certified only as presentation policy under its distribution contract; it does
not claim desktop/Android pixel equality. A future battle cache needs complete
transform-family proof and device evidence. The styled-text registry baseline,
GC-REGION ordering gap, and any optimization requiring lifecycle/scheduler
changes remain outside P8-T03 and require controller review.
