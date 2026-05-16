from __future__ import annotations
from typing import TYPE_CHECKING

import logging
import math

from app.data.database.components import ComponentType
from app.data.database.skill_components import SkillComponent, SkillTags
from app.engine import action, equations, item_funcs, skill_system
from app.engine.game_state import game
import app.engine.combat.playback as pb
from app.utilities import static_random, utils
from app.engine.source_type import SourceType

if TYPE_CHECKING:
    from app.engine.objects.item import ItemObject

class MultiSkill(SkillComponent):
    nid = 'multi_skill'
    desc = 'Folds a list of skills into a single wrapper skill. Useful for skills with complicated effects or trigger conditions.'
    tag = SkillTags.ADVANCED
    author = 'GreyWulfos'

    expose = (ComponentType.List, ComponentType.Skill)    

    # conditional component to be passed on to child skills
    class ParentCondition(SkillComponent):
        nid = 'parent_condition'
        desc = ''
        tag = SkillTags.HIDDEN

        expose = ComponentType.Int

        ignore_conditional = True
        
        def condition(self, unit, item):
            parent_skill = game.get_skill(self.value)
            if not parent_skill:
                logging.error(f"Parent UID %{self.value} does not correspond to any known skill.")
                return False
            return all([component.condition(unit, item) for component in parent_skill.components if component.defines('condition')])

    # add all child skills when the skill is added
    def before_add(self, unit, skill):
        parent_condition = self.ParentCondition(skill.uid)

        subactions = []
        for child_skill in self.value:
            if child_skill == skill:
                logging.error("Skill %s attempted to create a recursive multiskill." % skill.nid)
                return
            subactions.append(action.AddSkill(unit, child_skill, source=skill, source_type=SourceType.MULTISKILL))
        for subaction in subactions:
            action.execute(subaction)
            subaction.skill_obj.components.append(parent_condition)

    # remove all child skills when the skill is removed
    def after_remove(self, unit, skill):
        for subaction in [action.RemoveSkill(unit, child_skill, source=skill, source_type=SourceType.MULTISKILL) for child_skill in self.value]:
            action.execute(subaction) 

class Ability(SkillComponent):
    nid = 'ability'
    desc = "Give unit an item as an extra ability"
    tag = SkillTags.ADVANCED

    expose = ComponentType.Item

    def extra_ability(self, unit):
        item_uid = self.skill.data.get('ability_item_uid', None)
        if item_uid and game.item_registry.get(item_uid, None):
            return game.item_registry[item_uid]
        else:
            new_item = item_funcs.create_item(unit, self.value)
            self.skill.data['ability_item_uid'] = new_item.uid
            game.register_item(new_item)
            return new_item

    def end_combat_unconditional(self, playback, unit, item, target, item2, mode):
        if item and item.nid == self.value:
            action.do(action.TriggerCharge(unit, self.skill))

class CombatArt(SkillComponent):
    nid = 'combat_art'
    desc = "Unit has the ability to apply an extra effect to next attack"
    tag = SkillTags.ADVANCED

    expose = ComponentType.Skill
    _action = None

    def init(self, skill):
        self.skill.data['active'] = False

    def combat_art(self, unit):
        return self.value

    def start_combat(self, playback, unit, item, target, item2, mode):
        if self._action:
            playback.append(pb.AttackPreProc(unit, self._action.skill_obj))

    def on_activation(self, unit):
        # I don't think this needs to use an action
        # because there will be no point in the turnwheel
        # where you could stop it at True
        self.skill.data['active'] = True
        self._action = action.AddSkill(unit, self.value)
        action.do(self._action)

    def on_deactivation(self, unit):
        self.skill.data['active'] = False
        # Remove the added combat art skill
        if self._action and self._action.skill_obj:
            action.do(action.RemoveSkill(unit, self._action.skill_obj))
        self._action = None

    def end_combat_unconditional(self, playback, unit, item, target, item2, mode):
        if self.skill.data.get('active'):
            action.do(action.TriggerCharge(unit, self.skill))
        self.skill.data['active'] = False


class MenuCategory(SkillComponent):
    nid = 'menu_category'
    desc = "Categorize an ability or combat art in the menu"
    tag = SkillTags.ADVANCED

    expose = ComponentType.String

    def menu_category(self):
        return self.value

class AutomaticCombatArt(SkillComponent):
    nid = 'automatic_combat_art'
    desc = "Unit will be given skill on upkeep and removed on endstep"
    tag = SkillTags.ADVANCED

    expose = ComponentType.Skill

    def on_upkeep(self, actions, playback, unit):
        actions.append(action.AddSkill(unit, self.value))
        actions.append(action.TriggerCharge(unit, self.skill))

    def on_endstep(self, actions, playback, unit):
        actions.append(action.RemoveSkill(unit, self.value))


