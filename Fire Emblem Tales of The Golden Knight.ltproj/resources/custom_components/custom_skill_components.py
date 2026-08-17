from __future__ import annotations

from app.data.database.components import ComponentType
from app.data.database.database import DB
from app.data.database.skill_components import SkillComponent, SkillTags
from app.engine import (action, banner, combat_calcs, engine, equations,
                        image_mods, item_funcs, item_system, skill_system,
                        target_system)
from app.engine.game_state import game
from app.engine.objects.unit import UnitObject
from app.utilities import utils, static_random
from app.engine.combat import playback as pb
from app.utilities.enums import Strikefrom app.engine.source_type import SourceType
import logging

class DoNothing(SkillComponent):
    nid = 'do_nothing'
    desc = 'does nothing'
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int
    value = 1


class ComparisonStatBonus(SkillComponent):
    nid = 'comparison_stat_bonus'
    desc = 'Adds to the user\'s Resistance only when skills compare stats.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int
    value = 0
    ignore_conditional = True

    def comparison_stat_bonus(self, unit, stat):
        return self.value if stat == 'RES' else 0


class Obstruct(SkillComponent):
    nid = 'obstruct'
    desc = ('Enemies without Pass cannot move through spaces adjacent to the '
            'user while the user has at least this fraction of maximum HP.')
    tag = SkillTags.MOVEMENT

    expose = ComponentType.Float
    value = 0.9

    def obstructs_movement(self, unit, mover):
        return bool(
            unit.position and unit.get_hp() > 0 and
            unit.get_hp() >= unit.get_max_hp() * self.value and
            skill_system.check_enemy(unit, mover) and
            not skill_system.pass_through(mover))


class Feint(SkillComponent):
    nid = 'feint'
    desc = 'Configuration for a Feint effect applied after a Rally assist.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {
        'stat': ComponentType.Stat,
        'effect': ComponentType.Skill,
    }
    value = {
        'stat': 'STR',
        'effect': '',
    }


class LostOnNextAction(SkillComponent):
    nid = 'lost_on_next_action'
    desc = 'Remove after this unit completes its next non-combat action.'
    tag = SkillTags.CUSTOM

    def on_wait(self, unit, actively_chosen):
        action.do(action.RemoveSkill(unit, self.skill))

    def on_end_chapter_unconditional(self, unit, skill):
        action.do(action.RemoveSkill(unit, self.skill))

class SavageBlowFates(SkillComponent):
    nid = 'savage_blow_fates'
    desc = 'Deals 20% Current HP damage to enemies within the given number of spaces from target.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int
    value = 0
    author = 'Lord_Tweed'

    def end_combat(self, playback, unit, item, target, item2, mode):
        if target and skill_system.check_enemy(unit, target):
            r = set(range(self.value+1))
            locations = game.target_system.get_shell({target.position}, r, game.board.bounds)
            for loc in locations:
                target2 = game.board.get_unit(loc)
                if target2 and target2 is not target and skill_system.check_enemy(unit, target2):
                    end_health = target2.get_hp() - (int(target2.get_hp() * .2))
                    action.do(action.SetHP(target2, max(1, end_health)))

class LostOnTakeHit(SkillComponent):
    nid = 'lost_on_take_hit'
    desc = "This skill is lost when receiving an attack (it must hit)"
    tag = SkillTags.CUSTOM

    author = 'Lord_Tweed'

    def after_take_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        if target and skill_system.check_enemy(unit, target) and strike == Strike.HIT:
            action.do(action.RemoveSkill(unit, self.skill))

class EventOnTakeHit(SkillComponent):
    nid = 'event_stack_on_take_hit'
    desc = "An event procs when receiving an attack (it must hit)"
    tag = SkillTags.CUSTOM

    expose = ComponentType.Event
    value = ''

    def after_take_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        if target and skill_system.check_enemy(unit, target) and strike == Strike.HIT:
            game.events.trigger_specific_event(self.value, unit, unit, unit.position, {'item': None, 'mode': None})
        
class LostOnStrike(SkillComponent):
    nid = 'lost_on_strike'
    desc = "This skill is after performing a strike (hit or miss)"
    tag = SkillTags.CUSTOM

    def after_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        action.do(action.RemoveSkill(unit, self.skill))
        
class GainSkillOnStrike(SkillComponent):
    nid = 'gain_on_strike'
    desc = "Gain skill after performing a strike (hit or miss)"
    tag = SkillTags.CUSTOM
    
    expose = ComponentType.Skill

    def after_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        action.do(action.AddSkill(unit, self.value))

class SelfNihil(SkillComponent):
    nid = 'self_nihil'
    desc = "Skill does not work if the unit has this other skill"
    tag = SkillTags.CUSTOM

    expose = (ComponentType.List, ComponentType.Skill)
    value = []

    ignore_conditional = True

    def condition(self, unit, item):
        all_target_nihils = set(self.value)
        for skill in unit.skills:
          if skill.nid in all_target_nihils:
            return False
        return True

class SelfRecoil(SkillComponent):
    nid = 'self_recoil'
    desc = "Unit takes non-lethal damage after any combat"
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int
    value = 0
    author = 'Lord_Tweed'

    def end_combat(self, playback, unit, item, target, item2, mode):
        if target:
            end_health = unit.get_hp() - self.value
            action.do(action.SetHP(unit, max(1, end_health)))
            action.do(action.TriggerCharge(unit, self.skill))

class EvalGaleforce(SkillComponent):
    nid = 'eval_galeforce'
    desc = "Unit can move again if conditions are met. Value must resolve to a Boolean."
    tag = SkillTags.CUSTOM

    expose = ComponentType.String
    value = ''
    author = 'Lord_Tweed'

    def end_combat(self, playback, unit, item, target, item2, mode):
        from app.engine import evaluate
        try:
            x = bool(evaluate.evaluate(self.value, unit, target, unit.position, {'item': item, 'item2': item2, 'mode': mode}))
            if x:
                action.do(action.Reset(unit))
                action.do(action.TriggerCharge(unit, self.skill))
        except Exception as e:
            print("%s: Could not evaluate EvalGaleforce condition %s" % (e, self.value))

class UpkeepEvent(SkillComponent):
    nid = 'upkeep_event'
    desc = "Triggers the designated event at upkeep"
    tag = SkillTags.CUSTOM

    expose = ComponentType.Event
    value = ''

    def on_upkeep(self, actions, playback, unit):
        game.events.trigger_specific_event(self.value, unit, unit, unit.position, {'item': None, 'mode': None})

class EndstepEvent(SkillComponent):
    nid = 'endstep_event'
    desc = "Triggers the designated event at endstep"
    tag = SkillTags.CUSTOM

    expose = ComponentType.Event
    value = ''

    def on_endstep(self, actions, playback, unit):
        game.events.trigger_specific_event(self.value, unit, unit, unit.position, {'item': None, 'mode': None})

class CritEvent(SkillComponent):
    nid = 'crit_event'
    desc = "Triggers the designated event on crit"
    tag = SkillTags.CUSTOM

    expose = ComponentType.Event
    value = ''

    def end_combat(self, playback, unit, item, target, item2, mode):
        mark_playbacks = [p for p in playback if p.nid in ('mark_crit')]
        if target and any(p.attacker is unit for p in mark_playbacks):
            game.events.trigger_specific_event(self.value, unit, target, unit.position, {'item': item, 'item2': item2, 'mode': mode})

class UpkeepSkillGain(SkillComponent):
    nid = 'upkeep_skill_gain'
    desc = "Grants the designated skill at upkeep"
    tag = SkillTags.CUSTOM

    expose = ComponentType.Skill

    def on_upkeep(self, actions, playback, unit):
        action.do(action.AddSkill(unit, self.value))

class EndstepSkillGain(SkillComponent):
    nid = 'endstep_skill_gain'
    desc = "Grants the designated skill at endstep"
    tag = SkillTags.CUSTOM

    expose = ComponentType.Skill

    def on_endstep(self, actions, playback, unit):
        action.do(action.AddSkill(unit, self.value))

class LostOnEndNextCombat(SkillComponent):
    nid = 'lost_on_end_next_combat'
    desc = "Remove after subsequent combat"
    tag = SkillTags.CUSTOM

    author = "Xilirite"
    expose = (ComponentType.MultipleOptions)

    value = [["NumberOfCombats (X)", "2", 'Number of combats before expiration'],["LostOnSelf (T/F)", "T", 'Lost after self combat (e.g. vulnerary)'],["LostOnAlly (T/F)", "T", 'Lost after combat with an ally'],["LostOnEnemy (T/F)", "T", 'Lost after combat with an enemy'],["LostOnSplash (T/F)", "T", 'Lost after combat if using an AOE item']]

    def init(self, skill):
        self.skill.data['combats'] = self.values.get('NumberOfCombats (X)', '2')

    @property
    def values(self) -> Dict[str, str]:
        return {value[0]: value[1] for value in self.value}

    def post_combat(self, playback, unit, item, target, item2, mode):
        from app.engine import skill_system
        remove_skill = False
        if self.values.get('LostOnSelf (T/F)', 'T') == 'T':
            if unit == target:
                val = int(self.skill.data['combats']) - 1
                action.do(action.SetObjData(self.skill, 'combats', val))
                if int(self.skill.data['combats']) <= 0:
                    remove_skill = True

        if self.values.get('LostOnAlly (T/F)', 'T') == 'T':
            if target:
                if skill_system.check_ally(unit, target):
                    val = int(self.skill.data['combats']) - 1
                    action.do(action.SetObjData(self.skill, 'combats', val))
                    if int(self.skill.data['combats']) <= 0:
                        remove_skill = True
        if self.values.get('LostOnEnemy (T/F)', 'T') == 'T':
            if target:
                if skill_system.check_enemy(unit, target):
                    val = int(self.skill.data['combats']) - 1
                    action.do(action.SetObjData(self.skill, 'combats', val))
                    if int(self.skill.data['combats']) <= 0:
                        remove_skill = True
        if self.values.get('LostOnSplash (T/F)', 'T') == 'T':
            if not target:
                val = int(self.skill.data['combats']) - 1
                action.do(action.SetObjData(self.skill, 'combats', val))
                if int(self.skill.data['combats']) <= 0:
                    remove_skill = True

        if remove_skill:
            action.do(action.RemoveSkill(unit, self.skill))

    def on_end_chapter(self, unit, skill):
        action.do(action.RemoveSkill(unit, self.skill))

