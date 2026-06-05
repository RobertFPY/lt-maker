from __future__ import annotations

from app.data.database.components import ComponentType
from app.data.database.database import DB
from app.data.database.item_components import ItemComponent, ItemTags
from app.engine import (action, banner, combat_calcs, engine, equations,
                        image_mods, item_funcs, item_system, skill_system,
                        target_system, unit_funcs)
from app.engine.game_state import game
from app.engine.objects.unit import UnitObjectfrom app.utilities import utils, static_random
from app.data.database.difficulty_modes import RNGOption
from app.engine.combat import playback as pb
from app.engine.movement import movement_funcs
from app.engine.source_type import SourceType
import logging
def ai_status_priority(unit, target, item, move, status_nid) -> float:
    if target and status_nid not in [skill.nid for skill in target.skills]:
        accuracy_term = utils.clamp(combat_calcs.compute_hit(unit, target, item, target.get_weapon(), "attack", (0, 0))/100., 0, 1)
        num_attacks = combat_calcs.outspeed(unit, target, item, target.get_weapon(), "attack", (0, 0))
        accuracy_term *= num_attacks
        # Tries to maximize distance from target
        distance_term = 0.01 * utils.calculate_distance(move, target.position)
        if skill_system.check_enemy(unit, target):
            return 0.5 * accuracy_term + distance_term
        else:
            return -0.5 * accuracy_term
    return 0
class DoNothing(ItemComponent):
    nid = 'do_nothing'
    desc = 'does nothing'
    tag = ItemTags.CUSTOM

    expose = ComponentType.Int
    value = 1

class StealFullInventoryWIP(ItemComponent):
    nid = 'steal_full_inventory'
    desc = "Steal any unequipped item from target on hit"
    tag = ItemTags.CUSTOM
    author = "TheD4rkblade"

    _did_steal = False

    def init(self, item):
        item.data['target_item'] = None

    def target_restrict(self, unit, item, def_pos, splash) -> bool:
        # Unit has item that can be stolen
        attack = equations.parser.steal_atk(unit)
        defender = game.board.get_unit(def_pos)
        defense = equations.parser.steal_def(defender)
        if attack >= defense:
            for def_item in defender.items:
                if self.item_restrict(unit, item, defender, def_item):
                    return True
        return False

    def valid_targets(self, unit, item):
        positions = set()
        for other in game.units:
            if other.position and skill_system.check_enemy(unit, other):
                for def_item in other.items:
                    if self.item_restrict(unit, item, other, def_item):
                        positions.add(other.position)
                        break
        return positions

    def targets_items(self, unit, item) -> bool:
        return True
 
    def item_restrict(self, unit, item, defender, def_item) -> bool:
        if item_system.unstealable(defender, def_item):
            return False
        if def_item is defender.get_weapon():
            return False
        if item_funcs.inventory_full(unit, def_item):
            return True if unit.team == 'player' else False
        return True

    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        target_item = item.data.get('target_item')
        if target_item:
            actions.append(action.RemoveItem(target, target_item))
            actions.append(action.DropItem(unit, target_item))
            if unit.team != 'player':
                actions.append(action.MakeItemDroppable(unit, target_item))
            actions.append(action.UpdateRecords('steal', (unit.nid, target.nid, target_item.nid)))
            self._did_steal = True

    def end_combat(self, playback, unit, item, target, item2, mode):
        if self._did_steal:
            if item_funcs.inventory_full(unit, item):
                game.memory['item_discard_current_unit'] = unit
                game.state.change('item_discard')
            target_item = item.data.get('target_item')
            game.alerts.append(banner.StoleItem(unit, target_item))
            game.state.change('alert')
        item.data['target_item'] = None
        self._did_steal = False

    def ai_priority(self, unit, item, target, move):
        if target:
            steal_term = 0.075
            enemy_positions = utils.average_pos({other.position for other in game.units if other.position and skill_system.check_enemy(unit, other)})
            distance_term = utils.calculate_distance(move, enemy_positions)
            return steal_term + 0.01 * distance_term
        return 0
 
class LupinSteal(ItemComponent):
    nid = 'lupin_steal'
    desc = "Steal all item from target on hit"
    tag = ItemTags.SPECIAL

    _did_steal = False

    def init(self, item):
        item.data['target_item'] = None

    def target_restrict(self, unit, item, def_pos, splash) -> bool:
        # Unit has item that can be stolen
        attack = equations.parser.steal_atk(unit)
        defender = game.board.get_unit(def_pos)
        defense = equations.parser.steal_def(defender)
        if attack >= defense:
            for def_item in defender.items:
                if self.item_restrict(unit, item, defender, def_item):
                    return True
        return False

    def valid_targets(self, unit, item):
        positions = set()
        for other in game.units:
            if other.position and skill_system.check_enemy(unit, other):
                for def_item in other.items:
                    if self.item_restrict(unit, item, other, def_item):
                        positions.add(other.position)
                        break
        return positions

    def targets_items(self, unit, item) -> bool:
        return True

    def item_restrict(self, unit, item, defender, def_item) -> bool:
        if item_system.unstealable(defender, def_item):
            return False
        if item_funcs.inventory_full(unit, def_item):
            return False
        return True

    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        target_item = item.data.get('target_item')
        if target_item:
            actions.append(action.RemoveItem(target, target_item))
            actions.append(action.DropItem(unit, target_item))
            if unit.team != 'player':
                actions.append(action.MakeItemDroppable(unit, target_item))
            actions.append(action.UpdateRecords('steal', (unit.nid, target.nid, target_item.nid)))
            self._did_steal = True

    def end_combat(self, playback, unit, item, target, item2, mode):
        if self._did_steal:
            target_item = item.data.get('target_item')
            game.alerts.append(banner.StoleItem(unit, target_item))
            game.state.change('alert')
        item.data['target_item'] = None
        self._did_steal = False

    def ai_priority(self, unit, item, target, move):
        if target:
            steal_term = 0.075
            enemy_positions = utils.average_pos({other.position for other in game.units if other.position and skill_system.check_enemy(unit, other)})
            distance_term = utils.calculate_distance(move, enemy_positions)
            return steal_term + 0.01 * distance_term
        return 0
class MagicWeaponRank(ItemComponent):
    nid = 'magic_weapon_rank'
    desc = "Item is a magic weapon, and has a wrank"
    requires = ['weapon_type']
    tag = ItemTags.CUSTOM

    expose = ComponentType.WeaponRank

    def weapon_rank(self, unit, item):
        return self.value

    def available(self, unit, item):
        required_wexp = DB.weapon_ranks.get(self.value).requirement
        weapon_type = item_system.weapon_type(unit, item)
        optional_tag = 'Magician'
        if weapon_type:
            return (unit.wexp.get(weapon_type) >= required_wexp or optional_tag in unit.tags)
        else:  # If no weapon type, then always available
            return True

class StealCon(ItemComponent):
    nid = 'steal_con'
    desc = "Steal any unequipped item from target on hit, only if user's CON exceeds item's weight"
    tag = ItemTags.CUSTOM

    _did_steal = False

    def init(self, item):
        item.data['target_item'] = None

    def target_restrict(self, unit, item, def_pos, splash) -> bool:
        # Unit has item that can be stolen
        attack = equations.parser.steal_atk(unit)
        defender = game.board.get_unit(def_pos)
        defense = equations.parser.steal_def(defender)
        if attack >= defense:
            for def_item in defender.items:
                if self.item_restrict(unit, item, defender, def_item):
                    return True
        return False

    def ai_targets(self, unit, item):
        positions = set()
        for other in game.units:
            if other.position and skill_system.check_enemy(unit, other):
                for def_item in other.items:
                    if self.item_restrict(unit, item, other, def_item):
                        positions.add(other.position)
                        break
        return positions

    def targets_items(self, unit, item) -> bool:
        return True

    def item_restrict(self, unit, item, defender, def_item) -> bool:
        if item_system.unstealable(defender, def_item):
            return False
        if item_funcs.inventory_full(unit, def_item):
            return False
        if def_item is defender.get_weapon():
            return False
        if def_item.components.get('weight') and unit.get_stat('CON') < def_item.components.get('weight').value:
            return False
        return True

    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        target_item = item.data.get('target_item')
        if target_item:
            actions.append(action.RemoveItem(target, target_item))
            actions.append(action.DropItem(unit, target_item))
            if unit.team != 'player':
                actions.append(action.MakeItemDroppable(unit, target_item))
            actions.append(action.UpdateRecords('steal', (unit.nid, target.nid, target_item.nid)))
            self._did_steal = True

    def end_combat(self, playback, unit, item, target, item2, mode):
        if self._did_steal:
            target_item = item.data.get('target_item')
            game.alerts.append(banner.StoleItem(unit, target_item))
            game.state.change('alert')
        item.data['target_item'] = None
        self._did_steal = False

    def ai_priority(self, unit, item, target, move):
        if target:
            steal_term = 0.075
            enemy_positions = utils.average_pos({other.position for other in game.units if other.position and skill_system.check_enemy(unit, other)})
            distance_term = utils.calculate_distance(move, enemy_positions)
            return steal_term + 0.01 * distance_term
        return 0

