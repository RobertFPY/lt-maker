# P9-T04 final release candidate review

**Task:** P9-T04 - Final release candidate review

**Result:** PASS - suitable for final controller review

**Behavioral reference:** `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`

**Recovery starting HEAD:** `0821182a717de2baaf52a699ee325241ffaddd03`

**Release-candidate HEAD:** `4b756738f051391e751de3a54fc61238f566f861`

## 1. Authorization and scope

P9-T04 was executed under the live controller authorization at
`4b756738f051391e751de3a54fc61238f566f861`, on branch
`recovery/pc-core-semantics`, with GPT-5.6 Sol / max. Sol / ultra was not
authorized or used. This task reconciles accepted evidence; it does not alter
gameplay, tests, build policy, project content, Trace V1, or Git history.

The expected unrelated zero-byte untracked file
`recovery/pc-core-semantics` was inspected read-only and left untouched. Git
metadata writes, staging, commits, tags, branch switches, and merge operations
were not attempted. Merge to `master` remains unauthorized.

## 2. Starting HEAD

| Item | Verified value |
| --- | --- |
| Branch | `recovery/pc-core-semantics` |
| Starting/current HEAD | `4b756738f051391e751de3a54fc61238f566f861` |
| Approved recovery start | `0821182a717de2baaf52a699ee325241ffaddd03` |
| Recovery start parent | `9004c67bd9427917d27dd7d7e258bad898e910ff` |
| Range | Inclusive `0821182a^..4b756738`; 107 commits including the starting commit, 106 after it |
| Ancestry | Recovery start is an ancestor of HEAD; all 106 later commits have exactly one parent |
| Initial worktree | Only `?? recovery/pc-core-semantics` |

The approved start commit itself predates the recovery task sequence and is
the controller-selected baseline. No merge, history gap, or unexplained
commit appears between it and the release-candidate HEAD.

## 3. Recovery commit range

### 3.1 Implementation, test, evidence, and audit commits

The following task-output commits are listed in chronological phase order.
Hashes are uniquely abbreviated; the exact endpoints above are full hashes.

| Phase | Ordered task-output commits |
| --- | --- |
| Setup | `0821182a7` approved start; `0ccc9ac4c` recovery plan; `4473e8059` recovery override; `292547f69`, `b36a794d4`, `7f2a0cc50` model/gate alignment |
| P0 | `2f43d80ec` baseline; `d57a2fbd9` change inventory |
| P1 | `37a8be4de` Trace V1 schema; `d7538402c` schema revision; `a036be233` harness; `d64fbdb34` adapters; `adc9ec753` semantic oracle; `869d03692` scenario evidence; `6f1da4bcc` immutable goldens |
| P2 | `a32a8d7a8` restore map; `304c044fb` destination correction; `0a6b854e0` atomic restore; `9efad11a9` staged-workaround removal |
| P3 | `ab16e7a14` combat map; `c20b9e02f` Simple/Map ordering; `3ab40895e` Base/Animation ordering; `090a72d98` preservation audit |
| P4 | `5c94701d9` tilemap map; `02f959b98` atomic event commits; `b8563c8e4` Android pending barrier |
| P5 | `280b5fec9` save audit; `f0abf0cb4` phase/initiative audit; `788d47c4d` canonical load; `4059a2af5` pristine restart |
| P6 | `017e73c31` capability map; `cb217eb4b` audio/resource policy; `3c8c5479d` semantic Event scheduling/work-budget boundary |
| P7 | `874c7adcf` fast-forward equivalence; `11f2a42cd` debugger parity; `9fcefdf8f` profiler equivalence; `6613d2b07` save/load/restart UX routing |
| P8 | `1d40f89cf` cache audit; `3d8624136` render/batching audit; `869e30d66` title-smoke proof; `849bf7544` Android retuning audit |
| P9 | `dcf9c937a` PC matrix; `50e733998` recovery-test isolation; `392a8f5fb`, `81670bb6c`, `f3b5330a3`, `23f31e9e6`, `8d3e3f7c9` Android gate/blocker evidence; `981593e78` x86_64 build policy and final Android evidence; `14f93b42c` contamination audit/docstring correction |

### 3.2 Controller-state and governance commits

These are separated from implementation/audit outputs. Within each row they
remain in chronological order.