class FullMiracle(SkillComponent):
    nid = 'full_miracle'
    desc = "Unit will not die after combat, but will instead be resurrected with full hp"
    tag = SkillTags.CUSTOM

    def cleanup_combat(self, playback, unit, item, target, item2, mode):
        if unit.get_hp() <= 0:
            action.do(action.SetHP(unit, unit.get_max_hp()))
            game.death.miracle(unit)
            action.do(action.TriggerCharge(unit, self.skill))

class UndamagedCondition(SkillComponent):
    nid = 'undamaged_condition'
    desc = "Skill is active while unit has not taken damage this chapter"
    tag = SkillTags.CUSTOM
    author = 'rainlash'

    ignore_conditional = True

    _took_damage_this_combat = False

    def init(self, skill):
        self.skill.data['_has_taken_damage'] = False

    def condition(self, unit):
        return not self.skill.data['_has_taken_damage']

    def after_take_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        for act in reversed(actions):
            if isinstance(act, action.ChangeHP) and act.num < 0 and act.unit == unit:
                self._took_damage_this_combat = True
                break

    def end_combat(self, playback, unit, item, target, item2, mode):
        if self._took_damage_this_combat:
            action.do(action.SetObjData(self.skill, '_has_taken_damage', True))
        self._took_damage_this_combat = False

    def on_end_chapter(self, unit, skill):
        self.skill.data['_has_taken_damage'] = False
        self._took_damage_this_combat = False

class CombatTriggerCharge(SkillComponent):
    nid = 'combat_trigger_charge'
    desc = "This skill will triger a charge usage as long as combat was with an enemy. A hit must have been landed."
    tag = SkillTags.CUSTOM
    author = 'Lord_Tweed'

    def end_combat(self, playback, unit, item, target, item2, mode):
        mark_playbacks = [p for p in playback if p.nid in ('mark_hit', 'mark_crit')]
        if target and skill_system.check_enemy(unit, target) and any(p.attacker == unit for p in mark_playbacks):
            action.do(action.TriggerCharge(unit, self.skill))

class HealOnKill(SkillComponent):
    nid = 'heal_on_kill'
    desc = 'Gives +X health on kill'
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int

    value = 0

    def end_combat(self, playback, unit, item, target, item2, mode):
        mark_playbacks = [p for p in playback if p.nid in ('mark_miss', 'mark_hit', 'mark_crit')]
        if target and target.get_hp() <= 0:
            heal = self.value
            action.do(action.ChangeHP(unit, heal))

class EvalRegeneration(SkillComponent):
    nid = 'eval_regeneration'
    desc = "Unit restores HP at beginning of turn, based on the given evaluation"
    tag = SkillTags.CUSTOM

    expose = ComponentType.String

    def on_upkeep(self, actions, playback, unit):
        max_hp = equations.parser.hitpoints(unit)
        if unit.get_hp() < max_hp:
            from app.engine import evaluate
            try:
                hp_change = int(evaluate.evaluate(self.value, unit))
            except:
                logging.error("Couldn't evaluate %s conditional" % self.value)
                hp_change = 0
            actions.append(action.ChangeHP(unit, hp_change))
            if hp_change > 0:
                # Playback
                playback.append(pb.HitSound('MapHeal'))
                playback.append(pb.DamageNumbers(unit, -hp_change))
                if hp_change >= 30:
                    name = 'MapBigHealTrans'
                elif hp_change >= 15:
                    name = 'MapMediumHealTrans'
                else:
                    name = 'MapSmallHealTrans'
                playback.append(pb.CastAnim(name))

class CannotUseItemsOnEnemy(SkillComponent):
    nid = 'cannot_use_items_enemy'
    desc = "Unit cannot use or equip any items that target specifically enemies"
    tag = SkillTags.CUSTOM

    def available(self, unit, item) -> bool:
        return not item.target_enemy
        
class EventAfterKill(SkillComponent):
    nid = 'event_after_kill'
    desc = "Triggers event after a kill"
    tag = SkillTags.CUSTOM

    expose = ComponentType.Event

    def end_combat(self, playback, unit, item, target, item2, mode):
        if target and target.get_hp() <= 0:
            game.events.trigger_specific_event(self.value, unit, target, unit.position, {'item': item, 'item2': item2, 'mode': mode})
            action.do(action.TriggerCharge(unit, self.skill))
            
class EventBeforeCombat(SkillComponent):
    nid = 'event_before_combat'
    desc = 'Calls event on combat start'
    tag = SkillTags.CUSTOM

    expose = ComponentType.Event
    value = ''

    def start_combat(self, playback, unit, item, target, item2, mode):
        game.events.trigger_specific_event(self.value, unit, target, unit.position, {'item': item, 'item2': item2, 'mode': mode})
        
class PermanentDamage(SkillComponent):
    nid = 'permanent_damage'
    desc = 'All damage taken is dealt to max HP'
    tag = SkillTags.CUSTOM
    
    def after_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        stat_changes = {}
        if unit.get_max_hp() > int(unit._fields['Undeath_Current_HP']):
            for i in range(unit.get_max_hp() - int(unit._fields['Undeath_Current_HP'])):
                action.do(action.AddSkill(unit, 'Undying_Will'))
            stat_changes['HP'] = int(unit._fields['Undeath_Current_HP']) - unit.get_max_hp()
            action.do(action.ApplyStatChanges(unit, stat_changes, False))
        elif unit.get_max_hp() < int(unit._fields['Undeath_Current_HP']):
            action.do(action.RemoveSkill(unit, 'Undying_Will', count=(int(unit._fields['Undeath_Current_HP']) - unit.get_max_hp())))
            stat_changes['HP'] = min(int(unit._fields['Undeath_Current_HP']) - unit.get_max_hp(), len([skill.nid for skill in unit.skills if skill.nid == 'Undying_Will']) - unit.get_max_hp())
            action.do(action.ApplyStatChanges(unit, stat_changes, False))
        stat_changes['HP'] = max(unit.get_hp() - unit.get_max_hp(), 1 - unit.get_max_hp())
        action.do(action.ApplyStatChanges(unit, stat_changes, False))
        action.do(action.ChangeField(unit, key='Undeath_Current_HP', value=unit.get_max_hp()))

    def after_take_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        stat_changes = {}
        if unit.get_max_hp() > int(unit._fields['Undeath_Current_HP']):
            for i in range(unit.get_max_hp() - int(unit._fields['Undeath_Current_HP'])):
                action.do(action.AddSkill(unit, 'Undying_Will'))
            stat_changes['HP'] = int(unit._fields['Undeath_Current_HP']) - unit.get_max_hp()
            action.do(action.ApplyStatChanges(unit, stat_changes, False))
        elif unit.get_max_hp() < int(unit._fields['Undeath_Current_HP']):
            action.do(action.RemoveSkill(unit, 'Undying_Will', count=(int(unit._fields['Undeath_Current_HP']) - unit.get_max_hp())))
            stat_changes['HP'] = min(int(unit._fields['Undeath_Current_HP']) - unit.get_max_hp(), len([skill.nid for skill in unit.skills if skill.nid == 'Undying_Will']) - unit.get_max_hp())
            action.do(action.ApplyStatChanges(unit, stat_changes, False))
        stat_changes['HP'] = max(unit.get_hp() - unit.get_max_hp(), 1 - unit.get_max_hp())
        action.do(action.ApplyStatChanges(unit, stat_changes, False))
        action.do(action.ChangeField(unit, key='Undeath_Current_HP', value=unit.get_max_hp()))
        
    def cleanup_combat(self, playback, unit, item, target, item2, mode):
        stat_changes = {}
        if unit.get_max_hp() > int(unit._fields['Undeath_Current_HP']):
            for i in range(unit.get_max_hp() - int(unit._fields['Undeath_Current_HP'])):
                action.do(action.AddSkill(unit, 'Undying_Will'))
            stat_changes['HP'] = int(unit._fields['Undeath_Current_HP']) - unit.get_max_hp()
            action.do(action.ApplyStatChanges(unit, stat_changes, False))
        elif unit.get_max_hp() < int(unit._fields['Undeath_Current_HP']):
            action.do(action.RemoveSkill(unit, 'Undying_Will', count=(int(unit._fields['Undeath_Current_HP']) - unit.get_max_hp())))
            stat_changes['HP'] = min(int(unit._fields['Undeath_Current_HP']) - unit.get_max_hp(), len([skill.nid for skill in unit.skills if skill.nid == 'Undying_Will']) - unit.get_max_hp())
            action.do(action.ApplyStatChanges(unit, stat_changes, False))
        stat_changes['HP'] = max(unit.get_hp() - unit.get_max_hp(), 1 - unit.get_max_hp())
        action.do(action.ApplyStatChanges(unit, stat_changes, False))
        action.do(action.ChangeField(unit, key='Undeath_Current_HP', value=unit.get_max_hp()))
        
    def end_combat(self, playback, unit, item, target, item2, mode):
        print(unit.get_max_hp())
        print(int(unit._fields['Undeath_Current_HP']))
        stat_changes = {}
        if unit.get_max_hp() > int(unit._fields['Undeath_Current_HP']):
            for i in range(unit.get_max_hp() - int(unit._fields['Undeath_Current_HP'])):
                action.do(action.AddSkill(unit, 'Undying_Will'))
            stat_changes['HP'] = int(unit._fields['Undeath_Current_HP']) - unit.get_max_hp()
            action.do(action.ApplyStatChanges(unit, stat_changes, False))
        elif unit.get_max_hp() < int(unit._fields['Undeath_Current_HP']):
            action.do(action.RemoveSkill(unit, 'Undying_Will', count=(int(unit._fields['Undeath_Current_HP']) - unit.get_max_hp())))
            stat_changes['HP'] = min(int(unit._fields['Undeath_Current_HP']) - unit.get_max_hp(), len([skill.nid for skill in unit.skills if skill.nid == 'Undying_Will']) - unit.get_max_hp())
            action.do(action.ApplyStatChanges(unit, stat_changes, False))
        stat_changes['HP'] = max(unit.get_hp() - unit.get_max_hp(), 1 - unit.get_max_hp())
        action.do(action.ApplyStatChanges(unit, stat_changes, False))
        action.do(action.ChangeField(unit, key='Undeath_Current_HP', value=unit.get_max_hp()))