class EvalMaximumRange(ItemComponent):
    nid = 'eval_max_range'
    desc = "Set the maximum_range of the item solved using evaluate"
    tag = ItemTags.CUSTOM

    expose = ComponentType.String
    value = 0

    def maximum_range(self, unit, item) -> int:
        from app.engine import evaluate
        try:
            return int(evaluate.evaluate(self.value, unit, local_args={'item': item}))
        except Exception as e:
            logging.error("Couldn't evaluate %s conditional (%s)", self.value, e)
        return 0

class DamageAny(ItemComponent):
    nid = 'damage_any'
    desc = "Item does damage on hit. Can target allies."
    tag = ItemTags.CUSTOM

    expose = ComponentType.Int
    value = 0

    def damage(self, unit, item):
        return self.value

    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        playback_nids = [brush.nid for brush in playback]
        if 'attacker_partner_phase' in playback_nids or 'defender_partner_phase' in playback_nids:
            damage = combat_calcs.compute_assist_damage(unit, target, item, target.get_weapon(), mode, attack_info)
        else:
            damage = combat_calcs.compute_damage(unit, target, item, target.get_weapon(), mode, attack_info)

        # Reduce damage if in Grandmaster Mode
        if game.mode.rng_choice == RNGOption.GRANDMASTER:
            hit = utils.clamp(combat_calcs.compute_hit(unit, target, item, target.get_weapon(), mode, attack_info), 0, 100)
            damage = int(damage * float(hit) / 100)

        true_damage = min(damage, target.get_hp())
        actions.append(action.ChangeHP(target, -damage))

        # For animation
        playback.append(pb.DamageHit(unit, item, target, damage, true_damage))
        if damage == 0:
            playback.append(pb.HitSound('No Damage'))
            playback.append(pb.HitAnim('MapNoDamage', target))

    def on_glancing_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        playback_nids = [brush.nid for brush in playback]
        if 'attacker_partner_phase' in playback_nids or 'defender_partner_phase' in playback_nids:
            damage = combat_calcs.compute_assist_damage(unit, target, item, target.get_weapon(), mode, attack_info)
        else:
            damage = combat_calcs.compute_damage(unit, target, item, target.get_weapon(), mode, attack_info)

        # Reduce damage if in Grandmaster Mode
        if game.mode.rng_choice == RNGOption.GRANDMASTER:
            hit = utils.clamp(combat_calcs.compute_hit(unit, target, item, target.get_weapon(), mode, attack_info), 0, 100)
            damage = int(damage * float(hit) / 100)

        damage //= 2  # Because glancing hit

        true_damage = min(damage, target.get_hp())
        actions.append(action.ChangeHP(target, -damage))

        # For animation
        playback.append(pb.DamageHit(unit, item, target, damage, true_damage))
        if damage == 0:
            playback.append(pb.HitAnim('MapNoDamage', target))
        else:
            playback.append(pb.HitAnim('MapGlancingHit', target))

    def on_crit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        playback_nids = [brush.nid for brush in playback]
        if 'attacker_partner_phase' in playback_nids or 'defender_partner_phase' in playback_nids:
            damage = combat_calcs.compute_assist_damage(unit, target, item, target.get_weapon(), mode, attack_info, crit=True)
        else:
            damage = combat_calcs.compute_damage(unit, target, item, target.get_weapon(), mode, attack_info, crit=True)
 
        # Reduce damage if in Grandmaster Mode (although crit doesn't make much sense with Grandmaster mode)
        if game.mode.rng_choice == RNGOption.GRANDMASTER:
            hit = utils.clamp(combat_calcs.compute_hit(unit, target, item, target.get_weapon(), mode, attack_info), 0, 100)
            damage = int(damage * float(hit) / 100)

        true_damage = min(damage, target.get_hp())
        actions.append(action.ChangeHP(target, -damage))

        playback.append(pb.DamageCrit(unit, item, target, damage, true_damage))
        if damage == 0:
            playback.append(pb.HitSound('No Damage'))
            playback.append(pb.HitAnim('MapNoDamage', target))

class ShoveOnEndCombatInitiate(ItemComponent):
    nid = 'shove_on_end_combat_initiate'
    desc = "Item shoves target at the end of combat, only on initiation"
    tag = ItemTags.CUSTOM

    expose = ComponentType.Int
    value = 1

    def _check_shove(self, unit_to_move, anchor_pos, magnitude):
        offset_x = utils.clamp(unit_to_move.position[0] - anchor_pos[0], -1, 1)
        offset_y = utils.clamp(unit_to_move.position[1] - anchor_pos[1], -1, 1)
        new_position = (unit_to_move.position[0] + offset_x * magnitude,
                        unit_to_move.position[1] + offset_y * magnitude)

        mcost = movement_funcs.get_mcost(unit_to_move, new_position)
        #If we could pass through it if we had movement, allow the action to occur
        if mcost != 99:
            mcost = 0
        if game.board.check_bounds(new_position) and \
                not game.board.get_unit(new_position) and \
                mcost <= equations.parser.movement(unit_to_move):
            return new_position
        return False
    
    def end_combat(self, playback, unit, item, target, item2, mode):
        if target and not skill_system.ignore_forced_movement(target) and mode and mode == 'attack':
            new_position = self._check_shove(target, unit.position, self.value)
            if new_position:
                action.do(action.ForcedMovement(target, new_position))
class ShoveOnEndCombatInitiatePlus(ItemComponent):
    nid = 'shove_on_end_combat_initiate_plus'
    desc = "Item shoves target at the end of combat, only on initiation, if target couldn't move back due to terrain limit, target suffered x damage."
    tag = ItemTags.CUSTOM
    expose = ComponentType.NewMultipleOptions

    options = {
        'space': ComponentType.Int,
        'damage': ComponentType.Int,
    }

    def __init__(self, value=None):
        self.value = {
            'space': 1,
            'damage': 10,
        }
        if value:
            self.value.update(value)

    def _check_shove(self, unit_to_move, anchor_pos, magnitude):
        offset_x = utils.clamp(unit_to_move.position[0] - anchor_pos[0], -1, 1)
        offset_y = utils.clamp(unit_to_move.position[1] - anchor_pos[1], -1, 1)
        new_position = (unit_to_move.position[0] + offset_x * magnitude,
                        unit_to_move.position[1] + offset_y * magnitude)

        mcost = movement_funcs.get_mcost(unit_to_move, new_position)
        #If we could pass through it if we had movement, allow the action to occur
        if mcost != 99:
            mcost = 0
        if game.board.check_bounds(new_position) and \
                not game.board.get_unit(new_position) and \
                mcost <= equations.parser.movement(unit_to_move):
            return new_position
        return False
    
    def end_combat(self, playback, unit, item, target, item2, mode):
        if target and not skill_system.ignore_forced_movement(target) and mode and mode == 'attack':
            new_position = self._check_shove(target, unit.position, self.value['space'])
            if new_position:
                action.do(action.ForcedMovement(target, new_position))            else:                if target and skill_system.check_enemy(unit, target) and not target.get_hp() <= 0:
                    end_health = target.get_hp() - self.value['damage']
                    action.do(action.SetHP(target, max(1, end_health)))