| Phase | Ordered controller/governance commits |
| --- | --- |
| P0 | `e99404b8f`, `0521ba8d1`, `092297d2a` |
| P1 | `87b1f2982`, `390972a1b`, `587266571`, `13c94e6c4`, `3bb86cd30`, `84af45101`, `343104cbb`, `93f608a1d`, `10be72014`, `caa63c45b`, `782221a2b`, `4957b2014`, `2e3806464`, `ed8e60317`, `371451792`, `a01e90166`, `bc22af5bc`, `65a299c29`, `72cc9da59`, `d49abcf7e` |
| P2 | `cf9188f01`, `864bbd160`, `c2d52c605`, `b6bec12dd` |
| P3 | `08b3389ea`, `1b79b0801`, `2d6f4e7cd`, `6ad10d13c` |
| P4 | `953595c4d`, `78f0befe0`, `58f06f6cb` |
| P5 | `b00c345ed`, `e45442a17`, `d9ed03674`, `4422419e0`, `12319eba1` |
| P6 | `a90ed76be`, `887877114`, `fc3f1812f` |
| P7 | `6a28b2687`, `487af528a`, `802023ce2`, `da7c38950` |
| P8 | `ec0c98cbb`, `88a4ac57d`, `a65dbceeb`, `b13b85b1c` |
| P9 | `d54decd31`, `4c7f418f4`, `a890539c5`, `d8388ee30`, `a20d538b7`, `dfa5f9ef6`, `4b756738f` |

All commits are associated with an approved setup step, task, evidence stop,
controller decision, or task acceptance. No unexplained history gap or
unassociated commit was found. History was inspected only; it was not
rewritten.

## 4. Architecture summary

The final branch has one shared gameplay core. Desktop and Android differ only
at bounded platform/presentation seams.

1. **Authoritative world transaction.** GameState hydration is synchronous on
   the game thread. Internal iterators expose profiling/dependency phases but
   are drained inside the transaction. Saved active stack S and pending queue
   Q remain local until the complete world is validated and installed once.
2. **Combat transaction.** Solver results, actions, playback, hooks, cleanup,
   EXP and `end_combat` retain one shared ordering. Natural presentation waits
   remain, but Android does not split authoritative combat work across host
   frames.
3. **Tilemap transaction.** Desktop builds and commits synchronously. Android
   may progressively prepare only pending TileMap/GameBoard/Boundary objects
   off-world. The Event-local barrier blocks movement, input and later Event
   commands until one synchronous live commit or synchronous rollback.
4. **Canonical load.** Desktop and Android call the same `load_game_data`
   authority. Android workers perform immutable read/unpickle only; board,
   aura, FOW, controllers, compatibility state, UID and S/Q publication belong
   to the main-thread transaction.
5. **Canonical restart.** SAVE is current progress. RESTART is source-proven
   pristine chapter-start material: matching current-session
   `chapter_start_snapshot` first, otherwise a matching persistent
   RESTART_SLOT. Wrong/stale material and progressed SAVE fallback are rejected.
6. **Platform policy.** SoundController owns physical streamed/cached backend
   behavior; resource workers prepare immutable presentation resources;
   owner-local render caches retain pixels only; the sole work budget is the
   4,000,000 ns Android off-world tilemap preparation budget.
7. **Observers and controls.** RuntimeDebuggerController is the shared semantic
   boundary. Desktop HTTP only queues; Android touch UI maps to the same
   operation/arguments. RuntimeProfiler records main-thread diagnostics only.
   Fast-forward changes host/presentation timing, not logical outcomes or input
   edges.
8. **Build boundary.** arm64-v8a remains the default Android ABI and x86_64 is
   supported as an explicitly selected build ABI. ABI selection and strict ELF
   verification live in editor/build tooling, not gameplay runtime logic.

## 5. Invariant-by-invariant status