class AllowedWeapons(SkillComponent):
    nid = 'allowed_weapons'
    desc = "Defines what weapons are allowed for combat art or proc skill"
    tag = SkillTags.ADVANCED

    expose = ComponentType.String

    def weapon_filter(self, unit, item) -> bool:
        from app.engine import evaluate
        try:
            return bool(evaluate.evaluate(self.value, unit, local_args={'item': item, 'skill': self.skill}))
        except Exception as e:
            print("Couldn't evaluate conditional {%s} %s" % (self.value, e))
        return False


def get_proc_rate(unit, skill) -> int:
    for component in skill.components:
        if component.defines('proc_rate'):
            return component.proc_rate(unit)
    return 100  # 100 is default


def get_modify_self_proc_rate(unit, skill) -> int:
    for component in skill.components:
        if component.defines('modify_self_proc_rate'):
            return component.modify_self_proc_rate(unit)
    return 0  # 0 is default


def get_modify_enemy_proc_rate(unit, skill) -> int:
    for component in skill.components:
        if component.defines('modify_enemy_proc_rate'):
            return component.modify_enemy_proc_rate(unit)
    return 0  # 0 is default


def get_modified_proc_rate(unit, skill, target=None) -> int:
    proc_rate = get_proc_rate(unit, skill)
    proc_rate += sum(get_modify_self_proc_rate(unit, s) for s in unit.skills)
    if target:
        proc_rate += sum(get_modify_enemy_proc_rate(target, s) for s in target.skills)
    return proc_rate


def get_weapon_filter(skill, unit, item) -> bool:
    for component in skill.components:
        if component.defines('weapon_filter'):
            return component.weapon_filter(unit, item)
    return True


class ProcGainSkillForTurn(SkillComponent):
    nid = 'proc_turn_skill'
    desc = "Unit has a chance to gain the proc skill at the beginning of the turn, and will lose it on endstep"
    tag = SkillTags.ADVANCED

    expose = ComponentType.Skill
    _did_action = False

    def on_upkeep(self, actions, playback, unit):
        proc_rate = get_modified_proc_rate(unit, self.skill)
        if static_random.get_combat() < proc_rate:
            actions.append(action.AddSkill(unit, self.value))
            actions.append(action.TriggerCharge(unit, self.skill))
            self._did_action = True

    def on_endstep_unconditional(self, actions, playback, unit):
        if self._did_action:
            actions.append(action.RemoveSkill(unit, self.value))


class AttackProc(SkillComponent):
    nid = 'attack_proc'
    desc = "Allows skill to proc on a single attacking strike"
    tag = SkillTags.ADVANCED

    expose = ComponentType.Skill
    _did_action = False

    def start_sub_combat(self, actions, playback, unit, item, target, item2, mode, attack_info):
        if mode == 'attack' and target and skill_system.check_enemy(unit, target):
            if not get_weapon_filter(self.skill, unit, item):
                return
            proc_rate = get_modified_proc_rate(unit, self.skill, target)
            if static_random.get_combat() < proc_rate:
                act = action.AddSkill(unit, self.value)
                action.do(act)
                if act.skill_obj:
                    playback.append(pb.AttackProc(unit, act.skill_obj))
                self._did_action = True

    def end_sub_combat_unconditional(self, actions, playback, unit, item, target, item2, mode, attack_info):
        if self._did_action:
            action.do(action.TriggerCharge(unit, self.skill))
            action.do(action.RemoveSkill(unit, self.value))
        self._did_action = False


class DefenseProc(SkillComponent):
    nid = 'defense_proc'
    desc = "Allows skill to proc when defending a single strike"
    tag = SkillTags.ADVANCED

    expose = ComponentType.Skill
    _did_action = False

    def start_sub_combat(self, actions, playback, unit, item, target, item2, mode, attack_info):
        if mode == 'defense' and target and skill_system.check_enemy(unit, target):
            if not get_weapon_filter(self.skill, unit, item):
                return
            proc_rate = get_modified_proc_rate(unit, self.skill, target)
            if static_random.get_combat() < proc_rate:
                act = action.AddSkill(unit, self.value)
                action.do(act)
                if act.skill_obj:
                    playback.append(pb.DefenseProc(unit, act.skill_obj))
                self._did_action = True

    def end_sub_combat_unconditional(self, actions, playback, unit, item, target, item2, mode, attack_info):
        if self._did_action:
            action.do(action.TriggerCharge(unit, self.skill))
            action.do(action.RemoveSkill(unit, self.value))
        self._did_action = False