class ShoveFlexibleOnEndCombatInitiate(ItemComponent):
    nid = 'shove_flexible_on_end_combat_initiate'
    desc = "Item shoves target at the end of combat, only on initiation. Target will stop if they hit a wall."
    tag = ItemTags.CUSTOM

    expose = ComponentType.Int
    value = 1

    def _check_shove(self, unit_to_move, anchor_pos, magnitude):
        curr_magnitude = 0
        ret_position = None
        while(abs(curr_magnitude) < abs(magnitude)):
            if magnitude < 0:
                curr_magnitude -= 1
            else:
                curr_magnitude += 1
            offset_x = utils.clamp(unit_to_move.position[0] - anchor_pos[0], -1, 1)
            offset_y = utils.clamp(unit_to_move.position[1] - anchor_pos[1], -1, 1)
            new_position = (unit_to_move.position[0] + offset_x * curr_magnitude,
                            unit_to_move.position[1] + offset_y * curr_magnitude)

            mcost = movement_funcs.get_mcost(unit_to_move, new_position)
            if game.board.check_bounds(new_position) and \
                    not game.board.get_unit(new_position) and \
                    mcost <= equations.parser.movement(unit_to_move):
                ret_position = new_position
            else:
                magnitude = 0
        if not ret_position:
            return False
        return ret_position
    
    def end_combat(self, playback, unit, item, target, item2, mode):
        if target and not skill_system.ignore_forced_movement(target) and mode and mode == 'attack':
            new_position = self._check_shove(target, unit.position, self.value)
            if new_position:
                action.do(action.ForcedMovement(target, new_position))

