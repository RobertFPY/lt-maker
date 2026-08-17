# Implementation Plan: Sudden Panic and Ploy status migration

## Execution contract

- Executor: `gpt-5.6-terra`, reasoning effort `high`.
- This plan is implementation authorization only after the user explicitly asks to implement it.
- Do not edit `plan.md`, `recovery/controller_state.md`, or recovery artifacts.
- Do not create a new custom skill component. Use existing data components and event commands only.
- Preserve unrelated dirty changes in `skills.json`, `metadata.json`, and `custom_skill_components.py`.
- Do not commit unless the user asks separately.
- Canonical spelling is `Wily_Fighter`; do not rename it to `Willy_Fighter`. Old `willy_fighter_*` level variables will disappear with the legacy restore events.

## Goal

Implement Sudden Panic and migrate Panic Ploy, Stall Ploy, and Wily Fighter away from permanent `change_stats` mutations and shared level variables. Temporary effects must live in removable skill objects whose `stat_change` component is populated by `modify_skill_component`.

The migration must preserve each family's current trigger and tier conditions, except for the explicitly requested Sudden Panic redesign:

- Sudden Panic: start of combat, checks only the combat target's HP and nearby-foe condition, then lasts through the next later action involving that target. The application combat never counts as that next action.
- Panic Ploy: combat condition remains unchanged, converts positive bonuses for that combat only.
- Stall Ploy: combat condition and after-combat trigger remain unchanged, MOV becomes 1 until the existing one-turn/endstep expiry.
- Wily Fighter: HP/mode conditions and extra-attack subskill remain unchanged; only the bonus-neutralization half is migrated.
- Dull Close and Dull Ranged must be included in the Wily event migration because they share `Global WilyFighterSkill` and its legacy restore event.

## Confirmed problems in the current checkout

1. Panic Ploy and Wily Fighter mutate `unit.stats` with `change_stats`, then restore from unit-keyed level variables. This is vulnerable to stale flags, overwritten snapshots, duplicate triggers, and cross-effect ordering.
2. Panic Ploy converts by `-2 * bonus`; Wily Fighter neutralizes by `-1 * bonus`, but both use the same generic `_change_*_bonus` flags.
3. Stall Ploy permanently mutates base MOV and restores it later. Its guard uses `not T1 or not T2 or not T3`, which is true unless the target owns all three tiers.
4. `Stall_Ploy_Effect` has no stat component of its own; it exists only to trigger a restore event.
5. Sudden Panic T1-T3 are still `do_nothing`.
6. `get_enemies_within_distance` is player-team-specific and must not be used for Sudden Panic's nearby-foe test. The combat target comes directly from `{unit2}`; only its nearby partner needs a relationship-aware scan.
7. `event_on_wait` alone is insufficient: it mistakes the application combat's finishing wait for the next action when the affected target initiated. Sudden therefore needs a `combat_end` arming stage plus `event_on_wait` expiry.

## Architecture decisions

### 1. Effects are reversible skill instances

Create or migrate these effect skills:

| Effect skill | Runtime component | Lifetime |
| --- | --- | --- |
| `Sudden_Panic_Effect` | zero-initialized `stat_change` plus an internal `priority` lifecycle state | `combat_end -> Global SuddenPanicAdvance`, `event_on_wait -> Global SuddenPanicExpire`, plus `lost_on_end_chapter` |
| `Panic_Ploy_Effect` | zero-initialized `stat_change` for the seven combat stats | `lost_on_end_combat2`, plus end-chapter fallback supplied by that component |
| `Wily_Fighter_Neutralize_Effect` | zero-initialized `stat_change` for the seven combat stats | `lost_on_end_combat2` |
| `Stall_Ploy_Effect` | zero-initialized `stat_change` for MOV | keep `lost_on_endstep` and `lost_on_end_chapter` |

Removing one of these skills automatically removes its stat contribution. No restore event is needed.

Do not add the `negative` marker in this migration. The current implementations bypass status immunity/reflection; adding `negative` would silently change gameplay and can cause `ImmuneStatus` to remove the effect before `modify_skill_component` runs. Status immunity/reflection is a separate design decision.

### 2. Transformation formulas

For each `stat` in `('STR', 'MAG', 'SKL', 'SPD', 'LCK', 'DEF', 'RES')`:

- Conversion: `delta = -2 * max(0, target.stat_bonus(stat))`.
- Neutralization: `delta = -max(0, target.stat_bonus(stat))`.
- Stall: `MOV delta = -max(0, target.get_stat('MOV') - 1)`.

Examples:

- `+6` bonus plus conversion delta `-12` produces `-6`.
- `+6` bonus plus neutralization delta `-6` produces `0`.
- MOV `6` plus Stall delta `-5` produces MOV `1`.
- Zero and negative stat bonuses are not made more negative.

The event must add a zero-valued effect first, verify the target owns the effect, then replace the entire `stat_change` list with one `modify_skill_component` command. Do not emit seven `change_stats` blocks.

### 3. Explicit precedence and deduplication

The result must not depend on event order:

1. Conversion beats neutralization.
2. If `Sudden_Panic_Effect` or `Panic_Ploy_Effect` is active, Wily/Dull must not add neutralization.
3. Sudden Panic is the longest-lived conversion and has highest precedence. If `Panic_Ploy_Effect` or `Wily_Fighter_Neutralize_Effect` was added earlier in the same combat, Sudden removes it before measuring bonuses and applying `Sudden_Panic_Effect`.
4. Panic Ploy skips when Sudden is already active. Otherwise, it removes Wily/Dull neutralization before measuring bonuses and applying combat conversion.
5. Wily/Dull skips whenever either conversion effect is active.
6. A second instance of the same effect is skipped. Tiers and multiple owners do not stack the same transform.
7. The Sudden status remains after the application combat. It expires after the next later combat involving that target, or after that target completes its next non-combat action, whichever happens first.
8. Stall is independent from stat-bonus transforms but must not stack multiple MOV penalties.

### 4. Sudden Panic start-of-combat semantics

Sudden Panic applies only to the current combat target, not every qualifying foe on the map:

- Combat target: `{unit2}`/`target`, which must exist, be alive, on-map, and satisfy `skill_system.check_enemy(user, target)`.
- Nearby partner: a different active unit that is also an enemy of the user and an ally of the combat target.
- The target and nearby partner must have non-`None` positions.
- Distance is Manhattan distance through `utils.calculate_distance`.
- The nearby partner does not need to satisfy the HP check; it only qualifies the combat target as clustered.
- HP comparison is strict: `foe.current_hp < user.current_hp - gap`.
- The check runs whether the skill owner attacks or defends; no `mode == 'attack'` restriction is added.
- The combat that applies Sudden never consumes its "next action" lifetime, regardless of which side initiated.
- After the application combat, a `combat_end` event arms the status. If the affected target initiated that combat, its immediately following `on_wait` only advances the status to the armed state instead of removing it.
- Once armed, the status is removed after the next later combat involving that target, or when the target completes its next non-combat action.

Tier settings remain:

| Tier | HP gap | Cluster radius |
| --- | ---: | ---: |
| T1 | 5 | 3 |
| T2 | 3 | 5 |
| T3 | 1 | 7 |

Each Sudden tier receives its own `combat_condition` containing its HP gap and radius, then calls one shared `event_before_combat: Global SuddenPanicApply`. The shared event transforms only `{unit2}`. Do not create level variables for gap or radius and do not scan the map for additional effect recipients.

## Dependency graph

```text
Behavior contract and tests
        |
        +--> Temporary effect skill schemas
        |        |
        |        +--> Sudden Panic combat condition/apply/expire events
        |        +--> Panic Ploy combat conversion event
        |        +--> Wily/Dull combat neutralization event
        |        +--> Stall Ploy MOV event
        |                 |
        +-----------------+--> reference cleanup and integration tests
```

## Task 1: Add failing contract tests

**Description:** Create focused tests before changing game data. Tests should parse project `skills.json` and `events.json`, validate wiring, and exercise the numeric/stat-lifetime contracts using real `SkillObject`, `StatChange`, `ModifySkillComponent`, and skill removal where practical.

**Acceptance criteria:**

- [ ] Tests describe conversion, neutralization, MOV-to-1, removal restoration, precedence, and non-stacking.
- [ ] Tests assert that migrated events contain no `change_stats`, `level_var`, or legacy restore references.
- [ ] Tests assert that Wily's extra-attack subskill and every existing combat condition remain unchanged.