class EvalUpkeepDamage(SkillComponent):
    nid = 'eval_upkeep_damage'
    desc = "Unit takes damage at upkeep based on eval"
    tag = SkillTags.CUSTOM

    expose = ComponentType.String

    def _playback_processing(self, playback, unit, hp_change):
        # Playback
        if hp_change < 0:
            playback.append(pb.HitSound('Attack Hit ' + str(static_random.get_randint(1, 5))))
            playback.append(pb.UnitTintAdd(unit, (255, 255, 255)))
            playback.append(pb.DamageNumbers(unit, abs(hp_change)))
        elif hp_change > 0:
            playback.append(pb.HitSound('MapHeal'))
            if hp_change >= 30:
                name = 'MapBigHealTrans'
            elif hp_change >= 15:
                name = 'MapMediumHealTrans'
            else:
                name = 'MapSmallHealTrans'
            playback.append(pb.CastAnim(name))
            playback.append(pb.DamageNumbers(unit, abs(hp_change)))

    def on_upkeep(self, actions, playback, unit):
        from app.engine import evaluate
        try:
            hp_change = -int(evaluate.evaluate(self.value, unit))
        except:
            logging.error("Couldn't evaluate %s conditional" % self.value)
            hp_change = 0
        actions.append(action.ChangeHP(unit, hp_change))
        actions.append(action.TriggerCharge(unit, self.skill))
        self._playback_processing(playback, unit, hp_change)
        skill_system.after_take_strike(actions, playback, unit, None, None, None, 'defense', (0, 0), Strike.HIT)

class CopySafe(SkillComponent):
    nid = 'copysafe'
    desc = "Skill is safe to copy to other units. If there are dependant skills, include them as the values."
    tag = SkillTags.CUSTOM
    
    expose = (ComponentType.List, ComponentType.Skill)
    
class EventAfterCombat(SkillComponent):
    nid = 'event_after_combat'
    desc = 'calls event after combat'
    tag = SkillTags.ADVANCED

    expose = ComponentType.Event
    value = ''

    def end_combat(self, playback, unit: UnitObject, item, target: UnitObject, item2, mode):
        game.events.trigger_specific_event(self.value, unit, target, unit.position, {'item': item, 'item2': item2, 'mode': mode})
        
class AbilityAttackCharge(SkillComponent):
    nid = 'ability_attack_charge'
    desc = "Give unit an item as an extra ability, only costs charges when attacking"
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
        if item and item.nid == self.value and mode == 'attack':
            action.do(action.TriggerCharge(unit, self.skill))

class Inherited(SkillComponent):
    nid = 'inherited'
    desc = "Don't actually put this on skills, please and thank you."
    tag = SkillTags.CUSTOM

class GainSkillAfterCrit(SkillComponent):
    nid = 'gain_skill_after_crit'
    desc = "Gives a skill to user after a crit"
    tag = SkillTags.CUSTOM

    expose = ComponentType.Skill

    def end_combat(self, playback, unit, item, target, item2, mode):
        mark_playbacks = [p for p in playback if p.nid in (
            'mark_crit')]
        if target and any(p.attacker is unit and (p.main_attacker is unit or p.attacker is p.main_attacker.strike_partner)
                          for p in mark_playbacks):  # Unit is overall attacker
            action.do(action.AddSkill(unit, self.value, target))
            action.do(action.TriggerCharge(unit, self.skill))

class ActiveCombatChargeIncrease(SkillComponent):
    nid = 'active_combat_charge_increase'
    desc = "Increases charge of skill each combat, if unit initiated"
    tag = SkillTags.CHARGE

    expose = ComponentType.Int
    value = 1

    ignore_conditional = True

    def end_combat(self, playback, unit, item, target, item2, mode):
        mark_playbacks = [p for p in playback if p.nid in (
            'mark_miss', 'mark_hit', 'mark_crit')]
        if not self.skill.data.get('active') and target and any(p.attacker is unit and (p.main_attacker is unit or p.attacker is p.main_attacker.strike_partner) for p in mark_playbacks):
            new_value = self.skill.data['charge'] + self.value
            new_value = min(new_value, self.skill.data['total_charge'])
            action.do(action.SetObjData(self.skill, 'charge', new_value))
            
class AdditionalInventory(SkillComponent):
    nid = 'additional_inventory'
    desc = "Unit can hold additional regular items rather than accessories"
    tag = SkillTags.BASE

    expose = ComponentType.Int
    value = 2

    def num_items_offset(self, unit) -> int:
        return self.value

    def num_accessories_offset(self, unit) -> int:
        return -1 * self.value

class GiveStatusOnTakeHit(SkillComponent):
    nid = 'give_status_on_take_hit'
    desc = "When receiving an attack, give a status to the attacker"
    tag = SkillTags.CUSTOM
    author = 'Lord_Tweed'
    
    expose = ComponentType.Skill

    def after_take_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        if target:
            actions.append(action.AddSkill(target, self.value, unit))
            actions.append(action.TriggerCharge(unit, self.skill))

class Dazzled(SkillComponent):
    nid = 'dazzled'
    desc = "Skill is treated as Dazzled. Allows us to have multiple different skills that are treated the same way."
    tag = SkillTags.CUSTOM

class Blinded(SkillComponent):
    nid = 'blinded'
    desc = "Skill is treated as Blinded. Allows us to have multiple different skills that are treated the same way."
    tag = SkillTags.CUSTOM

class Paragon(SkillComponent):
    nid = 'paragon'
    desc = "Skill is treated as Paragon. Allows us to have multiple different skills that are treated the same way."
    tag = SkillTags.CUSTOM

class TetherParameters(SkillComponent):
    nid = 'tether_parameters'
    desc = "Skill can be purchased in the Skill Shop. The cost should not exceed 50."
    tag = SkillTags.CUSTOM

    expose = (ComponentType.NewMultipleOptions)
    options = {
        "cost": ComponentType.Int,
        "level": ComponentType.Int,
    }
    
    def __init__(self, value=None):
        self.value = {
            "cost": 0,
            "level": 0,
        }
        if value:
            self.value.update(value)

class SavageStatus(SkillComponent):
    nid = 'savage_status'
    desc = 'Inflicts the given status to enemies within the given number of spaces from target.'
    tag = SkillTags.CUSTOM
    author = 'Lord_Tweed'

    expose = (ComponentType.NewMultipleOptions)
    options = {
        "status": ComponentType.Skill,
        "range": ComponentType.Int,
    }
    
    def __init__(self, value=None):
        self.value = {
            "status": 'Canto',
            "range": 1,
        }
        if value:
            self.value.update(value)

    def end_combat(self, playback, unit, item, target, item2, mode):
        if target and skill_system.check_enemy(unit, target):
            r = set(range(self.value.get('range') + 1))
            locations = game.target_system.get_shell({target.position}, r, game.board.bounds)
            for loc in locations:
                target2 = game.board.get_unit(loc)
                if target2 and target2 is not target and skill_system.check_enemy(unit, target2):
                    action.do(action.AddSkill(target2, self.value.get('status'), unit))

class VisualCharge(SkillComponent):
    nid = 'visual_charge'
    desc = "Skill displays charges, but does not actually use them itself. Unaffected by Trigger Charge."
    tag = SkillTags.CHARGE
    author = 'Lord_Tweed'

    expose = ComponentType.Int
    value = 5

    ignore_conditional = True

    def init(self, skill):
        self.skill.data['charge'] = 0
        self.skill.data['total_charge'] = self.value

    def condition(self, unit, item):
        return True

    def on_end_chapter(self, unit, skill):
        self.skill.data['charge'] = 0

    def text(self) -> str:
        return str(self.skill.data['charge'])

    def cooldown(self):
        return 1

class RemoveStatusAfterCombat(SkillComponent):
    nid = 'remove_status_after_combat'
    desc = "Removes a status from target enemy after combat"
    tag = SkillTags.CUSTOM

    expose = ComponentType.Skill

    def end_combat(self, playback, unit, item, target, item2, mode):
        from app.engine import skill_system
        if target and skill_system.check_enemy(unit, target):
            action.do(action.RemoveSkill(target, self.value))
            action.do(action.TriggerCharge(unit, self.skill))

def get_weapon_filter(skill, unit, item) -> bool:
    for component in skill.components:
        if component.defines('weapon_filter'):
            return component.weapon_filter(unit, item)
    return True

def get_proc_rate_with_target(unit, target, skill) -> int:
    for component in skill.components:
        if component.defines('proc_rate'):
            return component.proc_rate(unit, target)
    return 100  # 100 is default


_SPECIAL_PROC_EFFECT_COMPONENTS = {
    'attack_proc', 'attack_proc_with_target',
    'defense_proc', 'defense_proc_with_target',
}
_SPECIAL_PROC_SOURCE_COMPONENTS = {'astra_proc', 'aether_proc'}


def _special_proc_nids(unit):
    proc_nids = set()
    for skill in unit.skills:
        if not (getattr(skill, 'special_skill', None)
                or getattr(skill, 'weapon_special_skill', None)):
            continue
        for component in skill.components:
            if component.nid in _SPECIAL_PROC_EFFECT_COMPONENTS and component.value:
                proc_nids.add(component.value)
            elif component.nid in _SPECIAL_PROC_SOURCE_COMPONENTS:
                proc_nids.add(skill.nid)
    return proc_nids


def _special_proc_count(playback, unit):
    proc_nids = _special_proc_nids(unit)
    if not proc_nids:
        return 0
    return sum(
        brush.nid in ('attack_proc', 'defense_proc')
        and brush.unit is unit
        and getattr(brush.skill, 'nid', None) in proc_nids
        for brush in playback)


def _did_trigger_special(playback, unit):
    return bool(_special_proc_count(playback, unit))


def _is_special_skill(skill) -> bool:
    return bool(getattr(skill, 'special_skill', None)
                or getattr(skill, 'weapon_special_skill', None))


def _is_special_damage_strike(unit) -> bool:
    """Whether unit is currently resolving a Wrath-eligible Special strike."""
    for skill in unit.skills:
        if not _is_special_skill(skill):
            continue
        for component in skill.components:
            if component.nid in ('attack_proc', 'attack_proc_with_target'):
                if getattr(component, '_did_action', False):
                    return True
            elif component.nid == 'astra_proc':
                if (getattr(component, '_should_modify_damage', False)
                        and getattr(component, '_hitcount', 0) == 0):
                    return True
            elif component.nid == 'aether_proc':
                if (getattr(component, '_should_modify_damage', False)
                        and getattr(component, '_hitcount', 0) in (0, 1)):
                    return True
    return False


def _is_highest_priority_wrath(component, unit) -> bool:
    candidates = []
    for index, skill in enumerate(unit.skills):
        for other_component in skill.components:
            if other_component.nid == 'wrath_special_bonus':
                candidates.append((
                    _skill_priority(skill), getattr(skill, 'uid', index),
                    other_component))
    if not candidates:
        return False
    return max(candidates, key=lambda candidate: candidate[:2])[2] is component