| Invariant | Final status | Evidence |
| --- | --- | --- |
| INV-01 - one gameplay core | PASS | P6 capability map, shared load/debugger/tilemap owners, P9-T02 WSA synchronization points, P9-T03 direct-branch audit |
| INV-02 - PC behavioral reference | PASS | Locked Trace V1 S1, S2, S4-S18 exact; S3 remains reference-unsupported; P9-T01 exact baseline classification |
| INV-03 - no observable partial state | PASS | P2 atomic restore, P4 pending/off-world barrier, P5 canonical load publication, P9-T03 iterator/worker audit |
| INV-04 - Android platform policy only | PASS | P3-P6 transaction recovery, P9-T02 real runtime evidence, P9-T03 no duplicate authoritative path |
| INV-05 - shared optimizations trace-equivalent | PASS | P7 equivalence suites and P8 cache/render audits; no unexplained Trace V1 delta |
| INV-06 - fast-forward is time/presentation only | PASS | P7-T01 ON/OFF and 200/300/800 evidence, S16, final fast-forward sanity |
| INV-07 - debugger/profiler are observers | PASS | P7-T02/P7-T03, S17 three modes, final debugger/profiler sanity |
| INV-08 - intended later features preserved | PASS | P5-P7 functional matrices and P9 desktop/WSA routes |
| INV-09 - project content protected | PASS | P9 project/base integrity, no `default.ltproj` range diff, no current project/asset diff |
| INV-10 - evidence before optimization retention | PASS | P4 measurements, P8 inventory/measurement/equivalence audits, P8-T04 no-retune decision, P9-T02 characterization without knob changes |

No invariant remains unresolved.

## 6. Preserved feature list

| Feature | Final evidence and result |
| --- | --- |
| Fast-forward and speed controls | P7-T01 proves OFF == 200/300/800 logical outcomes, first-substep transient input, blocking state and presentation fence; S16 and WSA fast-forward pass |
| PC debugger | Shared controller/service, hotkeys and one game-thread dispatch proved by P7-T02 and P9-T01; preserved |
| Android debugger | Same controller op/args, touch ownership, close ordering and no double submit proved by P7-T02 and WSA; preserved |
| Runtime profiler | Disabled inert, ON/OFF equivalent, real worker-scope isolation and GC cleanup proved by P7-T03/S17; preserved |
| Restart current chapter | P5-T03 pristine snapshot/persistent fallback contract, P7-T04 source-routing proof, S4 and WSA restart; preserved |
| Game-over restart | Source-proven pristine restart and title handoff covered by P7-T04/S18; preserved |
| Save/load enhancements | Canonical transaction, additive phase/initiative correctness state, explicit legacy incompatibility failure, aura/FOW reconstruction and Android worker boundary all pass |
| Independent correctness fixes | One-use/broken cleanup order, LTCache post-publication invalidation, promotion finalization, aura teardown/reconstruction, and legacy tint guard remain protected |
| Android build support | Existing arm64-v8a route preserved; active/requested ABI now drives strict validation |
| Android x86_64 / WSA | Current-provenance x86_64 APK statically verified, installed and launched on WSA; previous ELF/SIGSEGV failure absent |
| Android streamed audio/resources | Caller-owned semantic selection, stream-success/fallback-once policy and immutable resource preload pass host tests and WSA backend/log evidence |

## 7. Removed/replaced staging and workaround inventory