**Verification:**

- [ ] New tests fail for the expected missing status/event wiring before implementation.
- [ ] Record the focused command and failure summary; do not weaken assertions to make the baseline pass.

**Dependencies:** None.

**Files likely touched:**

- `app/tests/test_ploy_status_effects.py`

**Estimated scope:** S.

## Task 2: Implement the shared reversible effect schemas

**Description:** Add the three new effect skills and convert `Stall_Ploy_Effect` into an actual stat-bearing status. Use explicit zero-valued stat dictionaries so `modify_skill_component` can safely replace them.

**Acceptance criteria:**

- [ ] All four effect NIDs exist exactly once.
- [ ] Combat effects use `lost_on_end_combat2`; Sudden uses combat-end arming plus `event_on_wait`; Stall keeps its current endstep lifetime.
- [ ] No effect modifies base stats, stores level variables, or adds a new Python component.

**Verification:**

- [ ] Load and parse `skills.json` successfully.
- [ ] Focused schema tests pass.

**Dependencies:** Task 1.

**Files likely touched:**

- `Fire Emblem Tales of The Golden Knight.ltproj/game_data/skills.json`
- `app/tests/test_ploy_status_effects.py`

**Estimated scope:** S.

## Task 3: Implement start-of-combat Sudden Panic end to end

**Description:** Replace `do_nothing` on all three tiers with a tier-specific `combat_condition` and shared `event_before_combat: Global SuddenPanicApply`. Add combat-end arming and wait expiry events so the application combat is ignored and the next later action involving the target consumes the status.

**Application order:**

1. Let the tier-specific `combat_condition` enforce target existence, strict HP threshold, and the nearby-foe radius check.
2. In the event, defensively validate `{unit2}` and the enemy relationship again.
3. Skip if `{unit2}` already carries `Sudden_Panic_Effect`.
4. Remove `Panic_Ploy_Effect` and `Wily_Fighter_Neutralize_Effect` if either was applied earlier in this combat.
5. Optionally skip if the restored target has no positive bonus in any of the seven stats.
6. Give the zero-valued Sudden effect to `{unit2}` with no banner.
7. Confirm `has_skill(target, 'Sudden_Panic_Effect')`.
8. Replace its `stat_change` with the conversion list.
9. At the end of the application combat, arm the status without removing it. If the affected target was the initiator, ignore the `on_wait` that finishes that same action.
10. Remove the armed status after the next later combat involving the target or after the target completes a non-combat action.

**Acceptance criteria:**

- [ ] T1/T2/T3 use gap/radius 5/3, 3/5, and 1/7.
- [ ] Only the combat target can receive the effect; other clustered foes are qualifiers, not additional recipients.
- [ ] Enemy-owned and player-owned users validate the combat target correctly.
- [ ] The nearby unit cannot be the combat target itself and need not pass the HP check.
- [ ] No upkeep event or map-wide target loop remains on Sudden Panic.
- [ ] The effect survives the application combat whether the target attacked or defended.
- [ ] The next later combat involving the target, or the target's next non-combat action, removes the effect after that action finishes.

**Verification:**

- [ ] Boundary tests cover equality, one point below threshold, radius edge, radius+1, isolated target, off-map partner, and dead partner.
- [ ] Lifecycle tests cover target-as-attacker, target-as-defender, a later combat targeting the foe, and a later wait/action; base stats remain unchanged.

**Dependencies:** Task 2.

**Files likely touched:**

- `Fire Emblem Tales of The Golden Knight.ltproj/game_data/skills.json`
- `Fire Emblem Tales of The Golden Knight.ltproj/game_data/events.json`
- `app/tests/test_ploy_status_effects.py`

**Estimated scope:** M.

## Checkpoint A: Sudden Panic slice

- [ ] JSON loads cleanly.
- [ ] Focused tests pass.
- [ ] No `custom_skill_components.py` edit exists for this feature.
- [ ] Diff contains no unrelated skill reserialization or broad JSON reorder.

## Task 4: Migrate Panic Ploy to a combat status

**Description:** Rewrite `Global PanicPloySkill` to apply `Panic_Ploy_Effect` and populate its stat-change list. Remove the restore component from T1-T3; the combat effect removes itself through `lost_on_end_combat2`.