def _is_highest_priority_special_spiral(component, unit) -> bool:
    candidates = []
    for index, skill in enumerate(unit.skills):
        for other_component in skill.components:
            if other_component.nid == 'special_spiral_bonus':
                candidates.append((
                    _skill_priority(skill), getattr(skill, 'uid', index),
                    other_component))
    if not candidates:
        return False
    return max(candidates, key=lambda candidate: candidate[:2])[2] is component


class SpecialSkillPulse(SkillComponent):
    nid = 'special_skill_pulse'
    desc = ('After the user triggers a Special Skill, each later attack that '
            'does not trigger it increases its activation rate by X%.')
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int
    value = 0

    def init(self, skill):
        skill.data.setdefault('special_skill_pulse_armed', False)
        skill.data.setdefault('special_skill_pulse_bonus', 0)
        self._seen_special_proc_count = 0

    def start_combat(self, playback, unit, item, target, item2, mode):
        self._seen_special_proc_count = 0

    def modify_self_proc_rate(self, unit):
        if skill_system.condition(self.skill, unit):
            return self.skill.data['special_skill_pulse_bonus']
        return 0

    def _did_trigger_new_special(self, playback, unit):
        proc_count = _special_proc_count(playback, unit)
        if not proc_count:
            # Unit tests can provide a strike-local playback list, while the
            # solver provides a combat-wide list. Resetting only on an empty
            # list supports both without treating a prior proc as a new one.
            self._seen_special_proc_count = 0
            return False
        if proc_count > self._seen_special_proc_count:
            self._seen_special_proc_count = proc_count
            return True
        return False

    def _process_strike(self, actions, playback, unit, mode, expected_mode):
        if self._did_trigger_new_special(playback, unit):
            if not self.skill.data['special_skill_pulse_armed']:
                actions.append(action.SetObjData(
                    self.skill, 'special_skill_pulse_armed', True))
            if self.skill.data['special_skill_pulse_bonus']:
                actions.append(action.SetObjData(
                    self.skill, 'special_skill_pulse_bonus', 0))
        elif (mode == expected_mode and
              self.skill.data['special_skill_pulse_armed']):
            actions.append(action.SetObjData(
                self.skill, 'special_skill_pulse_bonus',
                self.skill.data['special_skill_pulse_bonus'] + self.value))

    def after_strike(self, actions, playback, unit, item, target, item2, mode,
                     attack_info, strike):
        self._process_strike(actions, playback, unit, mode, 'attack')

    def after_take_strike(self, actions, playback, unit, item, target, item2,
                          mode, attack_info, strike):
        self._process_strike(actions, playback, unit, mode, 'defense')


class SpecialSpiralBonus(SkillComponent):
    nid = 'special_spiral_bonus'
    desc = ('After the user triggers a Special Skill, adds its activation '
            'rate through the next action involving the user.')
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int
    value = 0
    ignore_conditional = True

    def init(self, skill):
        skill.data.setdefault('special_spiral_active', False)
        skill.data.setdefault('special_spiral_skip_next_wait', False)
        self._triggered_this_combat = False

    def start_combat(self, playback, unit, item, target, item2, mode):
        self._triggered_this_combat = False
        if (not _is_highest_priority_special_spiral(self, unit)
                and self.skill.data['special_spiral_active']):
            action.do(action.SetObjData(
                self.skill, 'special_spiral_active', False))
            action.do(action.SetObjData(
                self.skill, 'special_spiral_skip_next_wait', False))

    def modify_self_proc_rate(self, unit):
        if (self.skill.data['special_spiral_active']
                and _is_highest_priority_special_spiral(self, unit)):
            return self.value
        return 0

    def after_strike(self, actions, playback, unit, item, target, item2, mode,
                     attack_info, strike):
        if (not _is_highest_priority_special_spiral(self, unit)
                or not skill_system.condition(self.skill, unit)
                or not _did_trigger_special(playback, unit)):
            return
        if not self.skill.data['special_spiral_active']:
            actions.append(action.SetObjData(
                self.skill, 'special_spiral_active', True))
        self._triggered_this_combat = True

    def end_combat(self, playback, unit, item, target, item2, mode):
        if not _is_highest_priority_special_spiral(self, unit):
            self._triggered_this_combat = False
            return
        if self._triggered_this_combat:
            action.do(action.SetObjData(
                self.skill, 'special_spiral_skip_next_wait', mode == 'attack'))
        elif self.skill.data['special_spiral_active']:
            action.do(action.SetObjData(
                self.skill, 'special_spiral_active', False))
            action.do(action.SetObjData(
                self.skill, 'special_spiral_skip_next_wait', False))
        self._triggered_this_combat = False

    def on_wait(self, unit, actively_chosen):
        if self.skill.data['special_spiral_skip_next_wait']:
            action.do(action.SetObjData(
                self.skill, 'special_spiral_skip_next_wait', False))
        elif self.skill.data['special_spiral_active']:
            action.do(action.SetObjData(
                self.skill, 'special_spiral_active', False))


class WrathSpecialBonus(SkillComponent):
    nid = 'wrath_special_bonus'
    desc = ('Adds proc rate while the combat condition is active and adds '
            'flat damage to Special Skill strikes.')
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {
        'proc_rate_bonus': ComponentType.Int,
        'damage_bonus': ComponentType.Int,
    }

    def __init__(self, value=None):
        self.value = {
            'proc_rate_bonus': 0,
            'damage_bonus': 0,
        }
        if value:
            self.value.update(value)

    def modify_self_proc_rate(self, unit):
        # get_modified_proc_rate calls this hook directly, so it bypasses the
        # normal skill_system dispatcher condition check. CombatCondition has
        # already captured its pre-combat result at this point.
        if (not _is_highest_priority_wrath(self, unit)
                or not skill_system.condition(self.skill, unit)):
            return 0
        return int(self.value['proc_rate_bonus'])

    def raw_damage(self, unit, item, target, item2, mode, attack_info, base_value):
        # raw_damage is condition-gated by skill_system, unlike proc rate.
        if (not _is_highest_priority_wrath(self, unit)
                or not _is_special_damage_strike(unit)):
            return 0
        return int(self.value['damage_bonus'])


def _highest_priority_cancel_affinity_value(unit):
    candidates = []
    for index, skill in enumerate(unit.skills):
        for component in skill.components:
            if component.nid != 'cancel_affinity':
                continue
            try:
                value = int(component.value)
            except (TypeError, ValueError):
                continue
            candidates.append((_skill_priority(skill), getattr(skill, 'uid', index), value))
    return max(candidates, key=lambda candidate: candidate[:2])[2] if candidates else None


class CancelAffinity(SkillComponent):
    nid = 'cancel_affinity'
    desc = ('Controls skill-sourced weapon-triangle multipliers while leaving '
            'direct item modifiers, including Reaver, unchanged.')
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int
    value = 1

    def weapon_triangle_multiplier_override(
            self, unit, item, target, item2, has_disadvantage,
            self_skill_multiplier, foe_skill_multiplier):
        tier = _highest_priority_cancel_affinity_value(unit)
        if tier == 1:
            return 1.0, 1.0
        if tier == 2:
            return 1.0, 1.0 if has_disadvantage else foe_skill_multiplier
        if tier == 3:
            return (1.0,
                    2.0 - foe_skill_multiplier if has_disadvantage
                    else foe_skill_multiplier)
        return None


def _is_highest_priority_lull(component, unit) -> bool:
    candidates = []
    for index, skill in enumerate(unit.skills):
        for other_component in skill.components:
            if other_component.nid == 'lull_combat_stats':
                candidates.append((
                    _skill_priority(skill), getattr(skill, 'uid', index),
                    other_component))
    if not candidates:
        return False
    return max(candidates, key=lambda candidate: candidate[:2])[2] is component


class LullCombatStats(SkillComponent):
    nid = 'lull_combat_stats'
    desc = ('Applies the selected Lull stat penalties and neutralizes the '
            'foe\'s positive net bonuses during combat.')
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {
        'penalty': ComponentType.Int,
        'affect_attack': ComponentType.Bool,
        'affect_speed': ComponentType.Bool,
        'affect_defense': ComponentType.Bool,
        'affect_resistance': ComponentType.Bool,
    }

    def __init__(self, value=None):
        self.value = {
            'penalty': 0,
            'affect_attack': False,
            'affect_speed': False,
            'affect_defense': False,
            'affect_resistance': False,
        }
        if value:
            self.value.update(value)

    def _active(self, unit, target) -> bool:
        return bool(target) and _is_highest_priority_lull(self, unit)

    def _amount(self, target, stat_nid) -> int:
        return int(self.value['penalty']) + max(0, target.stat_bonus(stat_nid))

    def dynamic_resist(self, unit, item, target, item2, mode, attack_info,
                       base_value):
        if not self.value['affect_attack'] or not self._active(unit, target):
            return 0
        attack_stat = ('MAG' if item2 and item_funcs.is_magic(target, item2)
                       else 'STR')
        return self._amount(target, attack_stat)

    def dynamic_damage(self, unit, item, target, item2, mode, attack_info,
                       base_value):
        if not self._active(unit, target):
            return 0
        is_magic = bool(item) and item_funcs.is_magic(unit, item)
        if self.value['affect_defense'] and not is_magic:
            return self._amount(target, 'DEF')
        if self.value['affect_resistance'] and is_magic:
            return self._amount(target, 'RES')
        return 0

    def dynamic_attack_speed(self, unit, item, target, item2, mode,
                             attack_info, base_value):
        if self.value['affect_speed'] and self._active(unit, target):
            return self._amount(target, 'SPD')
        return 0

    def dynamic_defense_speed(self, unit, item, target, item2, mode,
                              attack_info, base_value):
        if self.value['affect_speed'] and self._active(unit, target):
            return self._amount(target, 'SPD')
        return 0


class LowerDefResSource(SkillComponent):
    nid = 'lower_def_res_source'
    desc = 'Marks a skill that calculates damage using the lower of DEF or RES.'
    tag = SkillTags.CUSTOM


def _is_highest_priority_lower_def_res_neutralizer(component, unit) -> bool:
    candidates = []
    for index, skill in enumerate(unit.skills):
        for other_component in skill.components:
            if other_component.nid == 'neutralize_lower_def_res':
                candidates.append((
                    _skill_priority(skill), getattr(skill, 'uid', index),
                    other_component))
    if not candidates:
        return False
    return max(candidates, key=lambda candidate: candidate[:2])[2] is component


def _has_active_lower_def_res_source(unit, item) -> bool:
    for skill in unit.skills:
        if any(component.nid == 'lower_def_res_source'
               for component in skill.components):
            if skill_system.condition(skill, unit, item):
                return True
    return False