class EvalHPCost(ItemComponent):
    nid = 'eval_hp_cost'
    desc = "Item subtracts the specified amount of HP upon use. If the subtraction would kill the unit the item becomes unusable."
    tag = ItemTags.CUSTOM

    expose = ComponentType.String
    value = ""

    _did_something = False

    def _check_value(self, unit, item) -> int:
        from app.engine import evaluate
        try:
            return int(evaluate.evaluate(self.value, unit, local_args={'item': item}))
        except:
            print("Couldn't evaluate %s conditional" % self.value)
        return 0
    
    def available(self, unit, item) -> bool:
        return unit.get_hp() > self._check_value(unit, item)

    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        self._did_something = True

    def on_miss(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        self._did_something = True

    def end_combat(self, playback, unit, item, target, item2, mode):
        value = self._check_value(unit, item)
        if self._did_something:
            action.do(action.ChangeHP(unit, -value))
        self._did_something = False

    def reverse_use(self, unit, item):
        value = self._check_value(unit, item)
        action.do(action.ChangeHP(unit, value))

class ShoveFlexibleStops(ItemComponent):
    nid = 'shove_flex_stops'
    desc = "Item shoves target on hit up to X spaces, can be shortened by obstacles"
    tag = ItemTags.CUSTOM

    expose = ComponentType.Int
    value = 1

    def _check_shove(self, unit_to_move, anchor_pos, magnitude):
        curr_magnitude = 0
        ret_position = None
        while(abs(curr_magnitude) < abs(magnitude)):
            if magnitude < 0:
                curr_magnitude -= 1
            else:
                curr_magnitude += 1
            offset_x = utils.clamp(unit_to_move.position[0] - anchor_pos[0], -1, 1)
            offset_y = utils.clamp(unit_to_move.position[1] - anchor_pos[1], -1, 1)
            new_position = (unit_to_move.position[0] + offset_x * curr_magnitude,
                            unit_to_move.position[1] + offset_y * curr_magnitude)

            mcost = movement_funcs.get_mcost(unit_to_move, new_position)
            if game.board.check_bounds(new_position) and \
                    not game.board.get_unit(new_position) and \
                    mcost <= equations.parser.movement(unit_to_move):
                ret_position = new_position
            else:
                magnitude = 0
        if not ret_position:
            return False
        return ret_position

    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        if target and not skill_system.ignore_forced_movement(target):
            new_position = self._check_shove(target, unit.position, self.value)
            if new_position:
                actions.append(action.ForcedMovement(target, new_position))
                playback.append(pb.ShoveHit(unit, item, target))
                
class PermanentStatChangeEarly(ItemComponent):
    nid = 'permanent_stat_change_early'
    desc = "Using this item permanently changes the stats of the target in the specified ways. The target and user are often the same unit (think of normal FE stat boosters)."
    tag = ItemTags.CUSTOM

    expose = (ComponentType.Dict, ComponentType.Stat)

    def _target_restrict(self, defender):
        klass = DB.classes.get(defender.klass)
        for stat, inc in self.value:
            if inc <= 0 or defender.stats[stat] < klass.max_stats.get(stat, 30):
                return True
        return False

    def target_restrict(self, unit, item, def_pos, splash) -> bool:
        # Ignore's splash
        defender = game.board.get_unit(def_pos)
        if not defender:
            return True
        return self._target_restrict(defender)

    def simple_target_restrict(self, unit, item):
        return self._target_restrict(unit)

    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        stat_changes = {k: v for (k, v) in self.value}
        klass = DB.classes.get(target.klass)
        # clamp stat changes
        stat_changes = {k: utils.clamp(v, -target.stats[k], klass.max_stats.get(k, 30) - target.stats[k]) for k, v in stat_changes.items()}
        action.do(action.ApplyStatChanges(target, stat_changes))
        if any(v != 0 for v in stat_changes.values()):
            game.memory['stat_changes'] = stat_changes
            game.exp_instance.append((target, 0, None, 'stat_booster'))
            game.state.change('exp')

class StatusesAfterCombatOnHit(ItemComponent):
    nid = 'statuses_after_combat_on_hit'
    desc = "If the target is hit they gain the specified statuses at the end of combat. Prevents changes being applied mid-combat."
    tag = ItemTags.CUSTOM
    author = 'BigMood, Lord_Tweed'

    expose = (ComponentType.List, ComponentType.Skill)  # Nid

    _did_hit = set()

    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        self._did_hit.add(target)

    def end_combat(self, playback, unit, item, target, item2, mode):
        for target in self._did_hit:
            for status_nid in self.value:
                act = action.AddSkill(target, status_nid, unit)
                action.do(act)
        self._did_hit.clear()

    def ai_priority(self, unit, item, target, move):
        # Do I add a new status to the target
        return ai_status_priority(unit, target, item, move, self.value)

class EvalEnemyBlastAOE(ItemComponent):
    nid = 'eval_smartblast_aoe'
    desc = "Grants EVAL Enemy AoE range."
    tag = ItemTags.CUSTOM

    expose = ComponentType.String

    def _get_power(self, unit) -> int:
        from app.engine import evaluate
        try:
            base_power = int(evaluate.evaluate(self.value, unit))
        except Exception as e:
            logging.error("Couldn't evaluate %s conditional (%s)", self.value, e)
            base_power = 0
        empowered_splash = skill_system.empower_splash(unit)
        return base_power + 1 + empowered_splash

    def splash(self, unit, item, position) -> tuple:
        ranges = set(range(self._get_power(unit)))
        splash = game.target_system.find_manhattan_spheres(ranges, position[0], position[1])
        splash = {pos for pos in splash if game.board.check_bounds(pos)}
        from app.engine import item_system, skill_system
        if item_system.is_spell(unit, item):
            # spell blast
            splash = [game.board.get_unit(s) for s in splash]
            splash = [s.position for s in splash if s and skill_system.check_enemy(unit, s)]
            return None, splash
        else:
            # regular blast
            splash = [game.board.get_unit(s) for s in splash if s != position]
            splash = [s.position for s in splash if s and skill_system.check_enemy(unit, s)]
            return position if game.board.get_unit(position) else None, splash

    def splash_positions(self, unit, item, position) -> set:
        from app.engine import skill_system
        ranges = set(range(self._get_power(unit)))
        splash = game.target_system.find_manhattan_spheres(ranges, position[0], position[1])
        splash = {pos for pos in splash if game.tilemap.check_bounds(pos)}
        # Doesn't highlight allies positions
        splash = {pos for pos in splash if not game.board.get_unit(pos) or skill_system.check_enemy(unit, game.board.get_unit(pos))}
        return splash

class SelfUnloadUnit(ItemComponent):
    nid = 'self_unload_unit'
    desc = "Places the unit stored through the store unit component on the specified target (most often a tile). Uses the user's movement to check valid tiles."
    tag = ItemTags.CUSTOM

    def target_restrict(self, unit, item, def_pos, splash) -> bool:
        if def_pos and not game.board.get_unit(def_pos) and movement_funcs.check_weakly_traversable(unit, def_pos):
            return True
        return False

    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        if self.item.data.get('stored_unit'):
            rescuee = game.get_unit(self.item.data['stored_unit'])
            self.item.data['stored_unit'] = None
            if rescuee:
                actions.append(action.Warp(rescuee, target_pos))
                # Move camera over position
                game.cursor.set_pos(target_pos)
                
class BlitzStrike(ItemComponent):
    nid = 'galeforce_on_crit'
    desc = "Item causes wielder to move again after crit. Subtracts a charge from Blitz Strike."
    tag = ItemTags.CUSTOM

    def on_crit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        unit._fields['blitz_strike'] = True
        
    def end_combat(self, playback, unit, item, target, item2, mode):
        if 'blitz_strike' in unit._fields and unit._fields['blitz_strike']:
            action.do(action.AddSkill(unit, 'Galeforce_Status'))
            from app.engine import evaluate
            action.do(action.TriggerCharge(unit, evaluate.evaluate("get_skill(unit, 'Blitz_Strike')", unit1=unit)))
            unit._fields['blitz_strike'] = False
                
class RestrictRankMagic(ItemComponent):
    nid = 'restrict_rank_magic'
    desc = "Item cannot be used unless at or below the given rank if magic"
    tag = ItemTags.CUSTOM

    expose = ComponentType.WeaponRank

    def available(self, unit, item):
        return not item_system.weapon_type(unit, item) in ['Anima', 'Dark', 'Staff', 'Light'] or DB.weapon_ranks.get(self.value).requirement >= DB.weapon_ranks.get(item_system.weapon_rank(unit, item)).requirement
        
class WeaponTypeExempt(ItemComponent):
    nid = 'weapon_type_exempt'
    desc = "Categorizes a weapon type but does not require the wielder to be able to use that weapon type"
    tag = ItemTags.CUSTOM

    expose = ComponentType.WeaponType

    def weapon_type(self, unit, item):
        return self.value

    def available(self, unit, item) -> bool:
        return True
class WeaponRankExempt(ItemComponent):
    nid = 'weapon_rank_exempt'
    desc = "Categorizes a weapon rank but does not require the wielder to be able to use that weapon rank"
    tag = ItemTags.CUSTOM

    expose = ComponentType.WeaponRank

    def weapon_rank(self, unit, item):
        return self.value

    def available(self, unit, item) -> bool:
        return True

# Tag that lets a unit cast spells using their Staff rank instead of the
# spell's own weapon type (used by Mari).
STAFF_CASTER_TAG = 'StaffCaster'

class StaffCastWeaponType(ItemComponent):
    nid = 'staffcast_weapon_type'
    desc = ("The type of weapon to wield. Behaves like the normal weapon type, "
            "but units tagged '%s' may also wield it using their Staff rank." % STAFF_CASTER_TAG)
    tag = ItemTags.CUSTOM

    expose = ComponentType.WeaponType

    def weapon_type(self, unit, item):
        return self.value

    def available(self, unit, item) -> bool:
        # Normal weapon-type requirement (matches the base weapon_type component).
        klass = DB.classes.get(unit.klass)
        wexp_gain = klass.wexp_gain.get(self.value)
        if wexp_gain:
            klass_usable = self.value in unit_funcs.usable_wtypes(unit)
            if unit.wexp[self.value] > 0 and klass_usable:
                return True
        # Staff-caster fallback: tagged units may wield it via their Staff rank.
        if STAFF_CASTER_TAG in unit.tags and unit.wexp.get('Staff', 0) > 0:
            return True
        return False

class StaffCastWeaponRank(ItemComponent):
    nid = 'staffcast_weapon_rank'
    desc = ("Weapon rank requirement. Units tagged '%s' qualify when their "
            "Staff rank is at least the spell's rank." % STAFF_CASTER_TAG)
    requires = ['weapon_type']
    tag = ItemTags.CUSTOM

    expose = ComponentType.WeaponRank

    def weapon_rank(self, unit, item):
        return self.value

    def available(self, unit, item):
        required_wexp = DB.weapon_ranks.get(self.value).requirement
        weapon_type = item_system.weapon_type(unit, item)
        # Normal path: enough wexp in the spell's own weapon type.
        if weapon_type and unit.wexp.get(weapon_type, 0) >= required_wexp:
            return True
        # Staff-caster fallback: Staff rank >= the spell's required rank.
        if STAFF_CASTER_TAG in unit.tags and unit.wexp.get('Staff', 0) >= required_wexp:
            return True
        return False

class PivotOnEndCombatInitiate(ItemComponent):
    nid = 'pivot_on_end_combat_initiate'
    desc = "Item pivots over target at the end of combat, only on initiation"
    tag = ItemTags.CUSTOM

    expose = ComponentType.Int
    value = 1

    def _check_pivot(self, unit_to_move, anchor_pos, magnitude):
        offset_x = utils.clamp(unit_to_move.position[0] - anchor_pos[0], -1, 1)
        offset_y = utils.clamp(unit_to_move.position[1] - anchor_pos[1], -1, 1)
        new_position = (anchor_pos[0] + offset_x * -magnitude,
                        anchor_pos[1] + offset_y * -magnitude)

        mcost = movement_funcs.get_mcost(unit_to_move, new_position)
        #If we could pass through it if we had movement, allow the action to occur
        if mcost != 99:
            mcost = 0
        if game.board.check_bounds(new_position) and \
                not game.board.get_unit(new_position) and \
                mcost <= equations.parser.movement(unit_to_move):
            return new_position
        return False
    
    def end_combat(self, playback, unit, item, target, item2, mode):
        if target and not skill_system.ignore_forced_movement(unit) and mode and mode == 'attack':
            new_position = self._check_pivot(unit, target.position, self.value)
            if new_position:
                action.do(action.Teleport(unit, new_position))
                
class Locked2(ItemComponent):
    nid = 'locked_2'
    desc = 'Item cannot be taken or dropped from a units inventory. However, the trade command can be used to rearrange its position, and event commands can remove the item.'
    tag = ItemTags.CUSTOM

    def locked(self, unit, item) -> bool:
        return True

    def unstealable(self, unit, item) -> bool:
        return True


class Backdash(ItemComponent):
    nid = 'backdash'
    desc = 'Unit shoves *itself* backwards from the target point.'
    tag = ItemTags.CUSTOM
    author = 'mag'

    expose = ComponentType.Int
    value = 1

    def _check_dash(self, target, user, magnitude):
        tpos = target.position
        upos = user.position
        offset = utils.tmult(utils.tclamp(utils.tuple_sub(upos, tpos), (-1, -1), (1, 1)), magnitude)
        npos = utils.tuple_add(upos, offset)

        mcost_user = game.movement.get_mcost(user, npos)
        if game.board.check_bounds(npos) and not game.board.get_unit(npos) and \
                mcost_user <= equations.parser.movement(user):
            return npos
        return None

    def target_restrict(self, unit, item, def_pos, splash) -> bool:
        target = game.board.get_unit(def_pos)
        if not target:
            return False
        new_position = self._check_dash(target, unit, self.value)
        if new_position:
            return True
        return False

    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        if target and not skill_system.ignore_forced_movement(unit):
            new_position = self._check_dash(target, unit, self.value)
            if new_position:
                actions.append(action.ForcedMovement(unit, new_position))
                playback.append(pb.ShoveHit(unit, item, target))
class BackdashInitiate(ItemComponent):
    nid = 'backdash_initiate'
    desc = 'Unit shoves *itself* backwards from the target point.'
    tag = ItemTags.CUSTOM
    author = 'mag'

    expose = ComponentType.Int
    value = 1

    def _check_dash(self, target, user, magnitude):
        tpos = target.position
        upos = user.position
        offset = utils.tmult(utils.tclamp(utils.tuple_sub(upos, tpos), (-1, -1), (1, 1)), magnitude)
        npos = utils.tuple_add(upos, offset)

        mcost_user = game.movement.get_mcost(user, npos)
        if game.board.check_bounds(npos) and not game.board.get_unit(npos) and \
                mcost_user <= equations.parser.movement(user):
            return npos
        return None

    def target_restrict(self, unit, item, def_pos, splash) -> bool:
        target = game.board.get_unit(def_pos)
        if not target:
            return False
        new_position = self._check_dash(target, unit, self.value)
        if new_position:
            return True
        return False

    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        if target and not skill_system.ignore_forced_movement(unit) and mode and mode == 'attack':
            new_position = self._check_dash(target, unit, self.value)
            if new_position:
                actions.append(action.ForcedMovement(unit, new_position))
                playback.append(pb.ShoveHit(unit, item, target))
class DrawBackOnEndCombatInitiate(ItemComponent):
    nid = 'draw_back_on_end_combat_initiate'
    desc = "Item moves both user and target back at the end of combat, only on initiation"
    tag = ItemTags.CUSTOM

    expose = ComponentType.Int
    value = 1

    def _check_draw_back(self, target, user, magnitude):
        offset_x = utils.clamp(target.position[0] - user.position[0], -1, 1)
        offset_y = utils.clamp(target.position[1] - user.position[1], -1, 1)
        new_position_user = (user.position[0] - offset_x * magnitude,
                             user.position[1] - offset_y * magnitude)
        new_position_target = (target.position[0] - offset_x * magnitude,
                               target.position[1] - offset_y * magnitude)

        mcost_user = movement_funcs.get_mcost(user, new_position_user)
        mcost_target = movement_funcs.get_mcost(target, new_position_target)
        #If we could pass through it if we had movement, allow the action to occur
        if mcost_user != 99:
            mcost_user = 0
        if mcost_target != 99:
            mcost_target = 0
        if game.board.check_bounds(new_position_user) and \
                not game.board.get_unit(new_position_user) and \
                mcost_user <= equations.parser.movement(user) and mcost_target <= equations.parser.movement(target):
            return new_position_user, new_position_target
        return None, None
    
    def end_combat(self, playback, unit, item, target, item2, mode):
        if target and not skill_system.ignore_forced_movement(unit) and not skill_system.ignore_forced_movement(target) and mode and mode == 'attack':
            new_position_user, new_position_target = self._check_draw_back(target, unit, self.value)
            if new_position_user:
                action.do(action.Teleport(unit, new_position_user))
            if new_position_target and not game.board.get_unit(new_position_target):
                action.do(action.Teleport(target, new_position_target))

class EvalDamage(ItemComponent):
    nid = 'eval_damage'
    desc = "Item does damage on hit. Damage is evaluated."
    tag = ItemTags.WEAPON

    expose = ComponentType.String
    value = 0

    def damage(self, unit, item):
        from app.engine import evaluate
        try:
            return int(evaluate.evaluate(self.value, unit, local_args={'item': item}))
        except Exception as e:
            logging.error("EVAL DAMAGE: Couldn't evaluate %s conditional (%s)", self.value, e)
            return 0

    def target_restrict(self, unit, item, def_pos, splash) -> bool:
        # Restricts target based on whether any unit is an enemy
        defender = game.board.get_unit(def_pos)
        if defender and skill_system.check_enemy(unit, defender):
            return True
        for s_pos in splash:
            s = game.board.get_unit(s_pos)
            if s and skill_system.check_enemy(unit, s):
                return True
        return False

    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        playback_nids = [brush.nid for brush in playback]
        if 'attacker_partner_phase' in playback_nids or 'defender_partner_phase' in playback_nids:
            damage = combat_calcs.compute_assist_damage(unit, target, item, target.get_weapon(), mode, attack_info)
        else:
            damage = combat_calcs.compute_damage(unit, target, item, target.get_weapon(), mode, attack_info)

        # Reduce damage if in Grandmaster Mode
        if game.mode.rng_choice == RNGOption.GRANDMASTER:
            hit = utils.clamp(combat_calcs.compute_hit(unit, target, item, target.get_weapon(), mode, attack_info), 0, 100)
            damage = int(damage * float(hit) / 100)

        true_damage = min(damage, target.get_hp())
        actions.append(action.ChangeHP(target, -damage))

        # For animation
        playback.append(pb.DamageHit(unit, item, target, damage, true_damage))
        if damage == 0:
            playback.append(pb.HitSound('No Damage'))
            playback.append(pb.HitAnim('MapNoDamage', target))

    def on_glancing_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        playback_nids = [brush.nid for brush in playback]
        if 'attacker_partner_phase' in playback_nids or 'defender_partner_phase' in playback_nids:
            damage = combat_calcs.compute_assist_damage(unit, target, item, target.get_weapon(), mode, attack_info)
        else:
            damage = combat_calcs.compute_damage(unit, target, item, target.get_weapon(), mode, attack_info)

        # Reduce damage if in Grandmaster Mode
        if game.mode.rng_choice == RNGOption.GRANDMASTER:
            hit = utils.clamp(combat_calcs.compute_hit(unit, target, item, target.get_weapon(), mode, attack_info), 0, 100)
            damage = int(damage * float(hit) / 100)

        damage //= 2  # Because glancing hit

        true_damage = min(damage, target.get_hp())
        actions.append(action.ChangeHP(target, -damage))

        # For animation
        playback.append(pb.DamageHit(unit, item, target, damage, true_damage))
        if damage == 0:
            playback.append(pb.HitAnim('MapNoDamage', target))
        else:
            playback.append(pb.HitAnim('MapGlancingHit', target))

    def on_crit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        playback_nids = [brush.nid for brush in playback]
        if 'attacker_partner_phase' in playback_nids or 'defender_partner_phase' in playback_nids:
            damage = combat_calcs.compute_assist_damage(unit, target, item, target.get_weapon(), mode, attack_info, crit=True)
        else:
            damage = combat_calcs.compute_damage(unit, target, item, target.get_weapon(), mode, attack_info, crit=True)

        # Reduce damage if in Grandmaster Mode (although crit doesn't make much sense with Grandmaster mode)
        if game.mode.rng_choice == RNGOption.GRANDMASTER:
            hit = utils.clamp(combat_calcs.compute_hit(unit, target, item, target.get_weapon(), mode, attack_info), 0, 100)
            damage = int(damage * float(hit) / 100)

        true_damage = min(damage, target.get_hp())
        actions.append(action.ChangeHP(target, -damage))

        playback.append(pb.DamageCrit(unit, item, target, damage, true_damage))
        if damage == 0:
            playback.append(pb.HitSound('No Damage'))
            playback.append(pb.HitAnim('MapNoDamage', target))

def ai_status_priority_buff(unit, target, item, move, status_nid) -> float:
    if target and status_nid not in [skill.nid for skill in target.skills]:
        accuracy_term = utils.clamp(combat_calcs.compute_hit(unit, target, item, target.get_weapon(), "attack", (0, 0))/100., 0, 1)
        num_attacks = combat_calcs.outspeed(unit, target, item, target.get_weapon(), "attack", (0, 0))
        accuracy_term *= num_attacks
        # Tries to maximize distance from target
        distance_term = 0.01 * utils.calculate_distance(move, target.position)
        if skill_system.check_enemy(unit, target):
            return -0.5 * accuracy_term + distance_term
        else:
            return 0.5 * accuracy_term
    return 0

class BuffAlly(ItemComponent):
    nid = 'buff_ally'
    desc = "Target gains the specified status on hit. Only use this for staves that target allies."
    tag = ItemTags.CUSTOM

    expose = ComponentType.Skill  # Nid

    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        act = action.AddSkill(target, self.value, unit)
        actions.append(act)
        playback.append(pb.StatusHit(unit, item, target, self.value))

    def ai_priority(self, unit, item, target, move):
        # Do I add a new status to the target
        return ai_status_priority_buff(unit, target, item, move, self.value)
        
class EventBeforeCombat(ItemComponent):
    nid = 'event_before_combat'
    desc = "The selected event plays at the beginning of combat."
    tag = ItemTags.SPECIAL

    expose = ComponentType.Event

    def start_combat(self, playback, unit, item, target, item2, mode):
        event_prefab = DB.events.get_from_nid(self.value)
        if event_prefab:
            local_args = {'item': item, 'item2': item2, 'mode': mode}
            game.events.trigger_specific_event(event_prefab.nid, unit, target, unit.position, local_args)
            
class EvalMagic(ItemComponent):
    nid = 'eval_magic'
    desc = 'Makes Item use magic damage formula under certain conditions'
    tag = ItemTags.WEAPON
    
    expose = ComponentType.String

    def damage_formula(self, unit, item):
        if self.active(unit, item):
            return 'MAGIC_DAMAGE'
        return 'DAMAGE'

    def resist_formula(self, unit, item):
        if self.active(unit, item):
            return 'MAGIC_DEFENSE'
        return 'DEFENSE'
        
    def active(self, unit, item) -> bool:
        from app.engine import evaluate
        try:
            return bool(evaluate.evaluate(self.value, unit, local_args={'item': item}))
        except:
            logging.error("EvalMagic: Couldn't evaluate %s conditional" % self.value)
        return False

class EvalDragon(ItemComponent):
    nid = 'eval_dragon'
    desc = 'Makes Item magical and use target lower defense under certain conditions'
    tag = ItemTags.WEAPON
    
    expose = ComponentType.String
    
    def damage_formula(self, unit, item):
        if self.active(unit, item):
            return 'MAGIC_DAMAGE'
        return 'DAMAGE'

    def resist_formula(self, unit, item):
        if self.active(unit, item):
            return 'WORSE_DEFENSE'
        return 'DEFENSE'
        
    def active(self, unit, item) -> bool:
        from app.engine import evaluate
        try:
            return bool(evaluate.evaluate(self.value, unit, local_args={'item': item}))
        except:
            logging.error("EvalMagic: Couldn't evaluate %s conditional" % self.value)
        return False
        
class EvalDragonMagic(ItemComponent):
    nid = 'eval_dragon_magic'
    desc = 'Makes Item magical and use target lower defense under certain conditions, still magical if conditions not met'
    tag = ItemTags.WEAPON
    
    expose = ComponentType.String
    
    def damage_formula(self, unit, item):
        return 'MAGIC_DAMAGE'

    def resist_formula(self, unit, item):
        if self.active(unit, item):
            return 'WORSE_DEFENSE'
        return 'MAGIC_DEFENSE'
        
    def active(self, unit, item) -> bool:
        from app.engine import evaluate
        try:
            return bool(evaluate.evaluate(self.value, unit, local_args={'item': item}))
        except:
            logging.error("EvalMagic: Couldn't evaluate %s conditional" % self.value)
        return False

class RemoveOnEndChapter(ItemComponent):
    nid = 'remove_on_end_chapter'
    desc = "This item is lost on chapter end."
    tag = ItemTags.USES
    
    def on_end_chapter(self, unit, item):
        if item:
            if item in game.party.convoy:
                action.do(action.RemoveItemFromConvoy(item))
            elif unit and item in unit.items:
                action.do(action.RemoveItem(unit, item))
            else:
                for other_unit in game.get_units_in_party():
                    if item in other_unit.items:
                        action.do(action.RemoveItem(other_unit, item))

class StartCooldown(ItemComponent):
    nid = 'start_cooldown'
    desc = "Item will be on cooldown at the beginning of the chapter. Place underneath Cooldown component."
    tag = ItemTags.USES

    def init(self, item):
        item.data['cooldown'] = item.data['starting_cooldown']

    def on_end_chapter(self, unit, item):
        item.data['cooldown'] = item.data['starting_cooldown']
    
    def on_upkeep(self, actions, playback, unit, item):
        if game.turncount == 1:
            # Prevents cooldown ticking on turn 1
            action.do(action.SetObjData(item, 'cooldown', item.data['starting_cooldown']))

class PivotAlwaysOnEndCombatInitiate(ItemComponent):
    nid = 'pivot_always_on_end_combat_initiate'
    desc = "Item pivots over target at the end of combat, only on initiation. Will always work unless terrain is completely impassable."
    tag = ItemTags.CUSTOM

    expose = ComponentType.Int
    value = 1

    def _check_pivot(self, unit_to_move, anchor_pos, magnitude):
        offset_x = utils.clamp(unit_to_move.position[0] - anchor_pos[0], -1, 1)
        offset_y = utils.clamp(unit_to_move.position[1] - anchor_pos[1], -1, 1)
        new_position = (anchor_pos[0] + offset_x * -magnitude,
                        anchor_pos[1] + offset_y * -magnitude)

        mcost = movement_funcs.get_mcost(unit_to_move, new_position)
        #If we could pass through it if we had movement, allow the action to occur
        if mcost != 99:
            mcost = -999
        if game.board.check_bounds(new_position) and \
                not game.board.get_unit(new_position) and \
                mcost <= equations.parser.movement(unit_to_move):
            return new_position
        return False
    
    def end_combat(self, playback, unit, item, target, item2, mode):
        if target and not skill_system.ignore_forced_movement(unit) and mode and mode == 'attack':
            new_position = self._check_pivot(unit, target.position, self.value)
            if new_position:
                action.do(action.Teleport(unit, new_position))

class EvalWeight(ItemComponent):
    nid = 'eval_weight'
    desc = "Lowers attack speed. At first, subtracted from the CONSTITUTION equation. If negative, subtracts from overall attack speed. Value is evaluated."
    tag = ItemTags.WEAPON

    expose = ComponentType.String
    value = 0

    def modify_attack_speed(self, unit, item):
        from app.engine import evaluate
        try:
            new_value = int(evaluate.evaluate(self.value, unit, local_args={'item': item}))
        except Exception as e:
            logging.error("EVAL WEIGHT: Couldn't evaluate %s conditional (%s)", self.value, e)
            new_value = 0

        return -1 * max(0, new_value - equations.parser.constitution(unit))

    def modify_defense_speed(self, unit, item):
        from app.engine import evaluate
        try:
            new_value = int(evaluate.evaluate(self.value, unit, local_args={'item': item}))
        except Exception as e:
            logging.error("EVAL WEIGHT: Couldn't evaluate %s conditional (%s)", self.value, e)
            new_value = 0

        return -1 * max(0, new_value - equations.parser.constitution(unit))

    def modify_avoid(self, unit, item):
        from app.engine import evaluate
        try:
            new_value = int(evaluate.evaluate(self.value, unit, local_args={'item': item}))
        except Exception as e:
            logging.error("EVAL WEIGHT: Couldn't evaluate %s conditional (%s)", self.value, e)
            new_value = 0

        return -2 * max(0, new_value - equations.parser.constitution(unit))

class Unavailable(ItemComponent):
    nid = 'unavailable'
    desc = 'Item is not available and cannot be used under any circumstance.'
    tag = ItemTags.USES

    expose = ComponentType.String

    def available(self, unit, item) -> bool:
        return False

class RestoreAfterCombat(ItemComponent):
    nid = 'restore_after_combat'
    desc = "Item removes all negative statuses from target after combat. No targeting restriction."
    tag = ItemTags.UTILITY

    def _can_be_restored(self, status):
        return status.negative

    def end_combat(self, playback, unit, item, target, item2, mode):
        for skill in target.all_skills[:]:
            if self._can_be_restored(skill):
                actions.append(action.RemoveSkill(target, skill))
                playback.append(pb.RestoreHit(unit, item, target))

class StackCost(ItemComponent):
    nid = 'stack_cost'
    desc = "Item requires and uses a stack of the specified skill. Stack is lost at start of combat."
    tag = ItemTags.USES

    expose = ComponentType.Skill  # Nid
    
    def available(self, unit, item) -> bool:
        return self.value in [s.nid for s in unit.skills]

    def start_combat(self, playback, unit, item, target, item2, mode):
        action.do(action.AddSkill(unit, self.value, unit))
    
    def reverse_use(self, unit, item):
        action.do(action.RemoveSkill(unit, self.value))


class IgnoreWeaponDisadvantage(ItemComponent):
    nid = 'ignore_weapon_disadvantage'
    desc = "Weapon disadvantage defined in the weapon types editor is ignored by this item."
    tag = ItemTags.EXTRA

    author = 'Beccarte'

    def ignore_weapon_disadvantage(self, unit, item):
        return True
class ChangeDescOnEquip(ItemComponent):
    nid = 'change_desc_on_equip'
    desc = "A unit with this item equipped will change desc of item."
    tag = ItemTags.EXTRA

    expose = ComponentType.NewMultipleOptions

    options = {
        'list_unit': (ComponentType.List, ComponentType.Unit),
        'desc_for_unit': ComponentType.String,
        'desc_for_other': ComponentType.String,
        'item_desc': ComponentType.String,
    }

    def __init__(self, value=None):
        self.value = {
            'list_unit': [],
            'desc_for_unit': '',
            'desc_for_other': '',
            'item_desc': '',
        }
        if value:
            self.value.update(value)
    def on_equip_item(self, unit, item):        for u in self.value['list_unit']:            if u == unit.nid:                action.do(action.ChangeItemDesc(item, self.value['desc_for_unit']))            else:                action.do(action.ChangeItemDesc(item, self.value['desc_for_other']))

    def on_unequip_item(self, unit, item):        action.do(action.ChangeItemDesc(item, self.value['item_desc']))
class ChangeAnimation(ItemComponent):
    nid = 'change_animation'
    desc = "Change the unit's animation"
    tag = ItemTags.AESTHETIC

    author = 'Beccarte'

    expose = ComponentType.String
    value = ''

    def change_animation(self, unit, item):
        return self.valueclass EclipseOneHp(ItemComponent):
    nid = 'eclipse_one_hp'
    desc = "Target will be reduced to 1 hp on hit"
    tag = ItemTags.CUSTOM
    
    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        true_damage = damage = target.get_hp()-1
        actions.append(action.ChangeHP(target, -damage))

        # For animation
        playback.append(pb.DamageHit(unit, item, target, damage, true_damage))
        if true_damage == 0:
            playback.append(pb.HitSound('No Damage'))
            playback.append(pb.HitAnim('MapNoDamage', target))class Lethality(ItemComponent):
    nid = 'lethality'
    desc = "One hit target"
    tag = ItemTags.CUSTOM
    
    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        true_damage = damage = target.get_hp()
        actions.append(action.ChangeHP(target, -damage))

        # For animation
        playback.append(pb.DamageHit(unit, item, target, damage, true_damage))
        if true_damage == 0:
            playback.append(pb.HitSound('No Damage'))
            playback.append(pb.HitAnim('MapNoDamage', target))class DamageImproved(ItemComponent):
    nid = 'damage_improved'
    desc = "Item does damage on hit"
    tag = ItemTags.WEAPON

    expose = ComponentType.Int
    value = 0

    def damage(self, unit, item):
        return self.value

    def target_restrict(self, unit, item, def_pos, splash) -> bool:
        # Restricts target based on whether any unit is an enemy
        defender = game.board.get_unit(def_pos)
        if defender and skill_system.check_enemy(unit, defender):
            return True
        for s_pos in splash:
            s = game.board.get_unit(s_pos)
            if s and skill_system.check_enemy(unit, s):
                return True
        return False

    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        if not 'Bane_Effect' and 'Lethality_Effect' in [skill.nid for skill in unit.skills]:
            playback_nids = [brush.nid for brush in playback]
            if 'attacker_partner_phase' in playback_nids or 'defender_partner_phase' in playback_nids:
                damage = combat_calcs.compute_assist_damage(unit, target, item, target.get_weapon(), mode, attack_info)
            else:
                damage = combat_calcs.compute_damage(unit, target, item, target.get_weapon(), mode, attack_info)

            # Reduce damage if in Grandmaster Mode
            if game.rng_mode == RNGOption.GRANDMASTER:
                hit = utils.clamp(combat_calcs.compute_hit(unit, target, item, target.get_weapon(), mode, attack_info), 0, 100)
                damage = int(damage * float(hit) / 100)

            true_damage = min(damage, target.get_hp())
            actions.append(action.ChangeHP(target, -damage))

            # For animation
            playback.append(pb.DamageHit(unit, item, target, damage, true_damage))
            if damage == 0:
                playback.append(pb.HitSound('No Damage'))
                playback.append(pb.HitAnim('MapNoDamage', target))

    def on_glancing_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):        if not 'Bane_Effect' and 'Lethality_Effect' in [skill.nid for skill in unit.skills]:
            playback_nids = [brush.nid for brush in playback]
            if 'attacker_partner_phase' in playback_nids or 'defender_partner_phase' in playback_nids:
                damage = combat_calcs.compute_assist_damage(unit, target, item, target.get_weapon(), mode, attack_info)
            else:
                damage = combat_calcs.compute_damage(unit, target, item, target.get_weapon(), mode, attack_info)

            # Reduce damage if in Grandmaster Mode
            if game.rng_mode == RNGOption.GRANDMASTER:
                hit = utils.clamp(combat_calcs.compute_hit(unit, target, item, target.get_weapon(), mode, attack_info), 0, 100)
                damage = int(damage * float(hit) / 100)

            damage //= 2  # Because glancing hit

            true_damage = min(damage, target.get_hp())
            actions.append(action.ChangeHP(target, -damage))

            # For animation
            playback.append(pb.DamageHit(unit, item, target, damage, true_damage))
            if damage == 0:
                playback.append(pb.HitAnim('MapNoDamage', target))
            else:
                playback.append(pb.HitAnim('MapGlancingHit', target))

    def on_crit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):        if not 'Bane_Effect' and 'Lethality_Effect' in [skill.nid for skill in unit.skills]:
            playback_nids = [brush.nid for brush in playback]
            if 'attacker_partner_phase' in playback_nids or 'defender_partner_phase' in playback_nids:
                damage = combat_calcs.compute_assist_damage(unit, target, item, target.get_weapon(), mode, attack_info, crit=True)
            else:
                damage = combat_calcs.compute_damage(unit, target, item, target.get_weapon(), mode, attack_info, crit=True)

            # Reduce damage if in Grandmaster Mode (although crit doesn't make much sense with Grandmaster mode)
            if game.rng_mode == RNGOption.GRANDMASTER:
                hit = utils.clamp(combat_calcs.compute_hit(unit, target, item, target.get_weapon(), mode, attack_info), 0, 100)
                damage = int(damage * float(hit) / 100)

            true_damage = min(damage, target.get_hp())
            actions.append(action.ChangeHP(target, -damage))

            playback.append(pb.DamageCrit(unit, item, target, damage, true_damage))
            if damage == 0:
                playback.append(pb.HitSound('No Damage'))
                playback.append(pb.HitAnim('MapNoDamage', target))