**Required event behavior:**

1. Validate `{unit2}` exists and is an enemy.
2. If Sudden or Panic conversion already exists, stop; Sudden must never be replaced by the shorter combat-only effect.
3. If Wily/Dull neutralization exists, remove it first.
4. Measure the now-restored positive bonuses.
5. Add and populate `Panic_Ploy_Effect` only when at least one bonus is positive.

**Acceptance criteria:**

- [ ] Existing T1/T2/T3 combat conditions, priorities, slot/class markers, and `self_nihil` lists are unchanged.
- [ ] During combat, `+B` becomes `-B`; after combat, the exact pre-combat result returns automatically.
- [ ] `Global PanicPloySkill2` has no references and is deleted only after a full `rg` reference check.

**Verification:**

- [ ] Test positive, zero, negative, and mixed stat bonuses.
- [ ] Test Panic with pre-existing Sudden and with Wily executing both before and after Panic.

**Dependencies:** Tasks 2-3.

**Files likely touched:**

- `Fire Emblem Tales of The Golden Knight.ltproj/game_data/skills.json`
- `Fire Emblem Tales of The Golden Knight.ltproj/game_data/events.json`
- `app/tests/test_ploy_status_effects.py`

**Estimated scope:** M.

## Task 5: Migrate Wily Fighter and shared Dull consumers

**Description:** Rewrite `Global WilyFighterSkill` to add `Wily_Fighter_Neutralize_Effect` and populate `-max(0, bonus)` values. Remove the after-combat restore reference from `Wily_Fighter_Effect_1` and all Dull Close/Ranged skills that share this event.

**Acceptance criteria:**

- [ ] Wily T1-T3 HP thresholds, defense-mode condition, `desperation`, and `dynamic_attacks = 1` remain unchanged.
- [ ] Dull Close/Ranged retain their current conditions; only legacy restore wiring is removed.
- [ ] Conversion precedence is deterministic: Panic/Sudden wins regardless of event order.
- [ ] `Global WilyFighterSkill2` has no references and is deleted only after a full reference check.

**Verification:**

- [ ] Test `+B -> 0`, zero unchanged, negative unchanged.
- [ ] Test duplicate Wily/Dull triggers do not stack.
- [ ] Test Wily plus Panic in both application orders.

**Dependencies:** Task 4 defines precedence.

**Files likely touched:**

- `Fire Emblem Tales of The Golden Knight.ltproj/game_data/skills.json`
- `Fire Emblem Tales of The Golden Knight.ltproj/game_data/events.json`
- `app/tests/test_ploy_status_effects.py`

**Estimated scope:** M.

**Do not silently fix:** `Dull_Ranged_T3` currently has a full-HP condition despite a description without one. Report this mismatch separately; it is outside this requested migration unless the user authorizes the semantic correction.

## Checkpoint B: Combat transforms

- [ ] Panic conversion and Wily/Dull neutralization pass numeric tests.
- [ ] Both combat effects disappear after normal combat, counter combat, death, and aborted/no-target paths tested by the available harness.
- [ ] No base stat changes or restore variables remain.
- [ ] Wily extra attacks have no regression.

## Task 6: Migrate Stall Ploy to MOV stat contribution

**Description:** Rewrite `Global StallPloySkill` so it gives `Stall_Ploy_Effect` itself, then sets that instance's MOV contribution. Remove `give_status_after_combat` from T1-T3 to avoid ordering ambiguity and duplicate adds.

**Required event behavior:**

1. Validate the target exists and is an enemy.
2. Skip if `Stall_Ploy_Effect` already exists.
3. Give the zero-valued effect with no banner.
4. Confirm the effect exists.
5. Set MOV delta to `-max(0, target.get_stat('MOV') - 1)`.

**Acceptance criteria:**

- [ ] The broken T1/T2/T3 OR guard is removed; no undocumented immunity is introduced.
- [ ] MOV values above 1 become exactly 1; MOV 1 or lower is not reduced further.
- [ ] Removing/expiring the effect restores MOV without an event or level variable.
- [ ] `Global StallPloySkill2` and `event_on_remove` are removed after reference checks.

**Verification:**

- [ ] Test MOV 1, 2, 6, duplicate application, and expiry.
- [ ] Test all three existing Spd conditions remain byte-for-byte unchanged.