class NeutralizeLowerDefRes(SkillComponent):
    nid = 'neutralize_lower_def_res'
    desc = ('Neutralizes Foe skills that calculate damage using the lower of '
            'DEF or RES.')
    tag = SkillTags.CUSTOM

    def dynamic_resist(self, unit, item, target, item2, mode, attack_info,
                       base_value):
        if (not target or not item2 or
                not _is_highest_priority_lower_def_res_neutralizer(self, unit) or
                not _has_active_lower_def_res_source(target, item2)):
            return 0

        resolved_formula = combat_calcs.resolve_defensive_formula(
            unit, item, target, item2,
            item_system.resist_formula, skill_system.resist_formula,
            item_system.resist_formula_override,
            skill_system.resist_formula_override,
            skill_system.Defaults.resist_formula)
        if resolved_formula != 'WORSE_DEFENSE':
            return 0

        normal_formula = ('MAGIC_DEFENSE'
                          if item_funcs.is_magic(target, item2)
                          else 'DEFENSE')
        normal_resist = equations.parser.get(normal_formula, unit)
        worse_resist = equations.parser.get('WORSE_DEFENSE', unit)
        return max(0, normal_resist - worse_resist)


class StardustMirageBonus(SkillComponent):
    nid = 'stardust_mirage_bonus'
    desc = ('Adds Speed-based true damage to each Stardust Mirage strike and '
            'prevents crits during the proc sequence.')
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {
        'speed_damage_percent': ComponentType.Float,
        'disable_crit': ComponentType.Bool,
    }

    def __init__(self, value=None):
        self.value = {
            'speed_damage_percent': 0.1,
            'disable_crit': True,
        }
        if value:
            self.value.update(value)

    def _astra_proc_is_active(self) -> bool:
        for component in self.skill.components:
            if component.nid == 'astra_proc':
                return bool(getattr(component, '_should_modify_damage', False))
        return False

    def raw_damage(self, unit, item, target, item2, mode, attack_info, base_value):
        if not self._astra_proc_is_active():
            return 0
        return int(unit.get_stat('SPD') * self.value['speed_damage_percent'])

    def crit_multiplier(self, unit, item, target, item2, mode, attack_info, base_value):
        if self.value['disable_crit'] and self._astra_proc_is_active():
            return 0
        return 1


class EvalProcRate(SkillComponent):
    nid = 'eval_proc_rate'
    desc = "Evaluates the proc rate. Only compatible with custom Proc components."
    tag = SkillTags.CUSTOM

    expose = ComponentType.String

    def proc_rate(self, unit, target):
        from app.engine import evaluate
        try:
            return int(evaluate.evaluate(self.value, unit, target))
        except:
            logging.error("Couldn't evaluate %s conditional" % self.value)
        return 0

class AttackProcWithTarget(SkillComponent):
    nid = 'attack_proc_with_target'
    desc = "Allows skill to proc on a single attacking strike. Target is passed into the Proc Rate method. Only use this with custom Proc Rate components."
    tag = SkillTags.CUSTOM

    expose = ComponentType.Skill
    _did_action = False

    def start_sub_combat(self, actions, playback, unit, item, target, item2, mode, attack_info):
        if mode == 'attack' and target and skill_system.check_enemy(unit, target):
            if not get_weapon_filter(self.skill, unit, item):
                return
            proc_rate = get_proc_rate_with_target(unit, target, self.skill)
            if static_random.get_combat() < proc_rate:
                act = action.AddSkill(unit, self.value)
                action.do(act)
                if act.skill_obj:
                    playback.append(pb.AttackProc(unit, act.skill_obj))
                self._did_action = True

    def end_sub_combat(self, actions, playback, unit, item, target, item2, mode, attack_info):
        if self._did_action:
            action.do(action.TriggerCharge(unit, self.skill))
            action.do(action.RemoveSkill(unit, self.value))
        self._did_action = False

class DefenseProcWithTarget(SkillComponent):
    nid = 'defense_proc_with_target'
    desc = "Allows skill to proc when defending a single strike. Target is passed into the Proc Rate method. Only use this with custom Proc Rate components."
    tag = SkillTags.CUSTOM

    expose = ComponentType.Skill
    _did_action = False

    def start_sub_combat(self, actions, playback, unit, item, target, item2, mode, attack_info):
        if mode == 'defense' and target and skill_system.check_enemy(unit, target):
            if not get_weapon_filter(self.skill, unit, item):
                return
            proc_rate = get_proc_rate_with_target(unit, target, self.skill)
            if static_random.get_combat() < proc_rate:
                act = action.AddSkill(unit, self.value)
                action.do(act)
                if act.skill_obj:
                    playback.append(pb.DefenseProc(unit, act.skill_obj))
                self._did_action = True

    def end_sub_combat(self, actions, playback, unit, item, target, item2, mode, attack_info):
        if self._did_action:
            action.do(action.TriggerCharge(unit, self.skill))
            action.do(action.RemoveSkill(unit, self.value))
        self._did_action = False

class CombatArtProc(SkillComponent):
    nid = 'combat_art_proc'
    desc = "Skill is procced from a Combat Art."
    tag = SkillTags.CUSTOM

class UpkeepAOESkillGain(SkillComponent):
    nid = 'upkeep_aoe_skill_gain'
    desc = "Grants the designated skill at upkeep to units in an AoE around owner. Can optionally affect user as well."
    tag = SkillTags.CUSTOM
    author = 'Lord_Tweed'

    expose = (ComponentType.NewMultipleOptions)
    options = {
        "skill": ComponentType.Skill,
        "range": ComponentType.Int,
        "affect_self": ComponentType.Bool,
        "target": (ComponentType.MultipleChoice, ('ally', 'enemy', 'any')),
    }
    
    def __init__(self, value=None):
        self.value = {
            "skill": 'Canto',
            "range": 1,
            "affect_self": False,
            "target": 'ally',
        }
        if value:
            self.value.update(value)

    def on_upkeep(self, actions, playback, unit):
        # Spatial effects require an on-map origin. A unit may have been
        # removed by a phase-start event after the upkeep queue was created.
        if unit.position is None:
            return
        r = set(range(self.value.get('range') + 1))
        locations = game.target_system.get_shell({unit.position}, r, game.board.bounds)
        for loc in locations:
            target2 = game.board.get_unit(loc)
            if target2 and target2 is not unit and self.value.get('target') in ['enemy','any'] and skill_system.check_enemy(unit, target2):
                action.do(action.AddSkill(target2, self.value.get('skill'), unit))
            elif target2 and target2 is not unit and self.value.get('target') in ['ally','any'] and skill_system.check_ally(unit, target2):
                action.do(action.AddSkill(target2, self.value.get('skill'), unit))

        if self.value.get('affect_self'):
            action.do(action.AddSkill(unit, self.value.get('skill'), unit))

class EndstepAOESkillGain(SkillComponent):
    nid = 'endstep_aoe_skill_gain'
    desc = "Grants the designated skill at endstep to units in an AoE around owner. Can optionally affect user as well."
    tag = SkillTags.CUSTOM
    author = 'Lord_Tweed'

    expose = (ComponentType.NewMultipleOptions)
    options = {
        "skill": ComponentType.Skill,
        "range": ComponentType.Int,
        "affect_self": ComponentType.Bool,
        "target": (ComponentType.MultipleChoice, ('ally', 'enemy', 'any')),
    }
    
    def __init__(self, value=None):
        self.value = {
            "skill": 'Canto',
            "range": 1,
            "affect_self": False,
            "target": 'ally',
        }
        if value:
            self.value.update(value)

    def on_endstep(self, actions, playback, unit):
        if unit.position is None:
            return
        r = set(range(self.value.get('range') + 1))
        locations = game.target_system.get_shell({unit.position}, r, game.board.bounds)
        for loc in locations:
            target2 = game.board.get_unit(loc)
            if target2 and target2 is not unit and self.value.get('target') in ['enemy','any'] and skill_system.check_enemy(unit, target2):
                action.do(action.AddSkill(target2, self.value.get('skill'), unit))
            elif target2 and target2 is not unit and self.value.get('target') in ['ally','any'] and skill_system.check_ally(unit, target2):
                action.do(action.AddSkill(target2, self.value.get('skill'), unit))

        if self.value.get('affect_self'):
            action.do(action.AddSkill(unit, self.value.get('skill'), unit))

class FatalDamage(SkillComponent):
    nid = 'fatal_damage'
    desc = "Skill can deal fatal damage. Use on statuses such as Poison, Bleed, Infection, etc."
    tag = SkillTags.CUSTOM

class FatalBlock(SkillComponent):
    nid = 'fatal_block'
    desc = "This skill should prevent death from fatal damage statuses. Use on statuses such as Legend, Hope for Humanity, etc."
    tag = SkillTags.CUSTOM
    
class TrueMiracleEvent(SkillComponent):
    nid = 'True_Miracle_Event'
    desc = "Unit cannot go beneath 1 HP. An event will occur once this effect triggers."
    tag = SkillTags.COMBAT2
    
    expose = ComponentType.Event
    value = ''

    def after_take_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        did_something = False
        for act in reversed(actions):
            if isinstance(act, action.ChangeHP) and -act.num >= act.old_hp and act.unit == unit:
                act.num = -act.old_hp + 1
                did_something = True
                playback.append(pb.DefenseHitProc(unit, self.skill))

        if did_something:
            actions.append(action.TriggerCharge(unit, self.skill))
            game.events.trigger_specific_event(self.value, unit, target, unit.position, {'item': item, 'item2': item2, 'mode': mode})

class GiveStatusesOnTakeHit(SkillComponent):
    nid = 'give_statuses_on_take_hit'
    desc = "When receiving an attack, give statuses to the attacker"
    tag = SkillTags.CUSTOM
    author = 'Lord_Tweed'
    
    expose = (ComponentType.List, ComponentType.Skill)

    def after_take_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        if target:
            for skill_nid in self.value:
                actions.append(action.AddSkill(target, skill_nid, unit))
            actions.append(action.TriggerCharge(unit, self.skill))

class GainSkillAfterCombatOnTakeHit(SkillComponent):
    nid = 'gain_skill_after_combat_on_take_hit'
    desc = "Gain a skill after combat if an enemy hits you"
    tag = SkillTags.CUSTOM

    expose = ComponentType.Skill

    def end_combat(self, playback, unit, item, target, item2, mode):
        mark_playbacks = [p for p in playback if p.nid in (
            'mark_hit', 'mark_crit')]
        if target and any(p.defender is unit for p in mark_playbacks):  # Unit is overall defender
            action.do(action.AddSkill(unit, self.value, unit))
            action.do(action.TriggerCharge(unit, self.skill))