# --- Weapon-granted slot skills -------------------------------------------------
# Maps the regular skill-category nid -> matching weapon skill-category nid. A skill
# whose components contain the regular nid occupies that category in the Skill Swap
# UI; a skill whose components contain the weapon nid is treated as the same
# category but takes precedence whenever the weapon is equipped.
_WEAPON_SLOT_PAIRS = (
    ('special_skill', 'weapon_special_skill'),
    ('slota_skill', 'weapon_slota_skill'),
    ('slotb_skill', 'weapon_slotb_skill'),
    ('slotc_skill', 'weapon_slotc_skill'),
    ('assist_skill', 'weapon_assist_skill'),
)


def _category_of_weapon_skill(skill_prefab):
    """Return the regular-category nid that a weapon skill prefab maps to, or None."""
    if not skill_prefab:
        return None
    comp_nids = {c.nid for c in skill_prefab.components}
    for regular_nid, weapon_nid in _WEAPON_SLOT_PAIRS:
        if weapon_nid in comp_nids:
            return regular_nid
    return None


def _find_displaced_skill(unit, regular_nid):
    """Find the regular slot skill currently on the unit for that category, if any."""
    for sk in unit.skills:
        prefab = DB.skills.get(sk.nid)
        if not prefab:
            continue
        if any(c.nid == regular_nid for c in prefab.components):
            return sk
    return None