class AttackPreProc(SkillComponent):
    nid = 'attack_pre_proc'
    desc = "Allows skill to proc when initiating combat. Lasts entire combat."
    tag = SkillTags.ADVANCED

    expose = ComponentType.Skill
    _did_action = False

    def start_combat(self, playback, unit, item, target, item2, mode):
        if mode == 'attack' and target and skill_system.check_enemy(unit, target):
            if not get_weapon_filter(self.skill, unit, item):
                return
            proc_rate = get_modified_proc_rate(unit, self.skill, target)
            if static_random.get_combat() < proc_rate:
                act = action.AddSkill(unit, self.value)
                action.do(act)
                if act.skill_obj:
                    playback.append(pb.AttackPreProc(unit, act.skill_obj))
                self._did_action = True

    def end_combat_unconditional(self, playback, unit, item, target, item2, mode):
        if self._did_action:
            action.do(action.TriggerCharge(unit, self.skill))
            action.do(action.RemoveSkill(unit, self.value))
            self._did_action = False


class DefensePreProc(SkillComponent):
    nid = 'defense_pre_proc'
    desc = "Allows skill to proc when defending in combat. Lasts entire combat."
    tag = SkillTags.ADVANCED

    expose = ComponentType.Skill
    _did_action = False

    def start_combat(self, playback, unit, item, target, item2, mode):
        if mode == 'defense' and target and skill_system.check_enemy(unit, target):
            if not get_weapon_filter(self.skill, unit, item):
                return
            proc_rate = get_modified_proc_rate(unit, self.skill, target)
            if static_random.get_combat() < proc_rate:
                act = action.AddSkill(unit, self.value)
                action.do(act)
                if act.skill_obj:
                    playback.append(pb.DefensePreProc(unit, act.skill_obj))
                self._did_action = True

    def end_combat_unconditional(self, playback, unit, item, target, item2, mode):
        if self._did_action:
            action.do(action.TriggerCharge(unit, self.skill))
            action.do(action.RemoveSkill(unit, self.value))
            self._did_action = False


class ProcRate(SkillComponent):
    nid = 'proc_rate'
    desc = "Set the proc rate"
    tag = SkillTags.ADVANCED

    expose = ComponentType.Equation

    def proc_rate(self, unit):
        return equations.parser.get(self.value, unit)


class ModifySelfProcRate(SkillComponent):
    nid = 'modify_self_proc_rate'
    desc = "Modify the proc rate"
    tag = SkillTags.ADVANCED

    expose = ComponentType.Int

    def modify_self_proc_rate(self, unit):
        return self.value


class ModifyEnemyProcRate(SkillComponent):
    nid = 'modify_enemy_proc_rate'
    desc = "Modify the proc rate"
    tag = SkillTags.ADVANCED

    expose = ComponentType.Int

    def modify_enemy_proc_rate(self, unit):
        return self.value


class AstraProc(SkillComponent):
    nid = 'astra_proc'
    desc = "Specific Proc component for Astra or Adept"
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions

    options = {
        'extra_attacks': ComponentType.Int,
        'damage_percent': ComponentType.Float,
        'show_proc_effects': ComponentType.Bool,
    }

    def __init__(self, value=None):
        self.value = {
            'extra_attacks': 4,
            'damage_percent': 0.5,
            'show_proc_effects': True,
        }
        if value:
            self.value.update(value)
        
        # Instance variables - each skill instance has its own state
        self._num_procs = 0  # Number of times this astra has procced
        self._should_modify_damage = False  # Are we actually in an astra section of combat
        self._hitcount = 0  # Hit counts

    def start_sub_combat(self, actions, playback, unit, item, target, item2, mode, attack_info):
        # If we haven't done any subattacks
        if attack_info[1] == 0:
            self._num_procs = 0
            self._should_modify_damage = False

        if not self._should_modify_damage:
            self._hitcount = 0

        if not self._should_modify_damage and mode == 'attack' and target and skill_system.check_enemy(unit, target):
            if not get_weapon_filter(self.skill, unit, item):
                return
            proc_rate = get_modified_proc_rate(unit, self.skill, target)
            if static_random.get_combat() < proc_rate:
                self._num_procs += 1
                self._should_modify_damage = True
                action.do(action.TriggerCharge(unit, self.skill))
                if bool(self.value['show_proc_effects']):
                    playback.append(pb.AttackProc(unit, self.skill))

    def dynamic_multiattacks(self, unit, item, target, item2, mode, attack_info, base_value) -> int:
        return int(self.value['extra_attacks']) * self._num_procs

    def damage_multiplier(self, unit, item, target, item2, mode, attack_info, base_value):
        if self._should_modify_damage:
            return max(0, float(self.value['damage_percent']))
        return 1

    def after_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        if self._should_modify_damage:
            self._hitcount += 1
            if self._hitcount >= int(self.value['extra_attacks']) + 1:    
                self._should_modify_damage = False

    def cleanup_combat(self, playback, unit, item, target, item2, mode):
        # Shouln't be necessary but just in case
        self._num_procs = 0
        self._should_modify_damage = False
        self._hitcount = 0



