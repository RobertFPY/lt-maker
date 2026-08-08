# P5-T01 save format and compatibility audit

Date: 2026-08-09 (Asia/Bangkok)
Task: P5-T01 audit/test only; no production or format change
Reference: `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`
Audit HEAD: `58f06f6cb75f673ec7355132d931d565ced65f4c`

## 1. Serialized schema / field inventory

`GameState.save()` produces a pickle payload plus `*.pmeta`. There is no
payload schema discriminator; metadata `version` is not read by
`GameState.load_iter`. Compatibility is therefore reader-default based.

| Writer -> reader fields | Restoration / classification |
| --- | --- |
| `units`, `items`, `skills` | Runtime object graph. UID links, item subitems/command item and skill subskill links rebuild after registries. **REFERENCE-COMPATIBLE**. |
| `terrain_status_registry`, `regions`, `level`, `overworlds` | Persisted world identity/progress. Missing DB overworlds rebuild from prefabs. **REFERENCE-COMPATIBLE**. |
| `turncount`, `playtime`, `game_vars`, `level_vars`, `current_party`, `current_mode` | Campaign/turn/difficulty; `_random_seed` initializes RNG. `current_mode` has default fallback. **REFERENCE-COMPATIBLE**. |
| `current_random_state` | Combat RNG restored if present, otherwise seed-derived. **REFERENCE-COMPATIBLE / LEGACY-OPTIONAL**. |
| `state` | Ordered active stack `S` + pending queue `Q`; desktop loads synchronously, Android retains job-local until atomic commit. **REFERENCE-COMPATIBLE**. |
| `action_log`, `supports`, `records`, `speak_styles`, `dialog_log` | History/controllers; support/record/style readers have source-proven default objects. **REFERENCE-COMPATIBLE / LEGACY-OPTIONAL**. |
| `events` | Internal EventManager execution records; section 3. **REFERENCE-COMPATIBLE, INTERNAL-ONLY**. |
| `market_items`, `unlocked_lore`, `already_triggered_events`, `talk_options`, `talk_hidden`, `base_convos`, `roam_info`, `teams`, `parties` | Campaign/base/roam/team data; optional readers use `.get` or DB reconstruction where source shows it. **REFERENCE-COMPATIBLE / LEGACY-OPTIONAL**. |
| `bounds`, `fog_state` | Inputs to board reconstruction only. Board/boundary/occupancy/visible fog/aura grids are rebuilt. **DERIVED/RECONSTRUCTED -- NOT SERIALIZED**. |

Metadata fields are `playtime`, `realtime`, `version`, `title`, `mode`,
`level_nid`, `level_title`, then `kind`, `time`, and optional `disp`.
`SaveSlot.read()` defaults malformed/missing `realtime` to `0` and accepts
optional mode/display name. Units persist non-aura skill references, items,
stats/state/equipment. Nested current fields such as `persistent`, `roam_ai`,
`ai_group`, guard, stat-cap, affinity/notes and equipment defaults are
**LATER-FEATURE-REQUIRED** or **LATER-CORRECTNESS-FIX**, not a new top-level
protocol.

## 2. Reference versus current field / provenance table

Reference `GameState.save()` and current writer have the same top-level key
set above. Current changes transaction timing, not save bytes.

| Surface | Reference | Current / provenance | Classification |
| --- | --- | --- | --- |
| Desktop load | `read -> build_new -> load -> slot/UID` synchronously | Same public synchronous API; `load` drains iterator. P2 `0a6b854e`. | KEEP-SHARED |
| Android read | N/A | Worker reads/unpickles immutable dict only; main thread hydrates atomically. | KEEP-PLATFORM |
| S/Q state | Installed in synchronous load | Android job keeps it local then installs once after full world. | LATER-CORRECTNESS-FIX |
| Aura children | Prior unit data could retain child refs | Writer/reader filter `SourceType.AURA`; board re-derives children. `a961ee878` cluster. | LATER-CORRECTNESS-FIX |
| `chapter_start_snapshot` | Absent | In-memory pre-LevelStart restart material. | LATER-CORRECTNESS-FIX |
| Staged singleton state | Absent | Removed; no long-lived `_staged_state_data`. `8306e1a9` was superseded by P2. | REMOVE-WORKAROUND |

`6bd9da4b` and `8306e1a9` were inspected as staged-load history; `0a6b854e`
replaced frame-visible hydration with an atomic transaction. `a961ee878` is an
independent aura correctness fix. None justify a save-schema change.

## 3. Event serialization support decision

`GameState.save()` writes `EventManager.save()`. It serializes active events;
`Event.save()` stores event NID, unit/position, serializable local args and
processor state. `EventProcessor.save()` keeps script/NID/iterators/pointer and
excludes transient playback. `GameState.load_iter()` restores with
`EventManager.restore(s_dict.get('events'))`.

Decision: retain this as **internal payload support**. It does not re-enable
the removed arbitrary user-facing mid-event save/load feature: S3 remains
**N/A -- REFERENCE-UNSUPPORTED**. P5-T02 must preserve reader/writer support
or seek controller direction, never create a new F-key/mid-event route.

## 4. SAVE_SLOTS versus RESTART_SLOTS caller / semantic map