class WeaponSkillsOnEquip(ItemComponent):
    nid = 'weapon_skills_on_equip'
    desc = ("Item grants the listed skills while equipped. Each weapon skill must "
            "carry one of the weapon_*_skill components; it overrides whatever "
            "regular slot skill currently occupies that category. The displaced "
            "regular skill is shelved on the unit's WeaponDisplacedSkills field "
            "and restored automatically when the weapon is unequipped.")
    tag = ItemTags.EXTRA

    expose = (ComponentType.List, ComponentType.Skill)  # list of skill nids
    value = []

    def on_equip_item(self, unit, item):
        displaced_map = dict(unit.get_field('WeaponDisplacedSkills') or {})
        for skill_nid in self.value:
            prefab = DB.skills.get(skill_nid)
            regular_nid = _category_of_weapon_skill(prefab)
            if regular_nid:
                # Shelve any regular skill currently in that category before adding the weapon skill.
                existing = _find_displaced_skill(unit, regular_nid)
                if existing is not None and existing.nid != skill_nid:
                    displaced_map[skill_nid] = existing.nid
                    action.do(action.RemoveSkill(unit, existing))
            action.do(action.AddSkill(unit, skill_nid, source=item.uid, source_type=SourceType.ITEM))
        action.do(action.ChangeField(unit, 'WeaponDisplacedSkills', displaced_map))

    def on_unequip_item(self, unit, item):
        displaced_map = dict(unit.get_field('WeaponDisplacedSkills') or {})
        for skill_nid in self.value:
            action.do(action.RemoveSkill(unit, skill_nid, count=1, source=item.uid, source_type=SourceType.ITEM))
            restored = displaced_map.pop(skill_nid, None)
            if restored:
                # Restore the displaced regular skill via give_skill semantics so the
                # after_gain_skill hooks resolve any other conflicts naturally.
                action.do(action.AddSkill(unit, restored))
        action.do(action.ChangeField(unit, 'WeaponDisplacedSkills', displaced_map))