class AetherProc(SkillComponent):
    nid = 'aether_proc'
    desc = "Specific Proc component for Aether"
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions

    options = {
        'extra_attacks': ComponentType.Int,
        'lifelink': ComponentType.Float,
        'luna_def_multiplier': ComponentType.Float,
        'show_proc_effects': ComponentType.Bool,
    }

    def __init__(self, value=None):
        self.value = {
            'extra_attacks': 1,         # Each proc adds this many bonus strikes (1 Sol + 1 Luna = 2 total)
            'lifelink': 0.5,            # Sol: fraction of damage to heal (0.5 = 50%)
            'luna_def_multiplier': 0.5, # Luna: fraction of target's defense applied (0.5 = ignore 50%)
            'show_proc_effects': True,
        }
        if value:
            self.value.update(value)
        
        # Instance variables - each skill instance has its own state
        self._num_procs = 0              # Number of times Aether has procced this combat
        self._should_modify_damage = False  # Are we currently inside an Aether proc sequence
        self._hitcount = 0               # Number of strikes landed since proc began

    def start_sub_combat(self, actions, playback, unit, item, target, item2, mode, attack_info):
        # Reset at the very first subattack of the combat round
        if attack_info[1] == 0 and not self._should_modify_damage:
            self._num_procs = 0
            self._should_modify_damage = False

        if not self._should_modify_damage:
            self._hitcount = 0

        if not self._should_modify_damage and mode == 'attack' and target and skill_system.check_enemy(unit, target):
            if not get_weapon_filter(self.skill, unit, item):
                return
            proc_rate = get_modified_proc_rate(unit, self.skill, target)
            if static_random.get_combat() < proc_rate:
                self._num_procs += 1
                self._should_modify_damage = True
                action.do(action.TriggerCharge(unit, self.skill))
                if bool(self.value['show_proc_effects']):
                    playback.append(pb.AttackProc(unit, self.skill))

    def dynamic_multiattacks(self, unit, item, target, item2, mode, attack_info, base_value) -> int:
        return int(self.value['extra_attacks']) * self._num_procs

    def dynamic_damage(self, unit, item, target, item2, mode, attack_info, base_value) -> int:
        if self._should_modify_damage and self._hitcount == 1:
            return math.ceil(
                float(target.stats['DEF']) * float(self.value['luna_def_multiplier'])
            )
        return 0

    def after_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        if not self._should_modify_damage:
            return

        # Sol effect: heal from the first strike of the proc only
        if self._hitcount == 0:
            last_hit = next(
                (p for p in reversed(playback)
                 if p.nid in ('damage_hit', 'damage_crit') and p.attacker == unit),
                None
            )
            if last_hit:
                true_damage = int(
                    utils.clamp(last_hit.true_damage, 0, target.get_hp())
                    * float(self.value['lifelink'])
                )
                if true_damage > 0:
                    actions.append(action.ChangeHP(unit, true_damage))
                    playback.append(pb.HealHit(unit, item, unit, true_damage, true_damage))

        # Luna effect: bonus damage based on target's defense

        self._hitcount += 1
        if self._hitcount >= int(self.value['extra_attacks']) + 1:
            self._should_modify_damage = False

    def cleanup_combat(self, playback, unit, item, target, item2, mode):
        # Shouln't be necessary but just in case
        self._num_procs = 0
        self._should_modify_damage = False
        self._hitcount = 0


class ItemOverride(SkillComponent):
    nid = 'item_override'
    desc = 'allows overriding of item properties'
    tag = SkillTags.ADVANCED

    expose = ComponentType.Item
    value = ""

    item: ItemObject = None

    def get_components(self, unit):
        if not self.value:
            return []
        if not self.item:
            from app.engine import item_funcs
            self.item = item_funcs.create_item(unit, self.value)
        return self.item.components