class KillChargeIncrease(SkillComponent):
    nid = 'kill_charge_increase'
    desc = "Increases charge of skill when slaying a foe"
    tag = SkillTags.CHARGE

    expose = ComponentType.Int
    value = 1

    ignore_conditional = True

    def end_combat(self, playback, unit, item, target, item2, mode):
        if not self.skill.data.get('active') and target and target.get_hp() <= 0:
            new_value = self.skill.data['charge'] + self.value
            new_value = min(new_value, self.skill.data['total_charge'])
            action.do(action.SetObjData(self.skill, 'charge', new_value))

class NullSweep(SkillComponent):
    nid = 'null_sweep'
    desc = "Checked by evals to determine whether sweeping effects should occur."
    tag = SkillTags.CUSTOM

class CombatArtAll(SkillComponent):
    nid = 'combat_art_all'
    desc = "Combat Art also triggers charge for the designated skill for all allies."
    tag = SkillTags.CUSTOM

    expose = ComponentType.Skill

    def end_combat_unconditional(self, playback, unit, item, target, item2, mode):
        if self.skill.data.get('active'):
            for ally in game.get_all_units_in_party():
                if ally.nid != unit.nid and self.value in [s.nid for s in ally.skills]:
                    action.do(action.TriggerCharge(ally, ally.get_skill(self.value)))

class GrowthChangeExpression(SkillComponent):
    nid = 'growth_change_expression'
    desc = "Gives growth rate % bonuses dynamically"
    tag = SkillTags.COMBAT

    expose = (ComponentType.StringDict, ComponentType.Stat)
    value = []

    def growth_change(self, unit):
        from app.engine import evaluate
        try:
            return {stat[0]: int(evaluate.evaluate(stat[1], unit)) for stat in self.value}
        except Exception as e:
            logging.error("Couldn't evaluate conditional for skill %s: [%s], %s", self.skill.nid, str(self.value), e)
        return {stat[0]: 0 for stat in self.value}
        
class ShittyLifelink(SkillComponent):
    nid = 'shitty_lifelink'
    desc = "Heals user %% of damage dealt ignoring current HP"
    tag = SkillTags.COMBAT2

    expose = ComponentType.Float
    value = 0.5

    def after_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        total_damage_dealt = 0
        playbacks = [p for p in playback if p.nid in (
            'damage_hit', 'damage_crit') and p.attacker == unit]
        for p in playbacks:
            total_damage_dealt += p.damage

        damage = utils.clamp(total_damage_dealt, 0, total_damage_dealt)
        true_damage = int(damage * self.value)
        actions.append(action.ChangeHP(unit, true_damage))

        playback.append(pb.HealHit(unit, item, unit, true_damage, true_damage))

        actions.append(action.TriggerCharge(unit, self.skill))
        
class AbilityDrainParentCharge(SkillComponent):
    nid = 'ability_parent'
    desc = "Give unit an item as an extra ability via a drain charge aura"
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
        if item and item.nid == self.value and self.skill.parent_skill and self.skill.parent_skill.owner_nid:
            action.do(action.TriggerCharge(game.get_unit(self.skill.parent_skill.owner_nid), self.skill.parent_skill))
        
class Shit(SkillComponent):
    nid = 'shit'
    desc = "Shit skill, bruv."
    tag = SkillTags.ATTRIBUTE
    
class BlueMagic(SkillComponent):
    nid = 'blue'
    desc = "Used to track Blue Magic skills"
    tag = SkillTags.ATTRIBUTE

class EvalLifelink(SkillComponent):
    nid = 'eval_lifelink'
    desc = "Heals user on hit based on Eval."
    tag = SkillTags.CUSTOM

    expose = ComponentType.String

    def after_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        total_damage_dealt = 0
        playbacks = [p for p in playback if p.nid in (
            'damage_hit', 'damage_crit') and p.attacker == unit]
        for p in playbacks:
            total_damage_dealt += 1

        from app.engine import evaluate
        try:
            hp_change = int(evaluate.evaluate(self.value, unit, target, unit.position, {'item': item, 'item2': item2, 'mode': mode}))
        except:
            logging.error("Couldn't evaluate %s conditional" % self.value)
            hp_change = 0
        damage = hp_change * total_damage_dealt
        actions.append(action.ChangeHP(unit, damage))

        playback.append(pb.HealHit(unit, item, unit, damage, damage))

        actions.append(action.TriggerCharge(unit, self.skill))

class HasAffinities(SkillComponent):
    nid = 'has_affinities'
    desc = 'Skill grants the following affinities to the unit'
    tag = SkillTags.ATTRIBUTE

    expose = (ComponentType.List, ComponentType.Affinity)

class Subskills(SkillComponent):
    nid = 'subskills'
    desc = "This skill is not copy safe, but has underlying associated skills that should be removed with this skill."
    tag = SkillTags.CUSTOM
    
    expose = (ComponentType.List, ComponentType.Skill)
    
class CannotUseMagicItemsEval(SkillComponent):
    nid = 'cannot_use_magic_items_eval'
    desc = "Unit cannot use or equip magic items"
    tag = SkillTags.BASE

    def available(self, unit, item) -> bool:
        return not item_funcs.is_magic(unit, item) and not (item.eval_magic and item.eval_magic.active(unit, item)) and not (item.eval_dragon and item.eval_dragon.active(unit, item)) and not item.eval_dragon_magic
        
class AllyLifelinkTarget(SkillComponent):
    nid = 'ally_lifelink_target'
    desc = "Heals allies adjacent to target %% of damage dealt"
    tag = SkillTags.COMBAT2

    expose = ComponentType.Float
    value = 0.5

    def after_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        total_damage_dealt = 0
        playbacks = [p for p in playback if p.nid in (
            'damage_hit', 'damage_crit') and p.attacker == unit]
        for p in playbacks:
            total_damage_dealt += p.true_damage

        damage = utils.clamp(total_damage_dealt, 0, target.get_hp())
        true_damage = int(damage * self.value)
        if true_damage > 0 and target.position:
            adj_positions = game.target_system.get_adjacent_positions(target.position)
            did_happen = False
            for adj_pos in adj_positions:
                other = game.board.get_unit(adj_pos)
                if other and skill_system.check_ally(other, unit) and unit.nid != other.nid:
                    actions.append(action.ChangeHP(other, true_damage))
                    playback.append(pb.HealHit(
                        unit, item, other, true_damage, true_damage))
                    did_happen = True

            if did_happen:
                actions.append(action.TriggerCharge(unit, self.skill))

class StartAndEndEventInitiate(SkillComponent):
    nid = 'start_and_end_event_initiate'
    desc = 'Calls events before and after combat initated by user'
    tag = SkillTags.ADVANCED

    expose = (ComponentType.NewMultipleOptions)
    options = {
        "start_event": ComponentType.Event,
        "end_event": ComponentType.Event,
    }
    
    def __init__(self, value=None):
        self.value = {
            "start_event": '',
            "end_event": '',
        }
        if value:
            self.value.update(value)

    def start_combat(self, playback, unit, item, target, item2, mode):
        if mode == 'attack':
            game.events.trigger_specific_event(self.value.get('start_event'), unit, target, unit.position, {'item': item, 'item2': item2, 'mode': mode})
    
    def end_combat(self, playback, unit: UnitObject, item, target: UnitObject, item2, mode):
        if mode == 'attack':
            game.events.trigger_specific_event(self.value.get('end_event'), unit, target, unit.position, {'item': item, 'item2': item2, 'mode': mode})

class BetterPostCombatDamage(SkillComponent):
    nid = 'better_post_combat_damage'
    desc = "Target takes non-lethal flat damage after combat"
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int
    value = 0
    author = 'Lord_Tweed'

    def end_combat(self, playback, unit, item, target, item2, mode):
        if target and skill_system.check_enemy(unit, target) and not target.get_hp() <= 0:
            end_health = target.get_hp() - self.value
            action.do(action.SetHP(target, max(1, end_health)))
            action.do(action.TriggerCharge(unit, self.skill))


class SurvivingInitiatorPostCombatDamage(BetterPostCombatDamage):
    nid = 'surviving_initiator_post_combat_damage'
    desc = ('Target takes non-lethal flat damage after combat only when the '
            'initiator survives.')
    tag = SkillTags.CUSTOM

    def end_combat(self, playback, unit, item, target, item2, mode):
        if mode != 'attack' or unit.get_hp() <= 0:
            return
        super().end_combat(playback, unit, item, target, item2, mode)

class EvalPostCombatDamage(SkillComponent):
    nid = 'eval_post_combat_damage'
    desc = "Target takes non-lethal flat damage after combat, based on eval."
    tag = SkillTags.CUSTOM

    expose = ComponentType.String
    author = 'Lord_Tweed'

    def end_combat(self, playback, unit, item, target, item2, mode):
        if target and skill_system.check_enemy(unit, target) and not target.get_hp() <= 0:
            from app.engine import evaluate
            try:
                hp_change = int(evaluate.evaluate(self.value, unit, target, unit.position, {'item': item, 'item2': item2, 'mode': mode}))
            except:
                logging.error("Couldn't evaluate %s conditional" % self.value)
                hp_change = 0
            end_health = target.get_hp() - hp_change
            action.do(action.SetHP(target, max(1, end_health)))
            action.do(action.TriggerCharge(unit, self.skill))

class CombatChargeIncreaseBetter(SkillComponent):
    nid = 'combat_charge_increase_better'
    desc = "Increases charge of skill each combat, but actually works on miss. Does not work if unit and target are allied."
    tag = SkillTags.CHARGE

    expose = ComponentType.Int
    value = 1

    ignore_conditional = True

    def end_combat(self, playback, unit, item, target, item2, mode):
        if unit and target and not self.skill.data.get('active') and skill_system.check_enemy(unit, target):
            new_value = self.skill.data['charge'] + self.value
            new_value = min(new_value, self.skill.data['total_charge'])
            action.do(action.SetObjData(self.skill, 'charge', new_value))

class GiveStatusesAfterCombat(SkillComponent):
    nid = 'give_statuses_after_combat'
    desc = "Gives multiple statuses to target enemy after combat"
    tag = SkillTags.CUSTOM

    expose = (ComponentType.List, ComponentType.Skill)

    def end_combat(self, playback, unit, item, target, item2, mode):
        from app.engine import skill_system
        if target and skill_system.check_enemy(unit, target):
            for status in self.value:
                action.do(action.AddSkill(target, status, unit))
            action.do(action.TriggerCharge(unit, self.skill))