| Original mechanism | Final state / disposition | Why | Final semantic boundary | Evidence |
| --- | --- | --- | --- | --- |
| Android staged GameState restore and frame-visible `load_iter` hydration | **REMOVED/REWRITTEN.** `_staged_state_data` and `commit_staged_state` are absent; canonical transaction drains iterators | Partial live GameState and early S/Q were invalid | Immutable read may be background; all authoritative hydration/publication is one main-thread transaction | P2-T02/T03, P5-T02, atomic/canonical-load tests, P9-T03 |
| Deferred saved S/Q and saved-state publication | **REMOVED.** S/Q is transaction-local and installed exactly once | Loader residue and mixed old/new state were possible | Complete world validation and UID finalization precede publication | P2/P5 tests and S2 |
| Deferred chapter snapshot workaround | **REWRITTEN.** `chapter_start_snapshot` is retained as deep-copied pristine data captured before LevelStart, not a second live world | Restart needs source-proven pristine material | Snapshot selection belongs to restart source resolution; hydration still uses canonical load | P5-T03, P7-T04, S4/S18 |
| Staged Simple/Map/Base/Animation combat sequence | **REMOVED/REWRITTEN.** Authoritative solver/actions/hooks/cleanup ordering is shared; only natural visual waits remain | Host-frame splitting changed action/order visibility | One combat semantic transaction through cleanup/end; rendering may pace presentation only | P3 commits/tests, S5-S11, P9-T02 combat |
| Live staged tilemap/board publication and incremental live AddGroup | **REWRITTEN.** AddGroup is synchronous; Android tilemap work builds pending structures off-world | Live detach/publish/restore exposed partial board/unit/region state | Event-local barrier plus one synchronous live commit or rollback | P4 commits, S12-S14, WSA tilemap |
| Camera/map guards introduced around partial restore | **PARTLY REMOVED; independently valid guards RETAINED.** Stage-only workarounds were removed, while no-map/title/overworld/debugger guards remain | Retained guards prevent legitimate presentation/inspection crashes and do not hide partial state | Guards validate optional presentation/map context; they do not own publication | P2-T03 and P9-T03 H-01 through H-06 |
| Generic Android Event 2 ms command deadline and `_android_process_yielded` lifecycle | **REMOVED.** No replacement wall-clock or command-count scheduler exists | Event command order is gameplay-semantic | Commands run until command-created wait/dialog/pause/block/complete or `waiting_for_present` boundary | P6-T03, state-machine tests, static absence checks |
| Worker-thread live gameplay mutation | **REMOVED/CONSTRAINED.** SaveLoadJob reads/unpickles only; save worker serializes frozen data; audio workers own resources only | Workers cannot publish GameState, actions, Event, solver, units or board | Worker output is immutable/job-local; game thread owns authoritative commit | P5/P6 and P9-T03 worker audit |
| Android gameplay-semantic forks | **REMOVED/REJECTED.** Retained branches are touch/presentation/audio/resource/off-world preparation/build policy | One gameplay core is mandatory | Platform selects HOW presentation/resource work occurs, never gameplay result/order | P6 map, P7 parity, P9-T02/P9-T03 |

Historical audit statements that describe the original unsafe mechanisms are
not final-state contradictions. P2-T01 and P4-T01 are before-state maps;
P5-T01's Test Chapter risk was fixed by P5-T03; P6-T01's unresolved Event
deadline was rejected and removed by P6-T03; P8-T04's lack of a device was
superseded by the accepted P9-T02 WSA run.

## 8. PC behavior-equivalence evidence

**PC BEHAVIOR EQUIVALENCE: PASS.**

- Immutable Trace V1 comparisons are exact for S1, S2 and S4-S18, including
  S16 fast-forward and all three S17 observer modes. S3 remains explicitly
  N/A / reference-unsupported and was never re-enabled.
- P9-T01 reproduced the authoritative Windows full-suite baseline exactly
  after a recovery-test-only class-lifetime correction: 311 observed OK,
  8 FAIL, 1 ERROR, followed by the same native `-1073740791 / 0xC0000409`
  termination near the same editor workspace test. No additional aggregate
  failure remained.
- P9-T01 exercised a real `default.ltproj` launch through metadata validation,
  RESOURCES/DB load, driver start, GameState start and title startup before
  controlled termination.
- Accepted combat, Event/tilemap, save/load/restart, fast-forward, debugger and
  profiler matrices are coherent with the trace oracle.
- The final HEAD sanity run adds 219 passing tests across trace/golden
  integrity and representative core/platform owners; compile and runtime
  imports also pass.

There is no unexplained PC logical divergence.

## 9. Android behavior-equivalence evidence

**ANDROID BEHAVIOR EQUIVALENCE: PASS.**

The P9-T02 current-provenance x86_64 WSA run reached real project/resource/DB/
title startup. Synchronization-point evidence passed for title/new chapter,
consecutive Event commands and combat cleanup, pending tilemap preparation and
atomic commit, movement/Wait/FOW, current SAVE, canonical LOAD, pristine
RESTART, phase reconstruction, fast-forward input, debugger idle and profiler
observer behavior.

The device evidence matches the accepted PC transaction shapes. It does not
claim that log/profiler records are a second Trace V1 serializer; exact logical
Trace V1 equality remains the locked host oracle. No Android-only action,
Event, RNG, hook, save-source, phase, partial-world, or worker-publication path
was observed.

Audio/resource logs showed selected title/chapter resources, stream load,
`GlobalMusicState.PLAYING`, cache creation and Android AudioTrack delivery/stop
without missing packaged resources or duplicate fallback. This proves backend
state/order, not acoustic quality.

## 10. Performance comparison

The following is measured evidence from the accepted **instrumented x86_64
WSA debug build**, not a physical Android device and not a release-signing
benchmark. No performance knob changed during measurement.