class HpCostOverride(ItemComponent):
    nid = 'hp_cost_override'
    desc = ("Optional per-item HP cost override for Mari's magic. When present on an item, "
            "the spell HP-cost eval prefers this exact value over the rank-based table. "
            "Add this only to special spells whose HP cost should not follow their weapon rank.")
    tag = ItemTags.CUSTOM
    author = "v0"

    expose = ComponentType.Int
    value = 1

_SPELL_RANK_ORDER = ['E', 'D', 'C', 'B', 'A', 'S', 'SS']

def _spell_rank_index(rank) -> int:
    try:
        return _SPELL_RANK_ORDER.index(str(rank).strip().upper())
    except ValueError:
        return 0

def mari_book_learnable(mari, allowed=None) -> list:
    """Return the list of MariSpell nids Mari could learn from a study book right now.

    Rules (shared with the Mari_Book_Learn event so can_use and the menu stay in sync):
      - spell is offered by this book (its nid is in ``allowed``); when ``allowed`` is None
        every spell in the MariSpell catalog is considered
      - spell not already known
      - spell rank not above Mari's current Staff weapon rank
    """
    if not mari:
        return []
    try:
        catalog = list(game.get_data('MariSpell'))
    except Exception:
        return []
    known = mari.get_field('known_spells') or []
    try:
        staff_wexp = mari.wexp.get('Staff', 0)
    except Exception:
        staff_wexp = 0
    _wr = DB.weapon_ranks.get_rank_from_wexp(staff_wexp)
    cap = _spell_rank_index(_wr.rank if _wr else 'E')
    result = []
    for r in catalog:
        if allowed is not None and r.nid not in allowed:
            continue
        if r.nid in known:
            continue
        if _spell_rank_index(r.rank) > cap:
            continue
        result.append(r.nid)
    return result