class DrainChargeAll(SkillComponent):
    nid = 'drain_charge_all'
    desc = "Skill will have a number of charges that are drained by 1 when activated. if other allues have this skill, they will also lose charges."
    tag = SkillTags.CHARGE

    expose = ComponentType.Int
    value = 1

    ignore_conditional = True

    def init(self, skill):
        self.skill.data['charge'] = self.value
        self.skill.data['total_charge'] = self.value

    def condition(self, unit, item):
        return self.skill.data['charge'] > 0

    def on_end_chapter(self, unit, skill):
        self.skill.data['charge'] = self.skill.data['total_charge']

    def trigger_charge(self, unit, skill):
        new_value = self.skill.data['charge'] - 1
        action.do(action.SetObjData(self.skill, 'charge', new_value))
        combined_parties = game.get_all_units_in_party() + game.get_all_units_in_party('Flex')
        for ally in combined_parties:
            if ally.nid != unit.nid and self.skill.nid in [s.nid for s in ally.skills]:
                action.do(action.SetObjData(ally.get_skill(self.skill.nid), 'charge', new_value))

    def text(self) -> str:
        return str(self.skill.data['charge'])

    def cooldown(self):
        return self.skill.data['charge'] / self.skill.data['total_charge']

class ArmsthriftAlways(SkillComponent):
    nid = 'armsthrift_always'
    desc = 'Restores a use regardless of circumstance'
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int
    value = 1

    def _post_combat(self, unit, item):
        if item_system.unrepairable(unit, item):
            return  # Don't restore for unrepairable items
        # Handles Uses
        if item.uses:
            curr_uses = item.data.get('uses')
            max_uses = item.data.get('starting_uses')
            action.do(action.SetObjData(item, 'uses', min(curr_uses + self.value, max_uses)))
        # Handles Chapter Uses
        #if item.data.get('c_uses', None) and item.data.get('starting_c_uses', None):
        if item.c_uses:
            curr_uses = item.data.get('c_uses')
            max_uses = item.data.get('starting_c_uses')
            action.do(action.SetObjData(item, 'c_uses', min(curr_uses + self.value, max_uses)))

    def post_combat(self, playback, unit, item, target, item2, mode):
        # handles one loss per combat + armsthift interaction
        if not item:
            return
        if item.parent_item:
            self.post_combat(
                playback, unit, item.parent_item, target, item2, mode)
        if item.uses_options:
            self._post_combat(unit, item)

class SavageStatuses(SkillComponent):
    nid = 'savage_statuses'
    desc = 'Inflicts the given statuses to enemies within the given number of spaces from target.'
    tag = SkillTags.CUSTOM
    author = 'Lord_Tweed'

    expose = (ComponentType.NewMultipleOptions)
    options = {
        "statuses": (ComponentType.List, ComponentType.Skill),
        "range": ComponentType.Int,
    }
    
    def __init__(self, value=None):
        self.value = {
            "statuses": [],
            "range": 1,
        }
        if value:
            self.value.update(value)

    def end_combat(self, playback, unit, item, target, item2, mode):
        if target and skill_system.check_enemy(unit, target):
            r = set(range(self.value.get('range') + 1))
            locations = game.target_system.get_shell({target.position}, r, game.board.bounds)
            for loc in locations:
                target2 = game.board.get_unit(loc)
                if target2 and target2 is not target and skill_system.check_enemy(unit, target2):
                    for status in self.value.get('statuses'):
                        action.do(action.AddSkill(target2, status, unit))

class GainTerrain(SkillComponent):
    nid = 'gain_terrain'
    desc = "Unit will be affected by terrain"
    tag = SkillTags.MOVEMENT

    def ignore_terrain(self, unit):
        return False

    def ignore_region_status(self, unit):
        return False

class HealAfterFollowUp(SkillComponent):
    nid = 'heal_after_follow_up'
    desc = "Heal HP immediately after an enemy damages you, only if attack was a follow-up"
    tag = SkillTags.COMBAT

    expose = ComponentType.Int
    value = 5

    def after_take_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        for act in actions:
            if isinstance(act, action.ChangeHP) and act.num < 0 and act.unit == unit and attack_info[0] > 0 and unit.get_hp() > (-1 * act.num):
                playbacks = [p for p in playback if p.nid in ('damage_hit', 'damage_crit') and p.attacker == target]
                actions.append(action.ChangeHP(unit, self.value))
                playback.append(pb.HealHit(target, item2, unit, self.value, self.value))
                actions.append(action.TriggerCharge(unit, self.skill))
                return

class DynamicResistMultiplier(SkillComponent):
    nid = 'dynamic_resist_multiplier'
    desc = "Multiplies damage taken by a fraction, calculated dynamically"
    tag = SkillTags.COMBAT

    expose = ComponentType.String

    def resist_multiplier(self, unit, item, target, item2, mode, attack_info, base_value):
        from app.engine import evaluate
        try:
            local_args = {'item': item, 'item2': item2, 'mode': mode, 'skill': self.skill, 'attack_info': attack_info, 'base_value': base_value}
            return float(evaluate.evaluate(self.value, unit, target, unit.position, local_args))
        except Exception:
            print("Couldn't evaluate %s conditional" % self.value)
            return 1

class AlternateMagicDamageFormula(SkillComponent):
    nid = 'alternate_magic_damage_formula'
    desc = 'Unit uses a different magic_damage formula'
    tag = SkillTags.FORMULA

    expose = ComponentType.Equation
    value = 'MAGIC_DAMAGE'

    def damage_formula(self, unit):
        return self.value

class EvalCritDamage(SkillComponent):
    nid = 'eval_crit_additional'
    desc = "Gives +X additional damage on crit solved using evaluate"
    tag = SkillTags.COMBAT

    expose = ComponentType.String

    def modify_crit_addition(self, unit, item):
        from app.engine import evaluate
        try:
            return int(evaluate.evaluate(self.value, unit, local_args={'item': item}))
        except Exception as e:
            logging.error("Couldn't evaluate %s conditional (%s)", self.value, e)
        return 0

class GainSkillAfterActiveNotKill(SkillComponent):
    nid = 'gain_skill_after_active_not_kill'
    desc = "Gives a skill after failing to kill on personal phase"
    tag = SkillTags.COMBAT2

    expose = ComponentType.Skill

    def end_combat(self, playback, unit, item, target, item2, mode):
        mark_playbacks = [p for p in playback if p.nid in (
            'mark_miss', 'mark_hit', 'mark_crit')]
        if target and target.get_hp() > 0 and any(p.main_attacker is unit for p in mark_playbacks):  # Unit is overall attacker
            action.do(action.AddSkill(unit, self.value))
            action.do(action.TriggerCharge(unit, self.skill))

class PostCombatHealing(SkillComponent):
    nid = 'post_combat_healing'
    desc = "Unit heals a flat amount of HP after battle with an enemy"
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int
    value = 1
    author = 'Lord_Tweed'

    def end_combat(self, playback, unit, item, target, item2, mode):
        if target and skill_system.check_enemy(unit, target) and unit.get_hp() > 0:
            end_health = unit.get_hp() + self.value
            action.do(action.SetHP(unit, end_health))
            action.do(action.TriggerCharge(unit, self.skill))
class StatusOnCrit(SkillComponent):
    nid = 'status_on_crit'
    desc = "Gain skill during criticals"
    tag = SkillTags.CUSTOM

    expose = ComponentType.Skill
    value = None

    _did_action = False

    def before_crit(self, actions, playback, attacker, item, defender, item2, mode, attack_info):
        act = action.AddSkill(attacker, self.value)
        action.do(act)
        playback.append(pb.AttackProc(attacker, act.skill_obj))
        self._did_action = True

    def end_sub_combat(self, actions, playback, unit, item, target, item2, mode, attack_info):
        if self._did_action:
            action.do(action.RemoveSkill(unit, self.value))
            self._did_action = Falseclass GiveStatusBeforeCombat(SkillComponent):
    nid = 'give_status_before_combat'
    desc = "Gives a status to target enemy before combat"
    tag = SkillTags.COMBAT2

    expose = ComponentType.Skill
    author = 'Beccarte'
    
    def start_combat(self, playback, unit, item, target, item2, mode):
        if target and skill_system.check_enemy(unit, target):
            action.do(action.AddSkill(target, self.value, unit))
            action.do(action.TriggerCharge(unit, self.skill))            self._did_action = Trueclass GiveStatusBeforePreCombat(SkillComponent):
    nid = 'give_status_before_pre_combat'
    desc = "Gives a status to target enemy before pre combat"
    tag = SkillTags.COMBAT2

    expose = ComponentType.Skill
    author = 'Beccarte'
    
    def pre_combat(self, playback, unit, item, target, item2, mode):
        if target and skill_system.check_enemy(unit, target):
            action.do(action.AddSkill(target, self.value, unit))
            action.do(action.TriggerCharge(unit, self.skill))
            self._did_action = Trueclass NegatedBySkills(SkillComponent):
    nid = 'negated_by_skills'
    desc = "Skill does not work against a holder of other skill(s)"
    tag = SkillTags.CUSTOM

    expose = (ComponentType.List, ComponentType.Skill)
    value = []

    ignore_conditional = True
    _condition = True

    def pre_combat(self, playback, unit, item, target, item2, mode):
        all_negates = set(self.value)
        if target:
            for skill in target.skills:
                if skill.nid in all_negates:
                    self._condition = False
                    return
        self._condition = True

    def post_combat(self, playback, unit, item, target, item2, mode):
        self._condition = True

    def condition(self, unit, item):
        return self._condition

    def test_on(self, playback, unit, item, target, item2, mode):
        self.pre_combat(playback, unit, item, target, item2, mode)

    def test_off(self, playback, unit, item, target, item2, mode):
        self._condition = Trueclass NoStatDebuffs(SkillComponent):
    nid = 'no_stat_debuffs'
    desc = "Unit's stats cannot be lowered by skills."
    tag = SkillTags.COMBAT2

    author = 'Beccarte'

    def no_stat_debuffs(self, unit):
        return True
class EnemyPass(SkillComponent):
    nid = 'enemy_pass'
    desc = "Enemies can move through this unit"
    tag = SkillTags.MOVEMENT

    def enemy_pass_through(self, unit):
        return True
class CharacterSkillSlot(SkillComponent):
    nid = 'char_skill'
    desc = "Char Skill Slot"
    tag = SkillTags.ATTRIBUTE


# Helper: when two skills sharing the same slot category land on a unit, keep the higher-priority one and shelve the loser into the unit's LearnedSkills field so it can be re-equipped from the Skill Swap menu later.
_SLOT_NIDS = ('special_skill', 'slota_skill', 'slotb_skill', 'slotc_skill', 'extra_skill')


def _skill_priority(skill):
    for c in skill.components:
        if c.nid == 'priority':
            try:
                return int(c.value)
            except (TypeError, ValueError):
                return 0
    return 0