**Dependencies:** Task 2.

**Files likely touched:**

- `Fire Emblem Tales of The Golden Knight.ltproj/game_data/skills.json`
- `Fire Emblem Tales of The Golden Knight.ltproj/game_data/events.json`
- `app/tests/test_ploy_status_effects.py`

**Estimated scope:** M.

## Task 7: Cleanup, integrity checks, and focused review

**Description:** Remove only proven-dead restore events/variables, validate JSON and references, run focused tests, and inspect the final diff for accidental data churn.

**Acceptance criteria:**

- [ ] No reference remains to `Global PanicPloySkill2`, `Global WilyFighterSkill2`, or `Global StallPloySkill2` before those events are deleted.
- [ ] No `panic_ploy_*`, `willy_fighter_*`, `_change_*_bonus`, or `stall_ploy_mov_*` variable logic remains in the migrated events.
- [ ] No migrated event contains `change_stats`.
- [ ] Only intended skill/event records and the focused test file changed.

**Verification commands:**

```powershell
E:\FE\lt-maker\utilities\enemy_event_generator\.python\python.exe -m unittest app.tests.test_ploy_status_effects
E:\FE\lt-maker\utilities\enemy_event_generator\.python\python.exe -m unittest app.tests.events.test_event_commands app.tests.test_add_remove_skills
rg -n "Global (PanicPloySkill2|WilyFighterSkill2|StallPloySkill2)|panic_ploy_|willy_fighter_|stall_ploy_mov_|_change_.*_bonus" "Fire Emblem Tales of The Golden Knight.ltproj"
git diff --check
git diff --stat
git diff -- "Fire Emblem Tales of The Golden Knight.ltproj/game_data/skills.json" "Fire Emblem Tales of The Golden Knight.ltproj/game_data/events.json" "app/tests/test_ploy_status_effects.py"
```

**Dependencies:** Tasks 3-6.

**Files likely touched:**

- `Fire Emblem Tales of The Golden Knight.ltproj/game_data/skills.json`
- `Fire Emblem Tales of The Golden Knight.ltproj/game_data/events.json`
- `app/tests/test_ploy_status_effects.py`

**Estimated scope:** S.

## Final acceptance matrix

| Scenario | Expected result |
| --- | --- |
| Combat starts; Sudden T3 user HP 20, target HP 19 | no trigger because `19 < 19` is false |
| Combat starts; T3 target HP 18, partner at distance 7 | only the combat target receives Sudden |
| Same combat target but partner at distance 8 | no trigger |
| Start of turn without combat | Sudden does nothing |
| Bonus STR +6 under Sudden/Panic | effective STR bonus -6 |
| Bonus STR +6 under Wily/Dull | effective STR bonus 0 |
| Existing STR penalty -4 | remains -4; no extra inversion |
| Panic and Wily in either order | conversion wins; final bonus -B |
| Panic/Wily event runs before Sudden in same combat | Sudden removes the shorter effect and conversion wins |
| Sudden runs before Panic/Wily | later event skips; no double transform |
| Sudden target is the defender | application combat is ignored; effect survives until the next later action involving that target |
| Sudden target is the attacker | application combat and its finishing wait are ignored; effect survives until the next later action involving that target |
| A later combat targets or is initiated by the affected foe | effect remains through that combat, then expires |
| Affected foe next performs a non-combat action | effect expires when that action completes |
| Panic/Wily combat ends | combat status removed |
| Stall target MOV 6 | MOV becomes 1 |
| Stall expires | original MOV contribution returns |
| Duplicate source/tier | no stacking |

## Known limitation retained by the event-only design

The stat list is a snapshot at application time. If a bonus source is added or removed while the status is active, the transform does not dynamically recalculate. This matches the requested event-only approach and is still safer than permanent `change_stats`. Exact continuous recalculation would require a carefully designed reusable component and is explicitly out of scope.

## Final handoff report required from Terra High

Report:

1. Root causes fixed.
2. Exact files and NIDs changed.
3. Focused test commands and results.
4. Static checks and remaining runtime/manual validation.
5. Any semantic mismatch discovered but intentionally not changed.
6. Diff summary and confirmation that no unrelated dirty edits were overwritten.