class LearnSpellFromBook(ItemComponent):
    nid = 'learn_spell_from_book'
    desc = ("Mari-only study book. When Mari uses the item at full durability it opens the "
            "linked event so she can learn one rank-appropriate spell from the book's spell "
            "list, then the book is consumed by its normal uses. Configure two fields: the "
            "event to trigger, and the list of spell items this book can teach. The chosen "
            "spells' nids are passed to the event as 'mari_new_spell'. Only usable by Mari "
            "and only when no use has been spent.")
    tag = ItemTags.CUSTOM
    author = "v0"

    expose = ComponentType.NewMultipleOptions

    options = {
        'event': ComponentType.Event,
        'spells': (ComponentType.List, ComponentType.Item),  # Stored as Nids
    }

    _should_fire = False

    def __init__(self, value=None):
        self.value = {
            'event': '',
            'spells': [],
        }
        if value and isinstance(value, dict):
            self.value.update(value)
        elif value:
            # Backwards compatibility with the old single-Event value.
            self.value['event'] = value

    @property
    def event_nid(self):
        return self.value.get('event', '')

    @property
    def spell_nids(self) -> list:
        return list(self.value.get('spells') or [])

    def can_use(self, unit, item) -> bool:
        if not unit or unit.nid != 'Mari':
            return False
        # Require full durability: never let a partially-used book be studied again.
        if 'uses' in item.data and 'starting_uses' in item.data:
            if item.data['uses'] < item.data['starting_uses']:
                return False
        # Only usable if at least one of this book's spells is something she can learn now.
        return bool(mari_book_learnable(unit, self.spell_nids))

    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        self._should_fire = True

    def end_combat(self, playback, unit, item, target, item2, mode):
        if self._should_fire and unit and unit.nid == 'Mari':
            event_prefab = DB.events.get_from_nid(self.event_nid)
            if event_prefab:
                # Pass the book's spell nids so the event can offer exactly these spells.
                local_args = {'item': item, 'mode': mode, 'mari_new_spell': self.spell_nids}
                game.events.trigger_specific_event(event_prefab.nid, unit, unit, unit.position, local_args)
        self._should_fire = False

class HPCostAsUses(ItemComponent):
    nid = 'hp_cost_as_uses'
    desc = ("Display the item's HP cost in place of Uses in menus (supports both hp_cost and "
            "eval_hp_cost). Used for Mari's spells so the Attack/Spell list shows the HP that will "
            "be consumed instead of a uses count. Do not combine with other uses-display components.")
    tag = ItemTags.USES
    delim = None

    def _calc_uses(self, unit, item):
        # eval_hp_cost takes priority (Mari's elemental spells use it); fall back to flat hp_cost.
        if getattr(item, 'eval_hp_cost', None):
            from app.engine import evaluate
            try:
                return int(evaluate.evaluate(item.eval_hp_cost.value, unit, local_args={'item': item}))
            except Exception:
                logging.error("hp_cost_as_uses: couldn't evaluate eval_hp_cost for %s", item.nid)
                return None
        if getattr(item, 'hp_cost', None):
            return item.hp_cost.value
        return None

    def _calc_max_uses(self, unit, item):
        return None

    def _font_color(self, unit, item):
        from app.engine.fonts import FONT
        # Red signals the HP that will be spent to cast; grey when the spell
        # can't currently be used (missing weapon rank, not enough HP, etc.).
        color = 'red'
        if not item_funcs.available(unit, item):
            color = 'grey'
        if 'text-' + color in FONT:
            return color
        return None

    def item_uses_display(self, unit, item):
        from app.engine.game_menus.icon_options import UsesDisplayConfig
        return UsesDisplayConfig(self._calc_uses, self.delim, self._calc_max_uses, self._font_color, unit=unit, item=item)