def _resolve_slot_conflict(slot_nid, existing_skill, unit, other_skill):
    if other_skill is existing_skill:
        return
    if not any(c.nid == slot_nid for c in other_skill.components):
        return
    if existing_skill not in unit.skills or other_skill not in unit.skills:
        return
    if _skill_priority(other_skill) > _skill_priority(existing_skill):
        loser = existing_skill
    else:
        loser = other_skill
    if loser not in unit.skills:
        return
    learned = list(unit.get_field('LearnedSkills') or [])
    if loser.nid and loser.nid not in learned:
        learned.append(loser.nid)
        action.do(action.ChangeField(unit, 'LearnedSkills', learned))
    action.do(action.RemoveSkill(unit, loser))


class ClassSkillSlot(SkillComponent):
    nid = 'class_skill2'
    desc = "Class Skill Slot"
    tag = SkillTags.ATTRIBUTE


class SpecialSkillSlot(SkillComponent):
    nid = 'special_skill'
    desc = "Special Skill Slot"
    tag = SkillTags.ATTRIBUTE

    def after_gain_skill(self, unit, other_skill):
        _resolve_slot_conflict(self.nid, self.skill, unit, other_skill)


class SlotASkillSlot(SkillComponent):
    nid = 'slota_skill'
    desc = "SlotA Skill Slot"
    tag = SkillTags.ATTRIBUTE

    def after_gain_skill(self, unit, other_skill):
        _resolve_slot_conflict(self.nid, self.skill, unit, other_skill)


class SlotBSkillSlot(SkillComponent):
    nid = 'slotb_skill'
    desc = "SlotB Skill Slot"
    tag = SkillTags.ATTRIBUTE

    def after_gain_skill(self, unit, other_skill):
        _resolve_slot_conflict(self.nid, self.skill, unit, other_skill)


class SlotCSkillSlot(SkillComponent):
    nid = 'slotc_skill'
    desc = "SlotC Skill Slot"
    tag = SkillTags.ATTRIBUTE

    def after_gain_skill(self, unit, other_skill):
        _resolve_slot_conflict(self.nid, self.skill, unit, other_skill)


class ExtraSkillSlot(SkillComponent):
    nid = 'extra_skill'
    desc = "Extra Skill Slot"
    tag = SkillTags.ATTRIBUTE

    def after_gain_skill(self, unit, other_skill):
        _resolve_slot_conflict(self.nid, self.skill, unit, other_skill)


# Weapon skill markers: skills granted by an equipped weapon. They share the same five categories as regular slot skills but always override the regular skill in that slot while the weapon is equipped. They have no priority and do not conflict with each other since a unit only equips one weapon at a time.
class WeaponSpecialSkillSlot(SkillComponent):
    nid = 'weapon_special_skill'
    desc = "Weapon-granted skill occupying the Special slot."
    tag = SkillTags.ATTRIBUTE


class WeaponSlotASkillSlot(SkillComponent):
    nid = 'weapon_slota_skill'
    desc = "Weapon-granted skill occupying SlotA."
    tag = SkillTags.ATTRIBUTE


class WeaponSlotBSkillSlot(SkillComponent):
    nid = 'weapon_slotb_skill'
    desc = "Weapon-granted skill occupying SlotB."
    tag = SkillTags.ATTRIBUTE


class WeaponSlotCSkillSlot(SkillComponent):
    nid = 'weapon_slotc_skill'
    desc = "Weapon-granted skill occupying SlotC."
    tag = SkillTags.ATTRIBUTE


class WeaponExtraSkillSlot(SkillComponent):
    nid = 'weapon_extra_skill'
    desc = "Weapon-granted skill occupying the Extra slot."
    tag = SkillTags.ATTRIBUTE


class Priority (SkillComponent):
    nid = 'priority'
    desc = "Priority for skill display."
    tag = SkillTags.ATTRIBUTE

    expose = ComponentType.Int
    value = 0
    def int(self) -> int:
        return int(self.value)

class LupinStealIcon(SkillComponent):
    nid = 'lupin_steal_icon'
    desc = "Displays icon above units with stealable items"
    tag = SkillTags.AESTHETIC

    def target_icon(self, hovered_unit, icon_unit) -> str:
        if skill_system.check_enemy(hovered_unit, icon_unit):
            attack = equations.parser.steal_atk(hovered_unit)
            defense = equations.parser.steal_def(icon_unit)
            if attack >= defense:
                for def_item in icon_unit.items:
                    if self._can_steal(hovered_unit, icon_unit, def_item):
                        return 'steal'
        return None

    def _can_steal(self, unit, defender, def_item) -> bool:
        if item_system.unstealable(defender, def_item):
            return False
        if item_funcs.inventory_full(unit, def_item):
            return False
        return Trueclass GiveAllyStatusAfterCombatIfFullHP(SkillComponent):
    nid = 'give_ally_status_after_combat_if_full_hp'
    desc = "Gives a status to target ally after combat if target full hp"
    tag = SkillTags.COMBAT2

    expose = ComponentType.Skill

    def end_combat(self, playback, unit, item, target, item2, mode):
        from app.engine import skill_system
        if target and skill_system.check_ally(unit, target) and target.get_hp() == target.get_max_hp():
            action.do(action.AddSkill(target, self.value, unit))
            action.do(action.TriggerCharge(unit, self.skill))class EventOnDeath(SkillComponent):
    nid = 'event_on_death'
    desc = "calls event after death"
    tag = SkillTags.ADVANCED
    expose = ComponentType.Event
    value = ''
    def on_death(self, unit):
        game.events.trigger_specific_event(self.value, unit, unit.position)class GiveStatusesAfterHit(SkillComponent):
    nid = 'give_statuses_after_hit'
    desc = "Gives statuses to target after hitting them"
    tag = SkillTags.COMBAT2

    expose = (ComponentType.List, ComponentType.Skill)

    def after_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        mark_playbacks = [p for p in playback if p.nid in (
            'mark_hit', 'mark_crit')]

        if target and any(p.attacker == unit for p in mark_playbacks):
            from app.engine import skill_system
            if target and skill_system.check_enemy(unit, target):
                for status in self.value:
                    action.do(action.AddSkill(target, status, unit))
                action.do(action.TriggerCharge(unit, self.skill))
class RescueBonus(SkillComponent):
    nid = 'rescue_bonus'
    desc = "Grants a child skill to lead units while in rescue."
    tag = SkillTags.STATUS

    expose = ComponentType.Skill

    def on_rescue(self, unit, leader):
        action.do(action.AddSkill(leader, self.value, source=unit.nid, source_type=SourceType.TRAVELER))

    def on_give(self, unit, leader):
        if self.value in [skill.nid for skill in leader.skills]:
            action.do(action.RemoveSkill(leader, self.value, source=unit.nid, source_type=SourceType.TRAVELER))class ResistFirstStrike(SkillComponent):
    nid = 'resist_first_strike'
    desc = "Multiplies damage taken by a fraction at the first strike"
    tag = SkillTags.COMBAT

    expose = ComponentType.Float
    value = 0.5

    def resist_multiplier(self, unit, item, target, item2, mode, attack_info, base_value):
        return self.value if attack_info[0] == 0 else 1class NegateCannotDouble(SkillComponent):
    nid = 'NEGATE_cannot_double'
    desc = "Negate Unit cannot double"
    tag = SkillTags.COMBAT2

    def negate_no_double(self, unit):
        return True
class NegateCannotBeCountered(SkillComponent):
    nid = 'negate_cannot_be_countered'
    desc = "Negate cannot be countered"
    tag = SkillTags.COMBAT2

    def negate_cannot_be_countered(self, unit):
        return Trueclass EnemyCannotDynamicAttacks(SkillComponent):
    nid = 'no_dynamic_attacks'
    desc = "Target can't do dynamic attacks"
    tag = SkillTags.COMBAT2

    def no_dynamic_attacks(self, unit):
        return Trueclass NegateNoDynamicAttacks(SkillComponent):
    nid = 'negate_no_dynamic_attacks'
    desc = "Negate cannot dynamic attacks"
    tag = SkillTags.COMBAT2

    def negate_no_dynamic_attacks(self, unit):
        return Trueclass EnemyCannotDouble(SkillComponent):
    nid = 'Target_cannot_double'
    desc = "Target cannot double"
    tag = SkillTags.COMBAT2

    def target_no_double(self, unit):
        return Trueclass ReduceResistMultiplier(SkillComponent):
    nid = 'reduce_resist_multiplier'
    desc = "Reduce Multiplies damage taken by a fraction"
    tag = SkillTags.COMBAT

    expose = ComponentType.Float
    value = 0.5

    def reduce_resist_multiplier(self, unit, item, target, item2, mode, attack_info, base_value):
        return self.value

class MarkerWarningIcon(SkillComponent):
    nid = 'maker_warning_icon'
    desc = "Displays warning icons above units"
    tag = SkillTags.AESTHETIC

    def target_icon(self, hovered_unit, icon_unit) -> str:
        return 'warning'

class MariSpellContainer(SkillComponent):
    nid = 'mari_spell_container'
    desc = ("Treats equipped Mari spells (items whose nid is in the MariSpell catalog) as a separate "
            "container: they never consume the unit's regular inventory slots. The unit's effective "
            "item capacity is increased by the number of spell items currently carried.")
    tag = SkillTags.CUSTOM

    def num_items_offset(self, unit) -> int:
        try:
            catalog = DB.raw_data.get('MariSpell')
        except Exception:
            catalog = None
        if not catalog:
            return 0
        spell_nids = {row.nid for row in catalog}
        count = 0
        for item in unit.items:
            if item.nid in spell_nids and not item_system.is_accessory(unit, item):
                count += 1
        return count

class ExactLethalDamage(SkillComponent):
    nid = 'exact_lethal_damage'
    desc = "Cộng/giảm damage sao cho tổng sát thương đúng bằng HP hiện tại của mục tiêu (1 hit K.O vừa đủ, không thừa damage)"
    tag = SkillTags.COMBAT

    def raw_damage(self, unit, item, target, item2, mode, attack_info, base_value):
        from app.engine import skill_system
        # Chỉ áp dụng khi người sở hữu là bên tấn công và mục tiêu là kẻ địch còn sống
        if mode != 'attack' or target is None:
            return 0
        if not skill_system.check_enemy(unit, target):
            return 0
        current_hp = target.get_hp()
        if current_hp <= 0:
            return 0
        # base_value là sát thương cuối cùng dự kiến gây ra (sau giáp, crit, multiplier).
        # Trả về phần chênh lệch để tổng damage = đúng HP hiện tại.
        return current_hp - base_value