| Contract | Storage / producer | Consumers | Constraint |
| --- | --- | --- | --- |
| `SAVE_SLOTS` | `<game>-<slot>.p(.meta)` written by `suspend_game`/`save_io`. | Title Load Game, in-chapter load. | Current progress for slot. |
| `RESTART_SLOTS` | `<game>-restart<slot>.p(.meta)`: seeded by `kind='start'`; later saves carry old restart forward; Test Chapter fallback can seed first save. | Title Restart Level, game-over routing, debugger fallback. | Restart point, not progress. |

Title restart normally reads `RESTART_SLOTS[selection]`; overworld restart uses
the matching main slot. Debugger uses in-memory snapshot first, then only a
`kind == 'start'` restart slot. These concepts may share pickle helpers but
must not be merged.

## 5. Normal / start / overworld save-load matrix

| Kind / entry | Required current semantics |
| --- | --- |
| Normal desktop | `save.load_game` installs saved S/Q synchronously; next update sees complete world. |
| Normal Android title/in-chapter | worker immutable read -> full main-thread hydrate -> one S/Q/destination install; no loader residue. |
| `start` Load Game | Restore payload then `start_level(_next_level_nid)` plus `start_level_asset_loading`. |
| Restart Level | Read restart slot and rebuild chapter; preserve title prefix when applicable. |
| `overworld` | Full restore then exactly one `overworld` destination. |

## 6. chapter_start_snapshot / pristine restart lifecycle

`level_setup_iter` creates party/board/regions/fog, registers and arrives
units, starts initiative, then deep-copies `self.save()[0]` in
`_capture_chapter_start_snapshot`, before LevelStart mutation. Optional
`chapter_start_state` captures destination S/Q without publishing it early.
Debugger restart uses this snapshot before restart-slot fallback.

Normal new game seeds restart files from start save. Test Chapter bypasses
new-game/current-slot setup, so its first save can seed a non-pristine restart;
that documented dev fallback remains distinct from normal gameplay. Game-over,
title and debugger must preserve this precedence.

## 7. Aura / derived-state serialization and reconstruction map

`UnitObject.save()` excludes `SourceType.AURA`; `restore()` also discards aura
children from legacy payloads. After level + board + boundary + fog regions +
unit arrivals exist, load repopulates source auras/registers boundary auras and
`pull_auras` derives children from live parents. This prevents duplicate or
orphaned children. Board occupancy, boundaries, visible FOW and aura grids are
derived; only bounds/visited fog inputs persist. P4 pending tilemap/board
objects are neither written nor read as save truth. S12 and trace/aura tests
are the proof surface.

## 8. Old / current compatibility matrix

| Case | Result/evidence |
| --- | --- |
| Reference-era payload -> current | Same top-level writer fields; mandatory fields remain readers, optional defaults are source-proven. Field-level compatible. |
| Current -> current | Paired writer/reader and atomic restore tests. Supported. |
| Older missing optional fields | `teams`, `overworlds`, mode, RNG, supports/records/styles and named campaign fields use source-proven fallback/reconstruction. Supported only where `.get`/default exists. |
| Legacy unknown fields present | Reader consumes named keys only; extras are unread. LEGACY/OPTIONAL. |
| Normal/start/overworld and slot consumers | Distinct metadata routing and files; sections 4/5. Supported but must stay distinct. |
| Snapshot/restart | Snapshot is in-memory; restart slot is persistent carry-forward. Supported. |

No archived PC-reference binary `.p` fixture is committed. This is therefore
field/schema compatibility evidence, not a claim of byte-for-byte pickle
compatibility for arbitrary external saves.

## 9. Android load orchestration dependency map

`SaveLoadJob._read_worker` owns file read/unpickle. `advance()` does
`build_new` and drains hydration on the main thread in one logical update;
`take_state_data()` consumes S/Q only after it completes. Title and in-chapter
load-job states own opaque presentation/input suspension and route
normal/start/restart/overworld only after atomic installation. Resource/audio/
profiler work remains presentation/diagnostic policy.

P4 `TilemapChangeJob` and its Event-local barrier are not serialized, loader
state, pending GameState, or a second authoritative saved world.

## 10. P5-T02 canonical-load constraints

- Preserve desktop synchronous API and Android worker-only immutable I/O.
- Keep S/Q transaction-local until world/RNG/board/aura/event restoration is
  complete, then install destination exactly once.
- Preserve mandatory fields and explicit legacy defaults; no unapproved schema
  migration or serializing P4 pending boards.
- Preserve internal Event serialization without re-enabling S3.

## 11. P5-T03 restart constraints

- Keep numbered SAVE and RESTART files separate and slot-keyed.
- Preserve `kind='start'` seed/carry-forward and Test Chapter fallback.
- Preserve capture after chapter setup and before LevelStart; ordinary
  mid-chapter saves are not normal pristine restart material.
- Preserve game-over/title/debugger precedence.

## 12. Unresolved compatibility questions / escalation evidence

No ESC-01/02/04/06/09 condition occurred. The only limitation is no archived
reference binary save file; if P5-T02 needs a field without writer, reader
default, or concrete legacy fixture, it must stop for controller direction
rather than inventing migration semantics.

## Validation evidence

Existing proof targets are `test_atomic_restore` (Android destinations, S/Q,
snapshot), `test_runtime_debugger` (snapshot/restart fallback),
`test_recovery_trace` (aura trace model), and immutable S1/S2/S4/S12/S18
comparisons. P5-T01 adds no redundant tests: it changes no behavior.