| Workload | Accepted measurement |
| --- | --- |
| Startup/title steady state | repeated 300-frame windows; median about 16.0 ms, p95 16.7-16.8 ms, maxima 16.9-17.7 ms; one transition window 21.0 ms; DB load 101.24 ms; title stream load p95 3.3-3.6 ms |
| Map idle/movement | repeated 300-frame windows; median/about 16.0 ms, p95 16.6-16.8 ms, maxima 16.9-17.7 ms; map draw about 6-8 ms |
| Combat | representative window about 16.0 ms average, p95 16.6 ms, maximum 37.4 ms; logical combat completed |
| Tilemap/Event transition | worst observed transition frame 154.9 ms; pending work preceded one coherent commit |
| SAVE | snapshot 5.6 ms; worker I/O 8.8 ms |
| LOAD | main-thread restore 230.0 ms; containing frame 286.0 ms |
| RESTART | restore 288.0 ms; containing frame 290.6 ms; later chapter-start Event frame 555.9 ms |
| Fast-forward | about 16.0 ms cadence, p95 about 16.8 ms; three logical updates and one draw/present while held |
| Memory after restart Event | total PSS 307,387 KB; total RSS 407,780 KB; native heap PSS 181,288 KB; no swap |

Raw p99 was not emitted; reported maxima are the available worst meaningful
stalls. There is no historical x86_64 WSA baseline, so these numbers
characterize the release candidate rather than establish an FPS improvement.
The accepted 4,000,000 ns tilemap preparation budget, cache capacities,
renderer policy and audio policy remain unchanged. Correctness traces pass
despite the measured stalls.

## 11. Full test-result matrix

| Subsystem / suite | Accepted result | Most recent evidence | Rerun in P9-T04 |
| --- | --- | --- | --- |
| Trace V1 schema/goldens | S1, S2, S4-S18 exact; S3 N/A | P9-T01/P9-T02 | Integrity sanity: 40 tests, OK; full scenarios reused |
| Full PC discovery | Exact P0 baseline: 311 OK, 8 FAIL, 1 ERROR, same native termination | P9-T01-R1 | No; no later gameplay/test change requiring an expensive duplicate run |
| Real PC project startup | Project/RESOURCES/DB/driver/GameState/title reached | P9-T01-R1 | No; later executable change is Android build tooling only, then a docstring |
| Atomic/canonical load/restart | Accepted transaction/source/compatibility matrix green | P5, P7-T04, P9-T01/P9-T02 | 46 tests, OK |
| Combat lifecycle/order | Map/Simple/Base/Animation and cleanup contracts green | P3, P9-T01/P9-T02 | 22 tests, OK |
| Tilemap/work budget/state machine | Pending barrier, commit/rollback and no Event deadline green | P4/P6/P9-T02 | 31 tests, OK |
| Fast-forward | OFF/ON and input/presentation equivalence green | P7-T01, S16, WSA | 4 tests, OK |
| Debugger | PC/Android shared controller and observer behavior green | P7-T02, S17, WSA | 9 tests, OK |
| Profiler | Disabled/ON equivalence and worker isolation green | P7-T03, S17, WSA | 37 tests, OK |
| Android ABI/build policy | arm64 default plus selected x86_64 strict validation green | P9-T02 | 16 tests, OK |
| Audio/title presentation | Stream/fallback and title-smoke contract green | P6/P8/P9-T02 | 12 tests, OK |
| Project/base integrity | No project-content mutation | P9-T01/P9-T02 | 2 tests, OK |
| Architecture contamination | 217 focused tests in four fresh groups; no contamination | P9-T03 | Reused; no executable change since |

P9-T04 final sanity totals **219 tests, all passing**. Expected mocked failure
logs in restart tests (`disk full`, unavailable pristine source) verify the
failure contract and do not represent test failures. Repeated libpng profile
warnings are unchanged nonfatal resource warnings.

## 12. Android ABI/build status

P9-T02 repaired a confirmed build-policy blocker without touching gameplay.
arm64-v8a remains the normal/default policy. x86_64 is a supported explicit
selection, and editor/config/build/preflight/APK-verifier logic derives strict
expectations from the active requested ABI.

Accepted WSA artifact:

- build ID: `fire-emblem-tales-of-the-golden-knight-android-0.2.0-20260810T040804Z-026a5385`;
- APK size: 232,670,293 bytes;
- SHA-256: `026a53851b747b85cad5b89be1de65f4dfc9166f2114e60f3ccb6237229b8ff5`;
- native directory: exactly `lib/x86_64/` for the WSA artifact;
- all executable native `.so` files, including Python, libcrypto and SDL
  startup libraries, verified as ELF machine 62 / EM_X86_64;
- package version 0.2.0, code 1026410, min API 26, target API 36;
- install and cold launch on Android 13/API 33 x86_64 WSA succeeded; measured
  cold launch was 194 ms;
- the earlier `/system/bin/ifconfig` arm64 libcrypto mismatch and associated
  SIGSEGV did not recur.

The artifact is debug/instrumented and development-signed. No APK or generated
build output is committed. Build/editor/tooling ABI selection does not enter
GameState, Event, combat, save, movement or phase logic.

## 13. Architecture contamination conclusion

**PASS - no architecture contamination found.**

P9-T03 and this cross-phase reconciliation agree:

- no direct Android gameplay fork exists in GameState/action/phase/movement,
  authoritative combat, canonical hydration or save semantics;
- no staged authoritative restore or partial-world publication remains;
- no worker thread mutates gameplay state;
- no generic Event wall-clock/command-count scheduler remains;
- canonical load iterators are exhausted before publication;
- P4 pending builders remain off-world behind the Event-local barrier;
- retained camera/map/debugger/observer guards have independent no-map or
  validation purposes and are not concealed staging workarounds;
- ABI policy is confined to build/editor/tooling.

Earlier reports that document unsafe before-states are chronologically
superseded by their accepted implementation tasks, as listed in section 7.
No accepted evidence requires partial state or Android-only ordering. No
cross-phase contradiction reaches ESC-10.

## 14. Known limitations

### Non-blocking limitations

1. Android runtime/performance evidence is from x86_64 WSA, not physical
   Android hardware; no physical-device thermal, GPU or frame-time distribution
   is available.
2. Audio evidence confirms backend state/order and AudioTrack activity, not
   acoustic quality or audibility.
3. Raw p99 was unavailable; WSA profiler windows provide median/p95/max only,
   and there is no historical x86_64 WSA comparison baseline.
4. The Android artifact is debug/instrumented and development-signed; release
   signing/publishing is a later delivery operation, not evidence of gameplay
   readiness.
5. `mypy` was unavailable in P9-T01 and remains an accepted
   ENVIRONMENT/TOOLING limit; compile/import checks pass.
6. Authoritative full discovery retains the accepted Windows native
   `-1073740791` termination and the exact historical 8 FAIL/1 ERROR baseline.
   Focused suites pass in fresh processes.
7. Shared component/font registries retain known aggregate/import-order test
   debt. The recovery-owned fixture leak was fixed locally; no new failure is
   hidden.
8. `GC-REGION` remains not certified safe for hypothetical future re-entrant
   readers because its clear precedes region publication. Current synchronous
   actions expose no reader in that gap and no stale result was reproduced;
   its lifetime must not be expanded without a dedicated proof.
9. Canonical load/build iterators are safe under repository callers that drain
   them synchronously or use the P4 pending transaction. A future external
   frame-by-frame consumer would require controller review.
10. The legacy malformed/missing tile-animation tint compatibility guard and
    unrelated TODO debt remain documented; neither affects recovery staging.

### Blocking limitations

None found.

## 15. Release blockers

None. There is no unexplained PC/Android logical divergence, invariant breach,
feature loss, architecture contamination, project-data mutation, Trace V1
change after fixture lock, build-policy conflict, or required failed sanity
check.

## 16. Escalation and reconciliation findings

No P9-T04 escalation trigger was encountered. In particular, ESC-10 did not
trigger because apparent differences between early maps/audits and the final
state are ordered before-state/fix relationships, not mutually inconsistent
accepted final contracts. Sol / ultra was neither requested nor used.

The authorized P9-T02 ESC-02 was resolved by the bounded ABI build-policy
repair in `981593e78`; the strict x86_64 artifact and WSA runtime evidence were
accepted. That decision did not expand into runtime gameplay architecture.

## 17. Recommended merge strategy

After FINAL controller/user authorization, preserve the complete recovery
history and merge `recovery/pc-core-semantics` into `master` with a normal,
non-fast-forward merge commit. Do not squash: the ordered controller decisions,
immutable-oracle provenance, compatibility decisions, and Android ABI blocker
resolution are useful release evidence.

Before an authorized merge, record the then-current `master` SHA and consider
an explicit backup tag/branch under separate authorization. Reconfirm the
release-candidate HEAD and clean intended diff, then perform the merge without
rebasing or cherry-picking. After merge, rerun the lightweight sanity set and
the repository's real PC/Android launch gates appropriate to the release
artifact. No merge, tag, branch mutation or push is performed by P9-T04.

## 18. Exact commands used

Read-only identity/history/inventory commands included:

```powershell
git branch --show-current
git rev-parse HEAD
git status --short
git merge-base --is-ancestor 0821182a717de2baaf52a699ee325241ffaddd03 HEAD
git rev-list --count 0821182a717de2baaf52a699ee325241ffaddd03..HEAD
git rev-list --count 0821182a717de2baaf52a699ee325241ffaddd03^..HEAD
git rev-list --parents 0821182a717de2baaf52a699ee325241ffaddd03..HEAD
git log --reverse --format='%h %s' 0821182a717de2baaf52a699ee325241ffaddd03^..HEAD
git show --no-renames --format='%H %s' --name-only <task-commit>
git diff --name-only 0821182a717de2baaf52a699ee325241ffaddd03..HEAD -- default.ltproj
git diff --name-only 6f1da4bcc53f26237b0b2150a128420ecd9aa7cb..HEAD -- app/tests/fixtures/recovery_traces/v1
rg -n "_staged_state_data|commit_staged_state|android_process_budget_seconds|_android_process_yielded" app
rg -n "deadline_ns\s*=\s*4_000_000|TILEMAP_PREPARE_DEADLINE_NS\s*=\s*4_000_000" app/engine/runtime_capabilities app/engine/jobs app/events
```

Final sanity commands used the recorded baseline interpreter:

```powershell
utilities\enemy_event_generator\.python\python.exe -m unittest app.tests.test_recovery_trace app.tests.test_recovery_golden -v
utilities\enemy_event_generator\.python\python.exe -m unittest -q app.tests.test_atomic_restore app.tests.test_canonical_load app.tests.test_restart_contract
utilities\enemy_event_generator\.python\python.exe -m unittest -q app.tests.test_combat_transaction_order app.tests.test_animation_combat_transaction_order
utilities\enemy_event_generator\.python\python.exe -m unittest -q app.tests.test_tilemap_change_job app.tests.test_work_budget_policy app.tests.test_state_machine_lifecycle
utilities\enemy_event_generator\.python\python.exe -m unittest -q app.tests.test_fast_forward_equivalence
utilities\enemy_event_generator\.python\python.exe -m unittest -q app.tests.test_runtime_debugger_parity
utilities\enemy_event_generator\.python\python.exe -m unittest -q app.tests.test_performance_profiler
utilities\enemy_event_generator\.python\python.exe -m unittest -q app.tests.default_ltproj.test_base_project_integrity
utilities\enemy_event_generator\.python\python.exe -m unittest -q app.tests.test_android_build_config
utilities\enemy_event_generator\.python\python.exe -m unittest -q app.tests.test_sound_platform_policy app.tests.test_title_smoke_seed
utilities\enemy_event_generator\.python\python.exe -m compileall -q app
utilities\enemy_event_generator\.python\python.exe -c "import app.engine.driver; import app.engine.game_state; import app.engine.save; print('runtime-import-ok')"
git diff --check
git diff -- recovery/p9_t04_final_release_candidate_review.md
git status --short
```

The mandatory source reports, `AGENTS.md`, `AGENTS.override.md`, full
`plan.md`, and full `recovery/controller_state.md` were read with PowerShell
`Get-Content` before reconciliation.

## 19. Final release-candidate conclusion

**PASS.** The history is coherent, INV-01 through INV-10 are satisfied,
intended later features are preserved, unsafe staging has been removed or
bounded behind an accepted transaction, PC and Android behavior equivalence
are PASS, current Android ABI/build support is validated, measured performance
is reported without overstating WSA evidence, and no release blocker or
ESC-10 conflict remains.

The branch is suitable to present as the final release candidate to the
controller/user. This conclusion recommends, but does not authorize or perform,
a merge to `master`.
