from __future__ import annotations

from app.data.database.components import ComponentType
from app.data.database.database import DB
from app.data.database.skill_components import SkillComponent, SkillTags
from app.engine import (action, banner, combat_calcs, engine, equations,
                        image_mods, item_funcs, item_system, skill_system,
                        target_system)
from app.engine.game_state import game
from app.engine import ranked_upkeep
from app.engine.objects.unit import UnitObject
from app.utilities import utils, static_random
from app.engine.combat import playback as pb
from app.engine.combat import utils as combat_utils
from app.utilities.enums import Strikefrom app.engine.source_type import SourceType
import logging

class DoNothing(SkillComponent):
    nid = 'do_nothing'
    desc = 'does nothing'
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int
    value = 1

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

class GoldenUpkeepEvent(SkillComponent):
    nid = 'golden_upkeep_event'
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
        if skill_system.block_death_prevention(unit) or \
                (target and skill_system.neutralize_foe_death_prevention(target)):
            return
        if unit.get_hp() <= 0:
            action.do(action.SetHP(unit, 1 if skill_system.block_hp_recovery(unit) else unit.get_max_hp()))
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


class HealOnStrikeKill(SkillComponent):
    nid = 'heal_on_strike_kill'
    desc = 'Recovers HP only when this strike defeats the foe.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int
    value = 0

    def after_strike(self, actions, playback, unit, item, target, item2, mode,
                     attack_info, strike):
        if strike == Strike.MISS or not target or target.get_hp() <= 0:
            return
        damage = combat_utils.get_current_strike_true_damage(playback, unit, target)
        if damage < target.get_hp():
            return
        heal = action.ChangeHP(unit, self.value)
        if heal.num > 0:
            actions.append(heal)
            playback.append(pb.HealHit(unit, item, unit, heal.num, heal.num))

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

class ExperienceFamilyProvider(SkillComponent):
    nid = 'experience_family_provider'
    desc = 'Provides the strongest matching Experience-family multiplier to an ally.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {
        'scope': (ComponentType.MultipleChoice, ('self', 'team_weapon', 'team_units')),
        'weapon_types': (ComponentType.List, ComponentType.WeaponType),
        'eligible_unit_nids': (ComponentType.List, ComponentType.String),
        'multiplier': ComponentType.Float,
    }

    def __init__(self, value=None):
        self.value = {
            'scope': 'self',
            'weapon_types': [],
            'eligible_unit_nids': [],
            'multiplier': 1.0,
        }
        if value:
            self.value.update(value)

    def experience_family_multiplier(self, unit, target, item):
        scope = self.value['scope']
        if scope == 'self':
            return self.value['multiplier'] if unit is target else 1.0
        if scope == 'team_weapon':
            if item and item_system.weapon_type(target, item) in self.value['weapon_types']:
                return self.value['multiplier']
        elif scope == 'team_units' and target.nid in self.value['eligible_unit_nids']:
            return self.value['multiplier']
        return 1.0


class ValorFamilyProvider(SkillComponent):
    nid = 'valor_family_provider'
    desc = 'Provides the strongest matching Valor-family weapon experience multiplier to an ally.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {
        'scope': (ComponentType.MultipleChoice, ('self', 'team_weapon')),
        'weapon_types': (ComponentType.List, ComponentType.WeaponType),
        'multiplier': ComponentType.Float,
    }

    def __init__(self, value=None):
        self.value = {
            'scope': 'self',
            'weapon_types': [],
            'multiplier': 1.0,
        }
        if value:
            self.value.update(value)

    def valor_family_multiplier(self, provider, recipient, item):
        if self.value['scope'] == 'self':
            return self.value['multiplier'] if provider is recipient else 1.0
        if item and item_system.weapon_type(recipient, item) in self.value['weapon_types']:
            return self.value['multiplier']
        return 1.0

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
        if skill_system.block_death_prevention(unit) or \
                (target and skill_system.neutralize_foe_death_prevention(target)):
            return
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


class GiveStatusAfterCombatUntilNextAction(SkillComponent):
    nid = 'give_status_after_combat_until_next_action'
    desc = 'Gives a status to a target enemy through its next action after combat.'
    tag = SkillTags.COMBAT2

    expose = ComponentType.Skill

    def end_combat(self, playback, unit, item, target, item2, mode):
        if not target or not skill_system.check_enemy(unit, target):
            return

        add_status = action.AddSkill(target, self.value, unit)
        current_combat = game.memory.get('current_combat')
        skip_current_wait = (
            mode == 'defense'
            and current_combat is not None
            and current_combat.finalizes_turn
            and not current_combat.event_combat
        )
        if skip_current_wait and add_status.skill_obj:
            action.do(action.SetObjData(add_status.skill_obj, 'skip_current_wait', True))
        action.do(add_status)
        action.do(action.TriggerCharge(unit, self.skill))


class LostOnNextAction(SkillComponent):
    nid = 'lost_on_next_action'
    desc = 'Removes this skill after the owner completes its next action.'
    tag = SkillTags.TIME

    ignore_conditional = True

    def init(self, skill):
        skill.data.setdefault('skip_current_wait', False)

    def on_wait(self, unit, actively_chosen):
        if self.skill.data.get('skip_current_wait', False):
            action.do(action.SetObjData(self.skill, 'skip_current_wait', False))
        else:
            action.do(action.RemoveSkill(unit, self.skill))

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
            action.do(action.ChangeHP(unit, self.value))
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
            candidates.append((
                _skill_priority(skill), getattr(skill, 'uid', index), value))
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


class ComparisonStatBonus(SkillComponent):
    nid = 'comparison_stat_bonus'
    desc = "Adds to the user's Resistance only when skills compare stats."
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int
    value = 0
    ignore_conditional = True

    def comparison_stat_bonus(self, unit, stat):
        return self.value if stat == 'RES' else 0


class Obstruct(SkillComponent):
    nid = 'obstruct'
    desc = ('Enemies without Pass cannot move through spaces adjacent to the '
            'user while the user meets the HP threshold.')
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
    desc = 'Configures a Feint effect applied after a Rally assist.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {
        'stat': ComponentType.Stat,
        'effect': ComponentType.Skill,
    }
    value = {'stat': 'STR', 'effect': ''}


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


def _is_special_skill(skill):
    return bool(getattr(skill, 'special_skill', None)
                or getattr(skill, 'weapon_special_skill', None))


def _is_special_damage_strike(unit):
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


def _highest_priority_component(component, unit, nid):
    candidates = []
    for index, skill in enumerate(unit.skills):
        for other_component in skill.components:
            if other_component.nid == nid:
                candidates.append((
                    _skill_priority(skill), getattr(skill, 'uid', index),
                    other_component))
    if not candidates:
        return False
    return max(candidates, key=lambda candidate: candidate[:2])[2] is component


def _is_highest_priority_wrath(component, unit):
    return _highest_priority_component(component, unit, 'wrath_special_bonus')


def _is_highest_priority_lull(component, unit):
    return _highest_priority_component(component, unit, 'lull_combat_stats')


class WrathSpecialBonus(SkillComponent):
    nid = 'wrath_special_bonus'
    desc = 'Adds activation rate and flat damage to Special Skill strikes.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {
        'proc_rate_bonus': ComponentType.Int,
        'damage_bonus': ComponentType.Int,
    }

    def __init__(self, value=None):
        self.value = {'proc_rate_bonus': 0, 'damage_bonus': 0}
        if value:
            self.value.update(value)

    def modify_self_proc_rate(self, unit):
        if (not _is_highest_priority_wrath(self, unit)
                or not skill_system.condition(self.skill, unit)):
            return 0
        return int(self.value['proc_rate_bonus'])

    def raw_damage(self, unit, item, target, item2, mode, attack_info,
                   base_value):
        if (not _is_highest_priority_wrath(self, unit)
                or not _is_special_damage_strike(unit)):
            return 0
        return int(self.value['damage_bonus'])


class ClassFollowUpProc(SkillComponent):
    nid = 'class_follow_up_proc'
    desc = ('Rolls once for each pre-existing attack phase to grant a normal '
            'follow-up phase. Proc-created phases never roll again.')
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {
        'chance': ComponentType.Int,
        'skip_first': ComponentType.Bool,
        'initiator_only': ComponentType.Bool,
    }

    def __init__(self, value=None):
        self.value = {'chance': 0, 'skip_first': False, 'initiator_only': False}
        if value:
            self.value.update(value)

    def dynamic_follow_up_proc_count(self, unit, item, target, item2, mode,
                                     attack_info, eligible_phases):
        if self.value['initiator_only'] and mode != 'attack':
            return 0
        phase_count = max(0, int(eligible_phases))
        if self.value['skip_first']:
            phase_count = max(0, phase_count - 1)
        chance = max(0, min(100, int(self.value['chance'])))
        return sum(static_random.get_combat() < chance
                   for _ in range(phase_count))


def _is_normal_sword(unit, item):
    return bool(item and item_system.weapon_type(unit, item) == 'Sword'
                and not getattr(item, 'magic', False)
                and not getattr(item, 'magic_at_range', False))


class ClassMagicSwordMeleeCrit(SkillComponent):
    nid = 'class_magic_sword_melee_crit'
    desc = 'Allows magical swords to roll critical hits at melee range.'
    tag = SkillTags.CUSTOM

    def allow_critical(self, unit, item, target):
        return bool(item and target and unit.position and target.position
                    and item_system.weapon_type(unit, item) == 'Sword'
                    and getattr(item, 'magic', False)
                    and utils.calculate_distance(unit.position, target.position) == 1)


class ClassNormalSwordRange(SkillComponent):
    nid = 'class_normal_sword_range'
    desc = 'Extends normal swords by one range and prevents their ranged crits.'
    tag = SkillTags.CUSTOM

    def modify_maximum_range(self, unit, item):
        return 1 if _is_normal_sword(unit, item) else 0

    def prevent_critical(self, unit, item, target):
        if not _is_normal_sword(unit, item) or not target:
            return False
        if not unit.position or not target.position:
            return False
        return utils.calculate_distance(unit.position, target.position) > 1


class ClassFirstAttemptDamage(SkillComponent):
    nid = 'class_first_attempt_damage'
    desc = 'Adds damage only to the first attempted strike of a combat.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int
    value = 0

    def raw_damage(self, unit, item, target, item2, mode, attack_info,
                   base_value):
        return self.value if attack_info == (0, 0) else 0


class ClassCriticalKillLifelink(SkillComponent):
    nid = 'class_critical_kill_lifelink'
    desc = 'Heals the user for a fraction of actual damage when a critical strike defeats a foe.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.Float
    value = 0.25

    def after_strike(self, actions, playback, unit, item, target, item2, mode,
                     attack_info, strike):
        if (strike != Strike.CRIT or not target or target.get_hp() <= 0
                or not skill_system.check_enemy(unit, target)):
            return
        true_damage = combat_utils.get_current_strike_true_damage(playback, unit, target)
        if true_damage < target.get_hp():
            return
        heal_amount = int(true_damage * float(self.value))
        if heal_amount <= 0:
            return
        heal = action.ChangeHP(unit, heal_amount)
        if heal.num > 0:
            actions.append(heal)
            playback.append(pb.HealHit(unit, item, unit, heal.num, heal.num))


class ClassInitiatorFirstAttemptDamage(SkillComponent):
    nid = 'class_initiator_first_attempt_damage'
    desc = 'Adds damage only to the initiator\'s first attempted strike.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int
    value = 0

    def raw_damage(self, unit, item, target, item2, mode, attack_info,
                   base_value):
        return self.value if mode == 'attack' and attack_info == (0, 0) else 0


class ClassFirstAttemptHit(SkillComponent):
    nid = 'class_first_attempt_hit'
    desc = 'Adds Hit only to the first attempted strike of a combat.'
    tag = SkillTags.CUSTOM
    expose = ComponentType.Int
    value = 0

    def dynamic_accuracy(self, unit, item, target, item2, mode, attack_info, base_value):
        return self.value if attack_info == (0, 0) else 0


class ClassLowestHpAdjacentHeal(SkillComponent):
    nid = 'class_lowest_hp_adjacent_heal'
    desc = 'At upkeep, heals the adjacent living ally with the lowest HP.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int
    value = 0

    @staticmethod
    def _valid_target(unit, target):
        return bool(target and target is not unit and target.position is not None
                    and not getattr(target, 'dead', False)
                    and not getattr(target, 'is_dying', False)
                    and 'Tile' not in getattr(target, 'tags', ())
                    and target.get_hp() < target.get_max_hp())

    def _target(self, unit):
        if not unit or unit.position is None:
            return None
        candidates = [
            (target.get_hp(), index, getattr(target, 'nid', ''), target)
            for index, target in enumerate(game.get_all_units())
            if self._valid_target(unit, target)
            and skill_system.check_ally(unit, target)
            and utils.calculate_distance(unit.position, target.position) == 1
        ]
        return min(candidates, default=(None, None, None, None))[-1]

    def on_upkeep(self, actions, playback, unit):
        target = self._target(unit)
        if target and self.value > 0:
            actions.append(action.ChangeHP(target, self.value))


class ClassTraversableTerrainCost(SkillComponent):
    nid = 'class_traversable_terrain_cost'
    desc = 'Makes terrain already traversable by the user cost one movement.'
    tag = SkillTags.CUSTOM

    def modify_movement_cost(self, unit, position, terrain, base_cost):
        if unit and base_cost <= unit.get_movement():
            return 1
        return base_cost


class ClassPuppetExplosion(SkillComponent):
    nid = 'class_puppet_explosion'
    desc = 'On death, deals noncombat damage to enemy units within one tile.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int
    value = 10

    def on_death(self, unit):
        if not unit or unit.position is None:
            return
        for target in game.get_all_units():
            if (target is unit or target.position is None or getattr(target, 'dead', False)
                    or getattr(target, 'is_dying', False)
                    or 'Tile' in getattr(target, 'tags', ())
                    or not skill_system.check_enemy(unit, target)
                    or utils.calculate_distance(unit.position, target.position) > 1):
                continue
            action.do(action.ChangeHP(target, -self.value))
            if target.get_hp() <= 0:
                game.death.should_die(target)


class ClassPuppetTemporary(SkillComponent):
    nid = 'class_puppet_temporary'
    desc = 'Despawns this temporary puppet when the chapter ends.'
    tag = SkillTags.CUSTOM

    def on_end_chapter_unconditional(self, unit, skill):
        if getattr(unit, '_fields', {}).get('PuppetTemporary'):
            action.do(action.DespawnClassPuppet(unit))


class LullCombatStats(SkillComponent):
    nid = 'lull_combat_stats'
    desc = ('Applies selected stat penalties and neutralizes the foe\'s '
            'positive net bonuses during combat.')
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

    def _active(self, unit, target):
        return bool(target) and _is_highest_priority_lull(self, unit)

    def _amount(self, target, stat_nid):
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


class StardustMirageBonus(SkillComponent):
    nid = 'stardust_mirage_bonus'
    desc = 'Adds Speed damage to Stardust Mirage strikes.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {
        'speed_damage_percent': ComponentType.Float,
    }

    def __init__(self, value=None):
        self.value = {'speed_damage_percent': 0.1}
        if value:
            self.value.update(value)

    def _astra_proc_is_active(self):
        for component in self.skill.components:
            if component.nid == 'astra_proc':
                return bool(getattr(component, '_should_modify_damage', False))
        return False

    def raw_damage(self, unit, item, target, item2, mode, attack_info,
                   base_value):
        if not self._astra_proc_is_active():
            return 0
        return int(unit.get_stat('SPD') * self.value['speed_damage_percent'])

def _is_highest_priority_special_spiral(component, unit):
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

    def _process_special_trigger(self, actions, playback, unit):
        if (not _is_highest_priority_special_spiral(self, unit)
                or not skill_system.condition(self.skill, unit)
                or not _did_trigger_special(playback, unit)):
            return
        if not self.skill.data['special_spiral_active']:
            actions.append(action.SetObjData(
                self.skill, 'special_spiral_active', True))
        self._triggered_this_combat = True

    def after_strike(self, actions, playback, unit, item, target, item2, mode,
                     attack_info, strike):
        self._process_special_trigger(actions, playback, unit)

    def after_take_strike(self, actions, playback, unit, item, target, item2,
                          mode, attack_info, strike):
        self._process_special_trigger(actions, playback, unit)

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
        elif (mode == expected_mode
              and self.skill.data['special_skill_pulse_armed']):
            actions.append(action.SetObjData(
                self.skill, 'special_skill_pulse_bonus',
                self.skill.data['special_skill_pulse_bonus'] + self.value))

    def after_strike(self, actions, playback, unit, item, target, item2, mode,
                     attack_info, strike):
        self._process_strike(actions, playback, unit, mode, 'attack')

    def after_take_strike(self, actions, playback, unit, item, target, item2,
                          mode, attack_info, strike):
        self._process_strike(actions, playback, unit, mode, 'defense')


class SuddenPanicBeforeCombat(SkillComponent):
    nid = 'sudden_panic_before_combat'
    desc = ('At combat start, converts the target foe\'s positive bonuses '
            'when its HP and same-team proximity satisfy the active tier.')
    tag = SkillTags.COMBAT

    expose = ComponentType.NewMultipleOptions
    options = {
        'rank': ComponentType.Int,
        'hp_gap': ComponentType.Int,
        'radius': ComponentType.Int,
        'status': ComponentType.Skill,
    }

    _stats = ('STR', 'MAG', 'SKL', 'SPD', 'LCK', 'DEF', 'RES')

    def __init__(self, value=None):
        self.value = {
            'rank': 1,
            'hp_gap': 5,
            'radius': 3,
            'status': 'Sudden_Panic_Effect',
        }
        if value:
            self.value.update(value)

    @staticmethod
    def _valid_unit(unit):
        return bool(unit and unit.position is not None
                    and not unit.dead and not unit.is_dying
                    and unit.get_hp() > 0 and 'Tile' not in unit.tags)

    def _qualifies(self, unit, target):
        if (not self._valid_unit(target)
                or not skill_system.check_enemy(unit, target)
                or target.get_hp() >= unit.get_hp() - self.value['hp_gap']):
            return False
        return any(
            other is not target
            and self._valid_unit(other)
            and other.team == target.team
            and skill_system.check_enemy(unit, other)
            and utils.calculate_distance(target.position, other.position)
                <= self.value['radius']
            for other in game.get_all_units())

    def _is_winner(self, unit, target):
        candidates = []
        for index, skill in enumerate(unit.skills):
            for component in skill.components:
                if (component.nid == self.nid
                        and component._qualifies(unit, target)):
                    candidates.append((
                        int(component.value['rank']),
                        _skill_priority(skill),
                        getattr(skill, 'uid', index),
                        component,
                    ))
        return bool(candidates and
                    max(candidates, key=lambda candidate: candidate[:3])[3]
                    is self)

    @staticmethod
    def _skip_current_wait(mode):
        current_combat = game.memory.get('current_combat')
        return bool(
            mode == 'defense'
            and current_combat is not None
            and current_combat.finalizes_turn
            and not current_combat.event_combat)

    def pre_combat(self, playback, unit, item, target, item2, mode):
        if not target or not self._is_winner(unit, target):
            return
        snapshot = {
            stat: max(0, target.stat_bonus(stat)) for stat in self._stats}
        if not any(snapshot.values()):
            return
        skip_current_wait = self._skip_current_wait(mode)
        existing = next((skill for skill in target.skills
                         if skill.nid == self.value['status']), None)
        if existing:
            action.do(action.SetObjData(
                existing, 'sudden_panic_bonuses', snapshot))
            action.do(action.SetObjData(
                existing, 'skip_current_wait', skip_current_wait))
            return
        add_status = action.AddSkill(target, self.value['status'], unit)
        if add_status.skill_obj:
            add_status.skill_obj.data['sudden_panic_bonuses'] = snapshot
            add_status.skill_obj.data['skip_current_wait'] = skip_current_wait
        action.do(add_status)


class SuddenPanicBonusConversionEffect(SkillComponent):
    nid = 'sudden_panic_bonus_conversion_effect'
    desc = 'Converts the captured positive stat bonuses into penalties.'
    tag = SkillTags.COMBAT

    _stats = ('STR', 'MAG', 'SKL', 'SPD', 'LCK', 'DEF', 'RES')

    def init(self, skill):
        skill.data.setdefault('sudden_panic_bonuses', {})

    def stat_change(self, unit):
        snapshot = self.skill.data.get('sudden_panic_bonuses', {})
        return {
            stat: -2 * max(0, snapshot.get(stat, 0))
            for stat in self._stats
        }


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
        if strike in (Strike.HIT, Strike.CRIT) and target:
            from app.engine import skill_system
            if skill_system.check_enemy(unit, target):
                for status in self.value:
                    actions.append(action.AddSkill(target, status, unit))
                actions.append(action.TriggerCharge(unit, self.skill))
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
        return self.value if attack_info[0] == 0 and attack_info[1] == 0 else 1

class NegateCannotDouble(SkillComponent):
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


class DullWilyNeutralizeBonuses(SkillComponent):
    nid = 'dull_wily_neutralize_bonuses'
    desc = 'Snapshots and neutralizes the target\'s positive combat bonuses.'
    tag = SkillTags.COMBAT

    _effect_nid = 'Dull_Wily_Neutralized_Bonus_Effect'
    _data_key = 'dull_wily_neutralized_bonuses'
    _stat_nids = ('STR', 'MAG', 'SKL', 'SPD', 'LCK', 'DEF', 'RES')

    def start_combat(self, playback, unit, item, target, item2, mode):
        if not target or any(skill.nid == self._effect_nid for skill in target.skills):
            return

        snapshot = {
            stat_nid: max(0, target.stat_bonus(stat_nid))
            for stat_nid in self._stat_nids
        }
        add_effect = action.AddSkill(target, self._effect_nid, unit)
        if add_effect.skill_obj:
            add_effect.skill_obj.data[self._data_key] = snapshot
        action.do(add_effect)


class DullWilyNeutralizedBonusEffect(SkillComponent):
    nid = 'dull_wily_neutralized_bonus_effect'
    desc = 'Applies the Dull/Wily snapshot stored on this effect instance.'
    tag = SkillTags.COMBAT

    _data_key = 'dull_wily_neutralized_bonuses'
    _stat_nids = ('STR', 'MAG', 'SKL', 'SPD', 'LCK', 'DEF', 'RES')

    def init(self, skill):
        skill.data.setdefault(self._data_key, {})

    def stat_change(self, unit):
        bonuses = self.skill.data.get(self._data_key, {})
        return {
            stat_nid: -max(0, bonuses.get(stat_nid, 0))
            for stat_nid in self._stat_nids
        }


class SlickNeutralizeSelfPenalties(SkillComponent):
    nid = 'slick_neutralize_self_penalties'
    desc = 'Snapshots and neutralizes the user\'s negative combat penalties.'
    tag = SkillTags.COMBAT

    _effect_nid = 'Slick_Neutralized_Penalty_Effect'
    _data_key = 'slick_neutralized_self_penalties'
    _stat_nids = ('STR', 'MAG', 'SKL', 'SPD', 'LCK', 'DEF', 'RES')

    def start_combat(self, playback, unit, item, target, item2, mode):
        if any(skill.nid == self._effect_nid for skill in unit.skills):
            return

        snapshot = {
            stat_nid: max(0, -unit.stat_bonus(stat_nid))
            for stat_nid in self._stat_nids
        }
        add_effect = action.AddSkill(unit, self._effect_nid, unit)
        if add_effect.skill_obj:
            add_effect.skill_obj.data[self._data_key] = snapshot
        action.do(add_effect)


class SlickNeutralizedPenaltyStatChange(SkillComponent):
    nid = 'slick_neutralized_penalty_stat_change'
    desc = 'Applies the Slick penalty snapshot stored on this effect instance.'
    tag = SkillTags.COMBAT

    _data_key = 'slick_neutralized_self_penalties'
    _stat_nids = ('STR', 'MAG', 'SKL', 'SPD', 'LCK', 'DEF', 'RES')

    def init(self, skill):
        skill.data.setdefault(self._data_key, {})

    def stat_change(self, unit):
        penalties = self.skill.data.get(self._data_key, {})
        return {
            stat_nid: max(0, penalties.get(stat_nid, 0))
            for stat_nid in self._stat_nids
        }


class ExclusiveUpkeepEffect(SkillComponent):
    nid = 'exclusive_upkeep_effect'
    desc = 'Marks a temporary effect as claimed by one ranked upkeep group.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {'group': ComponentType.String, 'rank': ComponentType.Int}

    def __init__(self, value=None):
        self.value = {'group': '', 'rank': 0}
        if value:
            self.value.update(value)


class _RankedUpkeepStatus(SkillComponent):
    """Shared queueing bridge for project components using RankedUpkeepContext."""
    nid = None
    @staticmethod
    def _valid_target(target):
        return target and target.position is not None and not getattr(target, 'dead', False) \
            and not getattr(target, 'is_dying', False) and 'Tile' not in getattr(target, 'tags', ())

    @staticmethod
    def _has_status(target, status, actions):
        return any(skill.nid == status for skill in getattr(target, 'all_skills', target.skills)) or any(
            isinstance(queued, action.AddSkill) and queued.unit is target and queued.skill_obj
            and queued.skill_obj.nid == status for queued in actions)

    def _queue_assignment(self, actions, unit, request):
        context = ranked_upkeep.current()
        if context and request.group:
            targets = context.targets_for(unit, self)
        else:
            targets = request.targets if request.max_targets is None else request.targets[:request.max_targets]
        for target in targets:
            if not self._has_status(target, self.value['status'], actions):
                actions.append(action.AddSkill(target, self.value['status'], unit))


class TemporaryMovementBonus(SkillComponent):
    nid = 'temporary_movement_bonus'
    desc = 'Applies the strongest temporary movement bonus from this effect line.'
    tag = SkillTags.CUSTOM

    def init(self, skill):
        skill.data.setdefault('movement_bonus', 0)

    def stat_change(self, unit):
        components = [component for skill in unit.skills if skill.nid == self.skill.nid
                      for component in skill.components if component.nid == self.nid]
        if not components:
            return {'MOV': 0}
        winner = max(components, key=lambda component:
                     (component.skill.data.get('movement_bonus', 0), component.skill.uid))
        return {'MOV': winner.skill.data.get('movement_bonus', 0) if winner is self else 0}


class _ArmoredMovementAtUpkeep(SkillComponent):
    nid = None
    _effect_nid = None

    expose = ComponentType.NewMultipleOptions
    options = {
        'hp': ComponentType.String,
        'range': ComponentType.Int,
        'bonus': ComponentType.Int,
        'rank': ComponentType.Int,
    }

    def __init__(self, value=None):
        self.value = {'hp': 'any', 'range': 3, 'bonus': 1, 'rank': 1}
        if value:
            self.value.update(value)

    @staticmethod
    def _valid(unit):
        return unit and unit.position is not None and not getattr(unit, 'dead', False) \
            and not getattr(unit, 'is_dying', False) and unit.get_hp() > 0 \
            and 'Tile' not in getattr(unit, 'tags', ())

    def _hp_qualified(self, unit):
        if self.value['hp'] == 'full':
            return unit.get_hp() == unit.get_max_hp()
        if self.value['hp'] == 'above_half':
            return unit.get_hp() * 2 > unit.get_max_hp()
        return True

    def _qualified(self, unit):
        return self._valid(unit) and self._hp_qualified(unit) and self._condition(unit)

    def _is_highest_qualified(self, unit):
        qualified = [component for skill in unit.skills for component in skill.components
                     if component.nid == self.nid and component._qualified(unit)]
        return qualified and max(qualified, key=lambda component: component.value['rank']) is self

    def _condition(self, unit):
        raise NotImplementedError

    def _grant(self, actions, target, unit):
        existing = [skill for skill in target.skills if skill.nid == self._effect_nid]
        existing_bonus = max((skill.data.get('movement_bonus', 0) for skill in existing), default=0)
        if existing_bonus >= self.value['bonus']:
            return
        actions.extend(action.RemoveSkill(target, skill) for skill in existing)
        add_effect = action.AddSkill(target, self._effect_nid, unit)
        if add_effect.skill_obj:
            add_effect.skill_obj.data['movement_bonus'] = self.value['bonus']
            actions.append(add_effect)


class ArmorMachAtUpkeep(_ArmoredMovementAtUpkeep):
    nid = 'armor_mach_at_upkeep'
    desc = 'At upkeep, grants movement to its user and every nearby armored ally.'
    tag = SkillTags.CUSTOM
    _effect_nid = 'Armor_Mach_Movement_Effect'

    def _condition(self, unit):
        return True

    def on_upkeep(self, actions, playback, unit):
        if not self._is_highest_qualified(unit):
            return
        self._grant(actions, unit, unit)
        for target in game.get_all_units():
            if target is unit or not self._valid(target) or 'Armor' not in target.tags:
                continue
            if skill_system.check_ally(unit, target) \
                    and utils.calculate_distance(unit.position, target.position) <= self.value['range']:
                self._grant(actions, target, unit)


class ArmoredStrideAtUpkeep(_ArmoredMovementAtUpkeep):
    nid = 'armored_stride_at_upkeep'
    desc = 'At upkeep, grants movement to its user when no nearby valid ally exists.'
    tag = SkillTags.CUSTOM
    _effect_nid = 'Armored_Stride_Movement_Effect'

    def _condition(self, unit):
        return not any(target is not unit and self._valid(target) and skill_system.check_ally(unit, target)
                       and utils.calculate_distance(unit.position, target.position) <= self.value['range']
                       for target in game.get_all_units())

    def on_upkeep(self, actions, playback, unit):
        if self._is_highest_qualified(unit):
            self._grant(actions, unit, unit)


class ChillHighestStat(_RankedUpkeepStatus):
    nid = 'chill_highest_stat'
    desc = 'Inflicts a status on the highest selected-stat enemy at upkeep.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {
        'stat': ComponentType.Stat,
        'status': ComponentType.Skill,
        'rank': ComponentType.Int,
    }

    def __init__(self, value=None):
        self.value = {
            'stat': 'STR',
            'status': 'Chill_Strength_T1_Effect',
            'rank': 1,
        }
        if value:
            self.value.update(value)

    def ranked_upkeep_request(self, unit):
        stat_nid = self.value['stat']
        units = list(game.get_all_units())
        unit_order = {id(foe): index for index, foe in enumerate(units)}
        foes = [foe for foe in units
                if foe is not unit and self._valid_target(foe) and skill_system.check_enemy(unit, foe)]
        foes.sort(key=lambda foe: (-foe.get_stat(stat_nid), unit_order[id(foe)], foe.nid, getattr(foe, 'uid', 0)))
        return ranked_upkeep.RankedUpkeepRequest(
            unit, self, f'chill:{stat_nid}', self.value['rank'], foes, 1)

    def on_upkeep(self, actions, playback, unit):
        request = self.ranked_upkeep_request(unit)
        if not ranked_upkeep.current():
            for owned_skill in unit.skills:
                for component in owned_skill.components:
                    if component is not self and component.nid == self.nid and \
                            component.value['stat'] == self.value['stat'] and \
                            component.value['rank'] > self.value['rank']:
                        return
        self._queue_assignment(actions, unit, request)


class OpeningHighestStat(_RankedUpkeepStatus):
    nid = 'opening_highest_stat'
    desc = 'At upkeep, grants a status to all highest selected-stat allies other than the user.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {
        'stat': ComponentType.Stat,
        'status': ComponentType.Skill,
        'rank': ComponentType.Int,
    }

    def __init__(self, value=None):
        self.value = {
            'stat': 'STR',
            'status': 'Strength_Opening_T1_Effect',
            'rank': 1,
        }
        if value:
            self.value.update(value)

    @staticmethod
    def _living_target(target):
        return _RankedUpkeepStatus._valid_target(target) and \
            (not hasattr(target, 'get_hp') or target.get_hp() > 0)

    def ranked_upkeep_request(self, unit):
        if not self._living_target(unit) or not self.value['status']:
            return None
        stat_nid = self.value['stat']
        allies = [target for target in game.get_all_units()
                  if target is not unit and self._living_target(target)
                  and skill_system.check_ally(unit, target)]
        bands_by_stat = {}
        for target in allies:
            bands_by_stat.setdefault(target.get_stat(stat_nid), []).append(target)
        target_bands = [bands_by_stat[value] for value in sorted(bands_by_stat, reverse=True)]
        targets = [target for band in target_bands for target in band]
        return ranked_upkeep.RankedUpkeepRequest(
            unit, self, f'opening:{stat_nid}', self.value['rank'], targets, None, target_bands)

    def on_upkeep(self, actions, playback, unit):
        request = self.ranked_upkeep_request(unit)
        if not request:
            return
        if not ranked_upkeep.current():
            for owned_skill in unit.skills:
                for component in owned_skill.components:
                    if component is not self and component.nid == self.nid and \
                            component.value['stat'] == self.value['stat'] and \
                            component.value['rank'] > self.value['rank']:
                        return
        self._queue_assignment(actions, unit, request)


class UpkeepStatusClosestEnemy(SkillComponent):
    nid = 'upkeep_status_closest_enemy'
    desc = 'Inflicts a status on the closest valid enemy at upkeep.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.Skill
    value = None

    def on_upkeep(self, actions, playback, unit):
        valid_foes = [
            foe for foe in game.get_all_units()
            if foe is not unit and foe.position is not None and not foe.dead and not foe.is_dying
            and 'Tile' not in foe.tags and skill_system.check_enemy(unit, foe)
        ]
        if not valid_foes:
            return
        target = min(valid_foes, key=lambda foe: (utils.calculate_distance(unit.position, foe.position), foe.nid))
        actions.append(action.AddSkill(target, self.value, unit))


class HoneAllyStatus(_RankedUpkeepStatus):
    nid = 'hone_ally_status'
    desc = 'At upkeep, grants a status to nearby eligible allies.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {
        'status': ComponentType.Skill,
        'range': ComponentType.Int,
        'required_tags': (ComponentType.List, ComponentType.Tag),
        'group': ComponentType.String,
        'rank': ComponentType.Int,
    }

    def __init__(self, value=None):
        self.value = {
            'status': None,
            'range': 1,
            'required_tags': [],
            'group': '',
            'rank': 0,
        }
        if value:
            self.value.update(value)

    def ranked_upkeep_request(self, unit):
        if not unit or unit.position is None or not self.value['status']:
            return None
        required_tags = set(self.value['required_tags'])
        targets = []
        for target in game.get_all_units():
            if target is unit or not self._valid_target(target) or not skill_system.check_ally(unit, target):
                continue
            distance = utils.calculate_distance(unit.position, target.position)
            if not 1 <= distance <= self.value['range']:
                continue
            if required_tags and not required_tags.intersection(target.tags):
                continue
            targets.append(target)
        return ranked_upkeep.RankedUpkeepRequest(
            unit, self, f"hone:{self.value['group']}" if self.value['group'] else '',
            self.value['rank'], targets, None)

    def on_upkeep(self, actions, playback, unit):
        request = self.ranked_upkeep_request(unit)
        if request:
            self._queue_assignment(actions, unit, request)


class ThreatenFoesAtUpkeep(_RankedUpkeepStatus):
    nid = 'threaten_foes_at_upkeep'
    desc = 'At upkeep, inflicts a status on nearby foes unless a higher rank in its group is active.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {
        'status': ComponentType.Skill,
        'range': ComponentType.Int,
        'group': ComponentType.String,
        'rank': ComponentType.Int,
    }

    def __init__(self, value=None):
        self.value = {'status': None, 'range': 2, 'group': '', 'rank': 0}
        if value:
            self.value.update(value)

    def ranked_upkeep_request(self, unit):
        if not self._valid_target(unit) or not self.value['status']:
            return None
        targets = []
        for foe in game.get_all_units():
            if foe is unit or not self._valid_target(foe) or not skill_system.check_enemy(unit, foe):
                continue
            distance = utils.calculate_distance(unit.position, foe.position)
            if 1 <= distance <= self.value['range']:
                targets.append(foe)
        return ranked_upkeep.RankedUpkeepRequest(
            unit, self, f"threaten:{self.value['group']}", self.value['rank'], targets, None)

    def on_upkeep(self, actions, playback, unit):
        request = self.ranked_upkeep_request(unit)
        if not request:
            return
        if not ranked_upkeep.current():
            for skill in unit.skills:
                for component in skill.components:
                    if component is not self and component.nid == self.nid \
                            and component.value['group'] == self.value['group'] \
                            and component.value['rank'] > self.value['rank']:
                        return
        self._queue_assignment(actions, unit, request)


class RankedStatPloy(_RankedUpkeepStatus):
    nid = 'ranked_stat_ploy'
    desc = 'At upkeep, inflicts a ranked status on the eligible foe with highest Resistance.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {'stat': ComponentType.Stat, 'status': ComponentType.Skill, 'rank': ComponentType.Int}

    def __init__(self, value=None):
        self.value = {'stat': 'STR', 'status': None, 'rank': 1}
        if value:
            self.value.update(value)

    def ranked_upkeep_request(self, unit):
        if not self._valid_target(unit) or not self.value['status']:
            return None
        user_res = unit.get_stat('RES')
        units = list(game.get_all_units())
        unit_order = {id(foe): index for index, foe in enumerate(units)}
        targets = [foe for foe in units
                   if foe is not unit and self._valid_target(foe)
                   and skill_system.check_enemy(unit, foe) and foe.get_stat('RES') < user_res]
        targets.sort(key=lambda foe: (-foe.get_stat('RES'), unit_order[id(foe)], foe.nid, getattr(foe, 'uid', 0)))
        return ranked_upkeep.RankedUpkeepRequest(
            unit, self, f"ploy:{self.value['stat']}", self.value['rank'], targets, 1)

    def on_upkeep(self, actions, playback, unit):
        request = self.ranked_upkeep_request(unit)
        if request:
            self._queue_assignment(actions, unit, request)


class RankedSabotageUpkeep(_RankedUpkeepStatus):
    nid = 'ranked_sabotage_upkeep'
    desc = 'At upkeep, inflicts a ranked status on eligible clustered foes.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {'stat': ComponentType.Stat, 'status': ComponentType.Skill, 'rank': ComponentType.Int}

    def __init__(self, value=None):
        self.value = {'stat': 'STR', 'status': None, 'rank': 1}
        if value:
            self.value.update(value)

    def ranked_upkeep_request(self, unit):
        if not self._valid_target(unit) or not self.value['status']:
            return None
        user_res = unit.get_stat('RES')
        living = [other for other in game.get_all_units() if self._valid_target(other)]
        targets = []
        for foe in living:
            if foe is unit or not skill_system.check_enemy(unit, foe) or foe.get_stat('RES') >= user_res - 3:
                continue
            if any(other is not foe and skill_system.check_enemy(unit, other)
                   and utils.calculate_distance(foe.position, other.position) == 1 for other in living):
                targets.append(foe)
        return ranked_upkeep.RankedUpkeepRequest(
            unit, self, f"sabotage:{self.value['stat']}", self.value['rank'], targets, None)

    def on_upkeep(self, actions, playback, unit):
        request = self.ranked_upkeep_request(unit)
        if request:
            self._queue_assignment(actions, unit, request)


class PanicPloyDuringCombat(SkillComponent):
    nid = 'panic_ploy_during_combat'
    desc = 'Converts positive foe bonuses into penalties during combat at the highest active tier.'
    tag = SkillTags.COMBAT

    expose = ComponentType.NewMultipleOptions
    options = {'rank': ComponentType.Int, 'hp_gap': ComponentType.Int, 'status': ComponentType.Skill}
    _stats = ('STR', 'MAG', 'SKL', 'SPD', 'LCK', 'DEF', 'RES')

    def __init__(self, value=None):
        self.value = {'rank': 1, 'hp_gap': 5, 'status': 'Panic_Ploy_Effect'}
        if value:
            self.value.update(value)

    def _is_winner(self, unit, target):
        qualified = []
        for skill in unit.skills:
            for component in skill.components:
                if component.nid == self.nid and unit.get_hp() < target.get_hp() - component.value['hp_gap']:
                    qualified.append(component)
        return qualified and max(qualified, key=lambda component: component.value['rank']) is self

    def pre_combat(self, playback, unit, item, target, item2, mode):
        if not target or not skill_system.check_enemy(unit, target) or not self._is_winner(unit, target):
            return
        if any(skill.nid == self.value['status'] for skill in target.skills):
            return
        snapshot = {stat: max(0, target.stat_bonus(stat)) for stat in self._stats}
        add_effect = action.AddSkill(target, self.value['status'], unit)
        if add_effect.skill_obj:
            add_effect.skill_obj.data['panic_ploy_bonuses'] = snapshot
        action.do(add_effect)


class PanicPloyBonusConversionEffect(SkillComponent):
    nid = 'panic_ploy_bonus_conversion_effect'
    desc = 'Applies the per-combat Panic Ploy snapshot.'
    tag = SkillTags.COMBAT
    _stats = ('STR', 'MAG', 'SKL', 'SPD', 'LCK', 'DEF', 'RES')

    def init(self, skill):
        skill.data.setdefault('panic_ploy_bonuses', {})

    def stat_change(self, unit):
        snapshot = self.skill.data.get('panic_ploy_bonuses', {})
        return {stat: -2 * max(0, snapshot.get(stat, 0)) for stat in self._stats}


class StallPloyAfterCombat(SkillComponent):
    nid = 'stall_ploy_after_combat'
    desc = 'Caps foe movement after combat at the highest active tier.'
    tag = SkillTags.COMBAT2

    expose = ComponentType.NewMultipleOptions
    options = {'rank': ComponentType.Int, 'hp_gap': ComponentType.Int, 'status': ComponentType.Skill}

    def __init__(self, value=None):
        self.value = {'rank': 1, 'hp_gap': 5, 'status': 'Stall_Ploy_Effect'}
        if value:
            self.value.update(value)

    def _is_winner(self, unit, target):
        qualified = []
        for skill in unit.skills:
            for component in skill.components:
                if component.nid == self.nid and unit.get_hp() < target.get_hp() - component.value['hp_gap']:
                    qualified.append(component)
        return qualified and max(qualified, key=lambda component: component.value['rank']) is self

    def end_combat(self, playback, unit, item, target, item2, mode):
        if not target or not skill_system.check_enemy(unit, target) or target.dead or target.is_dying \
                or target.get_hp() <= 0 or not self._is_winner(unit, target):
            return
        if any(skill.nid == self.value['status'] for skill in target.skills):
            return
        add_status = action.AddSkill(target, self.value['status'], unit)
        current_combat = game.memory.get('current_combat')
        if mode == 'defense' and current_combat is not None and current_combat.finalizes_turn \
                and not current_combat.event_combat and add_status.skill_obj:
            action.do(action.SetObjData(add_status.skill_obj, 'skip_current_wait', True))
        action.do(add_status)


class MovementCap(SkillComponent):
    nid = 'movement_cap'
    desc = 'Caps the owner\'s final movement value.'
    tag = SkillTags.MOVEMENT

    expose = ComponentType.Int
    value = 1

    def movement_cap(self, unit):
        return self.value


class SaveInterceptor(SkillComponent):
    nid = 'save_interceptor'
    desc = 'Offers a nearby armored ally as the defender for a matching Save interception.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {
        'kind': (ComponentType.MultipleChoice, ('near', 'far')),
        'radius': ComponentType.Int,
        'rank': ComponentType.Int,
        'stats': (ComponentType.Dict, ComponentType.Stat),
        'damage': ComponentType.Int,
    }
    value = {'kind': 'near', 'radius': 1, 'rank': 1, 'stats': [], 'damage': 0}

    def save_intercept_offers(self, provider, attacker, protected, item, attack_distance):
        from app.engine.combat.save_intercept import SaveOffer
        return SaveOffer(
            provider, self.skill, self.value['kind'], self.value['radius'], self.value['rank'],
            tuple((stat, amount) for stat, amount in self.value['stats']), self.value['damage'])

    def _is_active_choice(self, unit):
        from app.engine.combat.save_intercept import get_active_save_interception
        interception = get_active_save_interception()
        return bool(interception and interception.savior is unit and
                    interception.offer.skill is self.skill)

    def stat_change(self, unit):
        if self._is_active_choice(unit):
            return {stat: amount for stat, amount in self.value['stats']}
        return {}

    def modify_damage(self, unit, item):
        return self.value['damage'] if self._is_active_choice(unit) else 0


class ClassDarkGiftIntercept(SkillComponent):
    nid = 'class_dark_gift_intercept'
    desc = ('Once per turn while below the configured HP threshold, lets an '
            'adjacent ally intercept for this unit.')
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {
        'hp_threshold': ComponentType.Int,
        'rank': ComponentType.Int,
        'proc_rate_bonus': ComponentType.Int,
        'heal_multiplier': ComponentType.Float,
    }
    value = {'hp_threshold': 20, 'rank': 4, 'proc_rate_bonus': 0, 'heal_multiplier': 1.0}

    def __init__(self, value=None):
        self.value = self.value.copy()
        if value:
            self.value.update(value)

    @staticmethod
    def _eligible(unit):
        return bool(unit and unit.position is not None and not unit.dead and
                    not unit.is_dying and 'Tile' not in unit.tags and unit.get_hp() > 0)

    def init(self, skill):
        skill.data.setdefault('save_intercept_last_turn', None)

    def save_intercept_offers(self, provider, attacker, protected, item, attack_distance):
        from app.engine.combat.save_intercept import SaveOffer

        if (provider is not protected or not self._eligible(provider)
                or provider.get_hp() * 100 >= provider.get_max_hp() * self.value['hp_threshold']
                or self.skill.data.get('save_intercept_last_turn') == getattr(game, 'turncount', 0)):
            return None
        candidates = [
            (-(candidate.get_hp()), index, candidate.nid, candidate)
            for index, candidate in enumerate(game.get_all_units())
            if self._eligible(candidate) and candidate is not provider
            and skill_system.check_ally(provider, candidate)
            and utils.calculate_distance(provider.position, candidate.position) == 1
        ]
        if not candidates:
            return None
        candidate = min(candidates)[-1]
        return SaveOffer(
            candidate, self.skill, 'any', 1, self.value['rank'], (), 0,
            requires_armored=False, consume_once_per_turn=True)

    def modify_debuff_proc_rate(self, unit, target):
        return int(self.value['proc_rate_bonus'])

    def heal_multiplier(self, unit, target):
        return float(self.value['heal_multiplier'])


class ClassIndoorHitAvoid(SkillComponent):
    nid = 'class_indoor_hit_avoid'
    desc = 'Grants the configured Hit and Avoid bonus only while on an indoor terrain.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {'bonus': ComponentType.Int}
    value = {'bonus': 5}
    _indoor_terrains = frozenset(('2', '3', '5', '8', '9', '25', '30', '31', '32', '33', '34',
                                  '35', '36', '37', '38', 'Arena', 'Ruins', 'Village Ruins',
                                  'NightVillageRuins', 'NightForest', 'NightVillage'))

    def __init__(self, value=None):
        self.value = self.value.copy()
        if value:
            self.value.update(value)

    def _active(self, unit):
        return bool(unit and unit.position is not None and game.tilemap
                    and game.tilemap.get_terrain(unit.position) in self._indoor_terrains)

    def modify_accuracy(self, unit, item):
        return self.value['bonus'] if self._active(unit) else 0

    def modify_avoid(self, unit, item):
        return self.value['bonus'] if self._active(unit) else 0


class ClassOutdoorHitAvoid(SkillComponent):
    nid = 'class_outdoor_hit_avoid'
    desc = 'Grants the configured Hit and Avoid bonus only while on an outdoor terrain.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {'bonus': ComponentType.Int}
    value = {'bonus': 5}
    _outdoor_terrains = frozenset(('1', '4', '6', '7', '10', '11', '12', '14', '17', '20',
                                   '21', '22', '41', '42', 'NightPlain', 'NightBridge',
                                   'NightRoad', 'NightRiver', 'NightMountain', 'NightDock'))

    def __init__(self, value=None):
        self.value = self.value.copy()
        if value:
            self.value.update(value)

    def _active(self, unit):
        return bool(unit and unit.position is not None and game.tilemap
                    and game.tilemap.get_terrain(unit.position) in self._outdoor_terrains)

    def modify_accuracy(self, unit, item):
        return self.value['bonus'] if self._active(unit) else 0

    def modify_avoid(self, unit, item):
        return self.value['bonus'] if self._active(unit) else 0


def _class_valid_map_unit(unit):
    return bool(unit and unit.position is not None and not getattr(unit, 'dead', False)
                and not getattr(unit, 'is_dying', False) and unit.get_hp() > 0
                and 'Tile' not in getattr(unit, 'tags', ()))


def _class_adjacent_allies(unit):
    if not _class_valid_map_unit(unit):
        return []
    return [candidate for candidate in game.get_all_units()
            if candidate is not unit and _class_valid_map_unit(candidate)
            and skill_system.check_ally(unit, candidate)
            and utils.calculate_distance(unit.position, candidate.position) == 1]


class ClassAdjacentHitAvoid(SkillComponent):
    nid = 'class_adjacent_hit_avoid'
    desc = 'Grants the configured Hit and Avoid while the user has an adjacent ally.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {'bonus': ComponentType.Int}
    value = {'bonus': 5}

    def __init__(self, value=None):
        self.value = self.value.copy()
        if value:
            self.value.update(value)

    def modify_accuracy(self, unit, item):
        return self.value['bonus'] if _class_adjacent_allies(unit) else 0

    def modify_avoid(self, unit, item):
        return self.value['bonus'] if _class_adjacent_allies(unit) else 0


class ClassIsolatedFirstAttemptDamage(SkillComponent):
    nid = 'class_isolated_first_attempt_damage'
    desc = 'Adds damage to the isolated user\'s first attempted outgoing strike.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int
    value = 0

    def raw_damage(self, unit, item, target, item2, mode, attack_info, base_value):
        if mode == 'attack' and attack_info == (0, 0) and not _class_adjacent_allies(unit):
            return self.value
        return 0


class ClassIsolatedFirstStrikeResist(SkillComponent):
    nid = 'class_isolated_first_strike_resist'
    desc = 'Reduces the isolated user\'s first attempted incoming strike.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.Float
    value = 1

    def resist_multiplier(self, unit, item, target, item2, mode, attack_info, base_value):
        if mode == 'defense' and attack_info == (0, 0) and not _class_adjacent_allies(unit):
            return self.value
        return 1


class ClassQuickBurnHitAvoid(SkillComponent):
    nid = 'class_quick_burn_hit_avoid'
    desc = 'Grants a Hit and Avoid bonus that starts at the configured value then drops by one each turn.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int
    value = 5

    _data_key = 'class_quick_burn_initiations'

    def init(self, skill):
        skill.data.setdefault(self._data_key, 0)

    def _bonus(self):
        return max(0, self.value - int(self.skill.data.get(self._data_key, 0)))

    def start_combat(self, playback, unit, item, target, item2, mode):
        if mode == 'attack':
            action.do(action.SetObjData(
                self.skill, self._data_key,
                int(self.skill.data.get(self._data_key, 0)) + 1))

    def modify_accuracy(self, unit, item):
        return self._bonus()

    def modify_avoid(self, unit, item):
        return self._bonus()


class ClassInfernalDominion(SkillComponent):
    nid = 'class_infernal_dominion'
    desc = ('Gains +2 Hit and Avoid each turn to +20, then grants +1 damage '
            'per five Hit and +1% skill proc rate per five Avoid.')
    tag = SkillTags.CUSTOM

    @staticmethod
    def _bonus():
        return min(20, max(0, getattr(game, 'turncount', 1)) * 2)

    def modify_accuracy(self, unit, item):
        return self._bonus()

    def modify_avoid(self, unit, item):
        return self._bonus()

    def raw_damage(self, unit, item, target, item2, mode, attack_info, base_value):
        return self._bonus() // 5 if mode == 'attack' else 0

    def modify_self_proc_rate(self, unit):
        return self._bonus() // 5


class ClassSourcePlaceholder(SkillComponent):
    nid = 'class_source_placeholder'
    desc = 'Marks a Class List row with no source behavior as an intentional placeholder.'
    tag = SkillTags.CUSTOM


class ClassSlowBurn(SkillComponent):
    """Shared turn-scaling contract for the three Malig Knight Class List rows."""
    nid = 'class_slow_burn'
    desc = 'Gains Hit/Avoid each turn and converts configured portions into combat bonuses.'
    tag = SkillTags.CUSTOM
    expose = ComponentType.NewMultipleOptions
    options = {
        'per_turn': ComponentType.Int,
        'cap': ComponentType.Int,
        'damage_per_five': ComponentType.Bool,
        'res_penalty_per_five': ComponentType.Bool,
        'proc_per_five': ComponentType.Bool,
    }

    def __init__(self, value=None):
        self.value = {'per_turn': 1, 'cap': 15, 'damage_per_five': False,
                      'res_penalty_per_five': False, 'proc_per_five': False}
        if value:
            self.value.update(value)

    def _bonus(self):
        return min(int(self.value['cap']), max(0, getattr(game, 'turncount', 1)) *
                   int(self.value['per_turn']))

    def modify_accuracy(self, unit, item):
        return self._bonus()

    def modify_avoid(self, unit, item):
        return self._bonus()

    def raw_damage(self, unit, item, target, item2, mode, attack_info, base_value):
        return self._bonus() // 5 if mode == 'attack' and self.value['damage_per_five'] else 0

    def dynamic_damage(self, unit, item, target, item2, mode, attack_info, base_value):
        if (mode == 'attack' and self.value['res_penalty_per_five'] and item and
                item_funcs.is_magic_in_combat(unit, item, target)):
            return self._bonus() // 5
        return 0

    def modify_self_proc_rate(self, unit):
        return self._bonus() // 5 if self.value['proc_per_five'] else 0


class ClassGroundFoeHitAvoid(SkillComponent):
    nid = 'class_ground_foe_hit_avoid'
    desc = 'Grants Hit and Avoid only while fighting a non-flying foe.'
    tag = SkillTags.CUSTOM
    expose = ComponentType.Int
    value = 0

    @staticmethod
    def _ground(target):
        return bool(target and 'Flying' not in getattr(target, 'tags', ()))

    def dynamic_accuracy(self, unit, item, target, item2, mode, attack_info, base_value):
        return self.value if self._ground(target) else 0

    def dynamic_avoid(self, unit, item, target, item2, mode, attack_info, base_value):
        return self.value if self._ground(target) else 0


def _class_adjacent_flying_allies(unit):
    return [candidate for candidate in _class_adjacent_allies(unit)
            if 'Flying' in getattr(candidate, 'tags', ())]


class ClassRaidValkyria(SkillComponent):
    nid = 'class_raid_valkyria'
    desc = 'Applies Raid of the Valkyria combat bonuses against grounded foes.'
    tag = SkillTags.CUSTOM
    expose = ComponentType.NewMultipleOptions
    options = {'ground_avoid': ComponentType.Int, 'first_attempt_damage': ComponentType.Int,
               'isolated_spd': ComponentType.Int}
    value = {'ground_avoid': 0, 'first_attempt_damage': 0, 'isolated_spd': 0}

    def __init__(self, value=None):
        self.value = self.value.copy()
        if value:
            self.value.update(value)

    @staticmethod
    def _ground(target):
        return bool(target and 'Flying' not in getattr(target, 'tags', ()))

    def dynamic_avoid(self, unit, item, target, item2, mode, attack_info, base_value):
        return int(self.value['ground_avoid']) if self._ground(target) else 0

    def dynamic_accuracy(self, unit, item, target, item2, mode, attack_info, base_value):
        if not self._ground(target):
            return 0
        total = 0
        for skill in getattr(target, 'skills', ()):
            if getattr(skill, 'source_type', None) != SourceType.TERRAIN:
                continue
            for component in getattr(skill, 'components', ()):
                if component.nid == 'avoid' and skill_system.condition(target, item2):
                    total += int(component.modify_avoid(target, item2))
        return total

    def raw_damage(self, unit, item, target, item2, mode, attack_info, base_value):
        if mode == 'attack' and attack_info == (0, 0):
            return int(self.value['first_attempt_damage'])
        return 0

    def stat_change(self, unit):
        return {'SPD': int(self.value['isolated_spd'])} if not _class_adjacent_flying_allies(unit) else {}


class ClassAirSuperiority(SkillComponent):
    nid = 'class_air_superiority'
    desc = 'Applies Air Superiority bonuses and blocks foe follow-up against magic.'
    tag = SkillTags.CUSTOM
    expose = ComponentType.NewMultipleOptions
    options = {'flying_foe_avoid_penalty': ComponentType.Int, 'crit': ComponentType.Int,
               'isolated_skl': ComponentType.Int, 'magic_block_status': ComponentType.Skill}
    value = {'flying_foe_avoid_penalty': 0, 'crit': 0, 'isolated_skl': 0,
             'magic_block_status': None}

    def __init__(self, value=None):
        self.value = self.value.copy()
        if value:
            self.value.update(value)

    @staticmethod
    def _flying(target):
        return bool(target and 'Flying' in getattr(target, 'tags', ()))

    def dynamic_accuracy(self, unit, item, target, item2, mode, attack_info, base_value):
        return int(self.value['flying_foe_avoid_penalty']) if self._flying(target) else 0

    def dynamic_crit_accuracy(self, unit, item, target, item2, mode, attack_info, base_value):
        return int(self.value['crit']) if self._flying(target) else 0

    def stat_change(self, unit):
        return {'SKL': int(self.value['isolated_skl'])} if not _class_adjacent_flying_allies(unit) else {}

    def start_combat(self, playback, unit, item, target, item2, mode):
        status = self.value['magic_block_status']
        if (status and self._flying(target) and item
                and item_funcs.is_magic_in_combat(unit, item, target)
                and not any(skill.nid == status for skill in unit.skills)):
            action.do(action.AddSkill(unit, status, unit))


class ClassRangedDefense(SkillComponent):
    nid = 'class_ranged_defense'
    desc = 'Grants configured Avoid and optionally reduces foe Hit at range two or greater.'
    tag = SkillTags.CUSTOM
    expose = ComponentType.NewMultipleOptions
    options = {'avoid': ComponentType.Int, 'foe_hit_penalty': ComponentType.Int}
    value = {'avoid': 0, 'foe_hit_penalty': 0}

    def __init__(self, value=None):
        self.value = self.value.copy()
        if value:
            self.value.update(value)

    @staticmethod
    def _active(unit, target):
        return bool(unit and target and unit.position and target.position and
                    utils.calculate_distance(unit.position, target.position) >= 2)

    def dynamic_avoid(self, unit, item, target, item2, mode, attack_info, base_value):
        return int(self.value['avoid']) if self._active(unit, target) and mode == 'defense' else 0

    def dynamic_accuracy(self, unit, item, target, item2, mode, attack_info, base_value):
        # This component is read from the defender in compute_hit; an Avoid
        # increase is the exact hit-probability equivalent of a foe Hit penalty.
        return 0

    def dynamic_avoid_penalty(self, unit, item, target, item2, mode, attack_info, base_value):
        return 0


class ClassMagicFoeCombatBonus(SkillComponent):
    nid = 'class_magic_foe_combat_bonus'
    desc = 'Grants configured Hit, Crit, and Avoid only against a foe using magic.'
    tag = SkillTags.CUSTOM
    expose = ComponentType.NewMultipleOptions
    options = {'hit': ComponentType.Int, 'crit': ComponentType.Int, 'avoid': ComponentType.Int}
    value = {'hit': 0, 'crit': 0, 'avoid': 0}

    def __init__(self, value=None):
        self.value = self.value.copy()
        if value:
            self.value.update(value)

    @staticmethod
    def _active(target, item2, unit):
        return bool(target and item2 and item_funcs.is_magic_in_combat(target, item2, unit))

    def modify_accuracy(self, unit, item):
        return int(self.value['hit'])

    def modify_crit_accuracy(self, unit, item):
        return int(self.value['crit'])

    def dynamic_avoid(self, unit, item, target, item2, mode, attack_info, base_value):
        return int(self.value['avoid']) if self._active(target, item2, unit) else 0


class ClassMagicAdvantageShift(SkillComponent):
    nid = 'class_magic_advantage_shift'
    desc = 'Adjusts magic weapon-triangle Hit and reduces foe Resistance while initiating.'
    tag = SkillTags.CUSTOM
    expose = ComponentType.NewMultipleOptions
    options = {'triangle_percent': ComponentType.Int,
               'res_reduction_percent': ComponentType.Int,
               'ignore_foe_crit_advantage': ComponentType.Bool}
    value = {'triangle_percent': 0, 'res_reduction_percent': 0,
             'ignore_foe_crit_advantage': False}

    def __init__(self, value=None):
        self.value = self.value.copy()
        if value:
            self.value.update(value)

    @staticmethod
    def _magic_user(unit, item, target):
        return bool(unit and item and item_funcs.is_magic_in_combat(unit, item, target))

    @staticmethod
    def _magic_foe(target, item2, unit):
        return bool(target and item2 and item_funcs.is_magic_in_combat(target, item2, unit))

    def dynamic_accuracy(self, unit, item, target, item2, mode, attack_info, base_value):
        if not self._magic_foe(target, item2, unit):
            return 0
        advantage = combat_calcs.compute_advantage(unit, target, item, item2)
        return int(round(max(0, getattr(advantage, 'hit', 0)) *
                         self.value['triangle_percent'] / 100))

    def dynamic_avoid(self, unit, item, target, item2, mode, attack_info, base_value):
        if not self._magic_foe(target, item2, unit):
            return 0
        advantage = combat_calcs.compute_advantage(target, unit, item2, item)
        return int(round(max(0, getattr(advantage, 'hit', 0)) *
                         self.value['triangle_percent'] / 100))

    def dynamic_damage(self, unit, item, target, item2, mode, attack_info, base_value):
        if mode != 'attack' or not target or not self._magic_user(unit, item, target):
            return 0
        return int(round(target.get_stat('RES') *
                         self.value['res_reduction_percent'] / 100))

    def dynamic_crit_avoid(self, unit, item, target, item2, mode, attack_info, base_value):
        if not self.value['ignore_foe_crit_advantage'] or not self._magic_foe(target, item2, unit):
            return 0
        advantage = combat_calcs.compute_advantage(target, unit, item2, item)
        return int(max(0, getattr(advantage, 'crit', 0)))


class ClassLowHpFollowUp(SkillComponent):
    nid = 'class_low_hp_follow_up'
    desc = 'Grants one normal follow-up phase while below the configured HP percent.'
    tag = SkillTags.CUSTOM
    expose = ComponentType.Int
    value = 0

    def dynamic_attacks(self, unit, item, target, item2, mode, attack_info):
        if unit and unit.get_max_hp() and unit.get_hp() * 100 < unit.get_max_hp() * self.value:
            return 1
        return 0


class ClassPathDamnedSummon(SkillComponent):
    nid = 'class_path_damned_summon'
    desc = 'At upkeep, spends 10 HP to trigger the existing Phantom summon contract.'
    tag = SkillTags.CUSTOM
    expose = ComponentType.Event
    value = 'Global Summon Phantom 2'

    def on_upkeep(self, actions, playback, unit):
        if not unit or unit.position is None or unit.get_hp() < 20:
            return
        positions = [pos for pos in game.target_system.get_adjacent_positions(unit.position)
                     if not game.board.get_unit(pos)]
        if not positions:
            return
        game.events.trigger_specific_event(self.value, unit, unit, unit.position,
                                           {'target_pos': positions[0]})


class RandomStatChange(SkillComponent):
    nid = 'random_stat_change'
    desc = 'Chooses one configured stat once when the status is created and changes it.'
    tag = SkillTags.CUSTOM
    expose = ComponentType.NewMultipleOptions
    options = {'amount': ComponentType.Int, 'stats': (ComponentType.List, ComponentType.Stat)}
    value = {'amount': 0, 'stats': []}

    def __init__(self, value=None):
        self.value = self.value.copy()
        if value:
            self.value.update(value)

    def init(self, skill):
        stats = tuple(self.value['stats'])
        if stats and 'random_stat_change_stat' not in skill.data:
            skill.data['random_stat_change_stat'] = stats[static_random.get_combat() % len(stats)]

    def stat_change(self, unit):
        stat = self.skill.data.get('random_stat_change_stat')
        return {stat: int(self.value['amount'])} if stat else {}


class ClassBattlecryCharge(SkillComponent):
    nid = 'class_battlecry_charge'
    desc = 'Deals 10% more final damage while initiating against a foe with more HP.'
    tag = SkillTags.CUSTOM

    def damage_multiplier(self, unit, item, target, item2, mode, attack_info, base_value):
        if mode == 'attack' and target and unit.get_hp() < target.get_hp():
            return 1.1
        return 1


class ClassRapidAssault(SkillComponent):
    nid = 'class_rapid_assault'
    desc = ('Reduces the foe\'s first attempted strike by 30% after moving at least '
            'five spaces without an adjacent ally.')
    tag = SkillTags.CUSTOM

    @staticmethod
    def _moved_far(unit):
        return bool(unit and unit.position is not None and unit.previous_position is not None
                    and utils.calculate_distance(unit.previous_position, unit.position) >= 5)

    def resist_multiplier(self, unit, item, target, item2, mode, attack_info, base_value):
        if (mode == 'defense' and attack_info == (0, 0)
                and self._moved_far(unit) and not _class_adjacent_allies(unit)):
            return .7
        return 1


class ClassSolidShield(SkillComponent):
    nid = 'class_solid_shield'
    desc = ('Reduces the foe\'s first attempted strike by 30% with two adjacent '
            'mounted or armored allies.')
    tag = SkillTags.CUSTOM

    def resist_multiplier(self, unit, item, target, item2, mode, attack_info, base_value):
        formation = [candidate for candidate in _class_adjacent_allies(unit)
                     if 'Horse' in getattr(candidate, 'tags', ())
                     or 'Armor' in getattr(candidate, 'tags', ())]
        if mode == 'defense' and attack_info == (0, 0) and len(formation) >= 2:
            return .7
        return 1


class ClassPrecisionVolley(SkillComponent):
    nid = 'class_precision_volley'
    desc = 'Grants +30 Critical while the user has not moved this turn.'
    tag = SkillTags.CUSTOM

    def dynamic_crit_accuracy(self, unit, item, target, item2, mode, attack_info, base_value):
        if (mode == 'attack' and unit and unit.position is not None
                and unit.previous_position == unit.position):
            return 30
        return 0


class ClassPhalanxFormation(SkillComponent):
    nid = 'class_phalanx_formation'
    desc = ('At upkeep, enables the configured Phalanx effect for the user and '
            'adjacent armored allies when the user has two such allies adjacent.')
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {'status': ComponentType.Skill, 'rank': ComponentType.Int}
    value = {'status': 'Class_Phalanx_Formation_Effect', 'rank': 1}

    def __init__(self, value=None):
        self.value = self.value.copy()
        if value:
            self.value.update(value)

    @staticmethod
    def _valid(unit):
        return bool(unit and unit.position is not None and not getattr(unit, 'dead', False)
                    and not getattr(unit, 'is_dying', False) and unit.get_hp() > 0
                    and 'Tile' not in getattr(unit, 'tags', ()))

    @staticmethod
    def _armored(unit):
        return 'Armor' in getattr(unit, 'tags', ())

    def _is_highest(self, unit):
        candidates = [component for skill in unit.skills for component in skill.components
                      if component.nid == self.nid]
        return bool(candidates and max(candidates, key=lambda component: component.value['rank']) is self)

    def _formation_targets(self, unit):
        if not self._valid(unit) or not self._armored(unit):
            return []
        adjacent = [target for target in game.get_all_units()
                    if target is not unit and self._valid(target) and self._armored(target)
                    and skill_system.check_ally(unit, target)
                    and utils.calculate_distance(unit.position, target.position) == 1]
        return [unit, *adjacent] if len(adjacent) >= 2 else []

    def _queue_effect(self, actions, target, owner):
        status = self.value['status']
        existing = [skill for skill in target.skills if skill.nid == status]
        existing_rank = max((skill.data.get('rank', 0) for skill in existing), default=0)
        queued = [queued for queued in actions
                  if isinstance(queued, action.AddSkill) and queued.unit is target
                  and queued.skill_obj and queued.skill_obj.nid == status]
        queued_rank = max((queued.skill_obj.data.get('rank', 0) for queued in queued), default=0)
        if max(existing_rank, queued_rank) >= self.value['rank']:
            return
        actions[:] = [queued_action for queued_action in actions
                      if not (isinstance(queued_action, action.AddSkill)
                              and queued_action.unit is target and queued_action.skill_obj
                              and queued_action.skill_obj.nid == status)]
        actions.extend(action.RemoveSkill(target, skill) for skill in existing)
        add_status = action.AddSkill(target, status, owner)
        if add_status.skill_obj:
            add_status.skill_obj.data['rank'] = self.value['rank']
            actions.append(add_status)

    def on_upkeep(self, actions, playback, unit):
        if not self._is_highest(unit):
            return
        for target in self._formation_targets(unit):
            self._queue_effect(actions, target, unit)


class ClassPhalanxRedirect(SkillComponent):
    nid = 'class_phalanx_redirect'
    desc = ('For each ten incoming combat damage, redirects one damage to the '
            'healthiest adjacent armored ally as non-combat damage without killing it.')
    tag = SkillTags.CUSTOM

    @staticmethod
    def _valid_armored_ally(unit, candidate):
        return bool(candidate is not unit and candidate and candidate.position is not None
                    and not getattr(candidate, 'dead', False) and not getattr(candidate, 'is_dying', False)
                    and candidate.get_hp() > 1 and 'Armor' in getattr(candidate, 'tags', ())
                    and skill_system.check_ally(unit, candidate)
                    and utils.calculate_distance(unit.position, candidate.position) == 1)

    def after_take_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        incoming = next((act for act in reversed(actions)
                         if isinstance(act, action.ChangeHP) and act.unit is unit and act.num < 0), None)
        if not incoming:
            return
        redirected = (-incoming.num) // 10
        if not redirected:
            return
        candidates = [candidate for candidate in game.get_all_units()
                      if self._valid_armored_ally(unit, candidate)]
        if not candidates:
            return
        recipient = max(candidates, key=lambda candidate: candidate.get_hp())
        redirected = min(redirected, recipient.get_hp() - 1)
        if redirected <= 0:
            return
        incoming.num += redirected
        actions.append(action.ChangeHP(recipient, -redirected))


class ClassFormationCritAvoid(SkillComponent):
    nid = 'class_formation_crit_avoid'
    desc = 'Grants +10 Critical Avoid while the temporary armored formation is active.'
    tag = SkillTags.CUSTOM

    def modify_crit_avoid(self, unit, item):
        return 10


class ClassSiegeBreakerFirstStrike(SkillComponent):
    nid = 'class_siege_breaker_first_strike'
    desc = 'Adds 5% final outgoing damage to the recipient\'s first attempted strike this turn.'
    tag = SkillTags.CUSTOM
    _data_key = 'siege_breaker_consumed'

    def init(self, skill):
        skill.data.setdefault(self._data_key, False)

    def on_upkeep(self, actions, playback, unit):
        if self.skill.data.get(self._data_key):
            action.do(action.SetObjData(self.skill, self._data_key, False))

    def damage_multiplier(self, unit, item, target, item2, mode, attack_info, base_value):
        return 1.05 if mode == 'attack' and not self.skill.data[self._data_key] else 1

    def after_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        if mode == 'attack' and not self.skill.data[self._data_key]:
            action.do(action.SetObjData(self.skill, self._data_key, True))


class MenaceAtUpkeep(SkillComponent):
    nid = 'menace_at_upkeep'
    desc = 'At upkeep, inflicts a status on nearby foes and grants another to the user if any foe exists.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {
        'foe_status': ComponentType.Skill,
        'user_status': ComponentType.Skill,
        'range': ComponentType.Int,
    }

    def __init__(self, value=None):
        self.value = {'foe_status': None, 'user_status': None, 'range': 4}
        if value:
            self.value.update(value)

    def on_upkeep(self, actions, playback, unit):
        if not ThreatenFoesAtUpkeep._valid_target(unit):
            return
        foes = [foe for foe in game.get_all_units()
                if foe is not unit and ThreatenFoesAtUpkeep._valid_target(foe)
                and skill_system.check_enemy(unit, foe)
                and 1 <= utils.calculate_distance(unit.position, foe.position) <= self.value['range']]
        if not foes:
            return
        for foe in foes:
            if not ThreatenFoesAtUpkeep._has_status(foe, self.value['foe_status'], actions):
                actions.append(action.AddSkill(foe, self.value['foe_status'], unit))
        if not ThreatenFoesAtUpkeep._has_status(unit, self.value['user_status'], actions):
            actions.append(action.AddSkill(unit, self.value['user_status'], unit))


class ThreatenPenalty(SkillComponent):
    nid = 'threaten_penalty'
    desc = 'Applies only the strongest Threaten penalty for each stat and damage independently.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {'stats': (ComponentType.Dict, ComponentType.Stat), 'damage': ComponentType.Int}

    def __init__(self, value=None):
        self.value = {'stats': [], 'damage': 0}
        if value:
            self.value.update(value)

    @staticmethod
    def _penalties(unit):
        return [component for skill in unit.skills if skill_system.condition(skill, unit)
                for component in skill.components
                if component.nid == 'threaten_penalty']

    @staticmethod
    def _winner(components, value):
        candidates = [(value(component), component.skill.uid, component) for component in components]
        candidates = [candidate for candidate in candidates if candidate[0] < 0]
        return min(candidates, key=lambda candidate: (candidate[0], candidate[1]))[2] \
            if candidates else None

    def stat_change(self, unit):
        result = {}
        components = self._penalties(unit)
        stat_values = dict(self.value['stats'])
        for stat, penalty in stat_values.items():
            winner = self._winner(components, lambda component, stat=stat:
                                  dict(component.value['stats']).get(stat, 0))
            if winner is self:
                result[stat] = penalty
        return result

    def modify_damage(self, unit, item):
        winner = self._winner(self._penalties(unit),
                              lambda component: component.value['damage'])
        return self.value['damage'] if winner is self else 0


class SmokeAfterCombat(SkillComponent):
    nid = 'smoke_after_combat'
    desc = 'At the highest eligible tier, gives Smoke statuses after combat around the foe and user.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {
        'group': ComponentType.String,
        'rank': ComponentType.Int,
        'requires_initiation': ComponentType.Bool,
        'foe_radius': ComponentType.Int,
        'foe_statuses': (ComponentType.List, ComponentType.Skill),
        'ally_radius': ComponentType.Int,
        'ally_statuses': (ComponentType.List, ComponentType.Skill),
    }

    def __init__(self, value=None):
        self.value = {
            'group': 'smoke', 'rank': 1, 'requires_initiation': False,
            'foe_radius': 0, 'foe_statuses': [], 'ally_radius': 0, 'ally_statuses': [],
        }
        if value:
            self.value.update(value)

    @staticmethod
    def _valid_target(target):
        return target and target.position is not None and not getattr(target, 'dead', False) \
            and not getattr(target, 'is_dying', False) and target.get_hp() > 0 \
            and 'Tile' not in getattr(target, 'tags', ())

    @staticmethod
    def _is_initiator(unit, mode):
        combat = getattr(game, 'memory', {}).get('current_combat')
        return combat.attacker is unit if combat is not None else mode == 'attack'

    def _is_winner(self, unit, mode):
        qualified = []
        for skill in unit.skills:
            if not skill_system.condition(skill, unit):
                continue
            for component in skill.components:
                if component.nid != self.nid or component.value['group'] != self.value['group']:
                    continue
                if component.value['requires_initiation'] and not self._is_initiator(unit, mode):
                    continue
                qualified.append(component)
        return bool(qualified) and max(qualified, key=lambda component: component.value['rank']) is self

    @staticmethod
    def _in_radius(center, radius, candidates):
        return [candidate for candidate in candidates
                if utils.calculate_distance(center, candidate.position) <= radius]

    @staticmethod
    def _add_status(target, status, source, skip_current_wait=False):
        add_status = action.AddSkill(target, status, source)
        if skip_current_wait and add_status.skill_obj:
            action.do(action.SetObjData(add_status.skill_obj, 'skip_current_wait', True))
        action.do(add_status)

    def end_combat(self, playback, unit, item, target, item2, mode):
        if not target or target.position is None or not skill_system.check_enemy(unit, target) \
                or not self._is_winner(unit, mode):
            return
        units = list(game.get_all_units())
        foes = [other for other in units if self._valid_target(other)
                and skill_system.check_enemy(unit, other)]
        if self._valid_target(target) and target not in foes:
            foes.insert(0, target)
        foes = self._in_radius(target.position, self.value['foe_radius'], foes)
        combat = getattr(game, 'memory', {}).get('current_combat')
        skip_primary_wait = mode == 'defense' and combat is not None \
            and combat.finalizes_turn and not combat.event_combat
        for foe in foes:
            for status in self.value['foe_statuses']:
                self._add_status(foe, status, unit, foe is target and skip_primary_wait)

        if not self._valid_target(unit) or not self.value['ally_statuses']:
            return
        allies = [other for other in units if self._valid_target(other)
                  and skill_system.check_ally(unit, other)]
        if unit not in allies:
            allies.insert(0, unit)
        for ally in self._in_radius(unit.position, self.value['ally_radius'], allies):
            for status in self.value['ally_statuses']:
                self._add_status(ally, status, unit)


class FatalSmokeDuringCombat(SkillComponent):
    nid = 'fatal_smoke_during_combat'
    desc = 'At the highest eligible tier, blocks the primary foe from recovering HP during combat.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {'group': ComponentType.String, 'rank': ComponentType.Int,
               'requires_initiation': ComponentType.Bool, 'status': ComponentType.Skill}

    def __init__(self, value=None):
        self.value = {'group': 'fatal_smoke', 'rank': 1, 'requires_initiation': False,
                      'status': 'Fatal_Smoke_Combat_Effect'}
        if value:
            self.value.update(value)

    def _is_winner(self, unit, mode):
        qualified = []
        for skill in unit.skills:
            if not skill_system.condition(skill, unit):
                continue
            for component in skill.components:
                if component.nid != self.nid or component.value['group'] != self.value['group']:
                    continue
                if component.value['requires_initiation'] and not SmokeAfterCombat._is_initiator(unit, mode):
                    continue
                qualified.append(component)
        return bool(qualified) and max(qualified, key=lambda component: component.value['rank']) is self

    def pre_combat(self, playback, unit, item, target, item2, mode):
        if not SmokeAfterCombat._valid_target(target) or not skill_system.check_enemy(unit, target) \
                or not self._is_winner(unit, mode):
            return
        action.do(action.AddSkill(target, self.value['status'], unit))


class SmokePenalty(SkillComponent):
    nid = 'smoke_penalty'
    desc = 'Applies only the strongest Smoke penalty for each stat and damage independently.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {'stats': (ComponentType.Dict, ComponentType.Stat), 'damage': ComponentType.Int}

    def __init__(self, value=None):
        self.value = {'stats': [], 'damage': 0}
        if value:
            self.value.update(value)

    @staticmethod
    def _penalties(unit):
        return [component for skill in unit.skills if skill_system.condition(skill, unit)
                for component in skill.components if component.nid == 'smoke_penalty']

    @staticmethod
    def _winner(components, value):
        candidates = [(value(component), getattr(component.skill, 'uid', 0), component)
                      for component in components]
        candidates = [candidate for candidate in candidates if candidate[0] < 0]
        return min(candidates, key=lambda candidate: (candidate[0], candidate[1]))[2] \
            if candidates else None

    def stat_change(self, unit):
        result = {}
        components = self._penalties(unit)
        for stat, penalty in dict(self.value['stats']).items():
            winner = self._winner(components, lambda component, stat=stat:
                                  dict(component.value['stats']).get(stat, 0))
            if winner is self:
                result[stat] = penalty
        return result

    def modify_damage(self, unit, item):
        winner = self._winner(self._penalties(unit), lambda component: component.value['damage'])
        return self.value['damage'] if winner is self else 0


class SmokePanicBonusConversion(SkillComponent):
    nid = 'smoke_panic_bonus_conversion'
    desc = 'Converts the owner\'s current net positive bonuses into penalties.'
    tag = SkillTags.CUSTOM

    _stats = ('STR', 'MAG', 'SKL', 'SPD', 'LCK', 'DEF', 'RES')

    def stat_bonus_adjustment(self, unit, stat_nid, base_value):
        return -2 * max(0, base_value) if stat_nid in self._stats else 0


class SmokeBlockHPRecovery(SkillComponent):
    nid = 'smoke_block_hp_recovery'
    desc = 'Prevents the owner from recovering HP.'
    tag = SkillTags.CUSTOM

    def block_hp_recovery(self, unit):
        return True


class SmokeBlockDeathPrevention(SkillComponent):
    nid = 'smoke_block_death_prevention'
    desc = 'Prevents the owner from activating death-prevention effects.'
    tag = SkillTags.CUSTOM

    def block_death_prevention(self, unit):
        return True


class AdaptiveDamage(SkillComponent):
    nid = 'adaptive_damage'
    desc = 'Uses the lower of the foe\'s Defense or Resistance for damage calculation.'
    tag = SkillTags.COMBAT

    def adaptive_damage(self, unit):
        return True


class NeutralizeFoeAdaptiveDamage(SkillComponent):
    nid = 'neutralize_foe_adaptive_damage'
    desc = 'Neutralizes the foe\'s adaptive damage effect.'
    tag = SkillTags.COMBAT

    def neutralize_foe_adaptive_damage(self, unit):
        return True


class BreathAdjacentHeal(SkillComponent):
    nid = 'breath_adjacent_heal'
    desc = 'Heals adjacent living allies at upkeep and/or after initiated combat.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {
        'upkeep_heal': ComponentType.Int,
        'post_combat_heal': ComponentType.Int,
    }

    def __init__(self, value=None):
        self.value = {
            'upkeep_heal': 0,
            'post_combat_heal': 0,
        }
        if value:
            self.value.update(value)

    @staticmethod
    def _valid_target(unit):
        return unit and unit.position is not None and not getattr(unit, 'dead', False) \
            and not getattr(unit, 'is_dying', False) and 'Tile' not in getattr(unit, 'tags', ())

    def _adjacent_injured_allies(self, unit):
        if not unit or unit.position is None:
            return []
        targets = []
        for position in game.target_system.get_adjacent_positions(unit.position):
            target = game.board.get_unit(position)
            if target is unit or not self._valid_target(target):
                continue
            if skill_system.check_ally(unit, target) and target.get_hp() < target.get_max_hp():
                targets.append(target)
        return targets

    def on_upkeep(self, actions, playback, unit):
        heal_amount = self.value['upkeep_heal']
        if heal_amount <= 0:
            return
        for target in self._adjacent_injured_allies(unit):
            actions.append(action.ChangeHP(target, heal_amount))

    def end_combat(self, playback, unit, item, target, item2, mode):
        heal_amount = self.value['post_combat_heal']
        if mode != 'attack' or heal_amount <= 0 or not unit or unit.position is None:
            return
        if not target or not skill_system.check_enemy(unit, target):
            return
        for ally in self._adjacent_injured_allies(unit):
            action.do(action.ChangeHP(ally, heal_amount))


class _SelfStatusAtUpkeep(SkillComponent):
    nid = None
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {
        'status': ComponentType.Skill,
        'group': ComponentType.String,
        'rank': ComponentType.Int,
    }

    def __init__(self, value=None):
        self.value = {'status': None, 'group': '', 'rank': 0}
        if value:
            self.value.update(value)

    @staticmethod
    def _valid_living_unit(unit):
        if not unit or unit.position is None or getattr(unit, 'dead', False) \
                or getattr(unit, 'is_dying', False) or 'Tile' in getattr(unit, 'tags', ()):
            return False
        return not hasattr(unit, 'get_hp') or unit.get_hp() > 0

    @staticmethod
    def _has_status(unit, status, actions):
        if any(skill.nid == status for skill in unit.skills):
            return True
        return any(getattr(queued, 'unit', None) is unit
                   and getattr(getattr(queued, 'skill_obj', None), 'nid', None) == status
                   for queued in actions)

    def _is_highest_active_rank(self, unit):
        for skill in unit.skills:
            if not skill_system.condition(skill, unit):
                continue
            for component in skill.components:
                if component is self or component.nid != self.nid:
                    continue
                if component.value['group'] == self.value['group'] \
                        and component.value['rank'] > self.value['rank']:
                    return False
        return True

    def _should_gain_status(self, unit):
        raise NotImplementedError

    def on_upkeep(self, actions, playback, unit):
        if not self._valid_living_unit(unit) or not self.value['status'] \
                or not self._is_highest_active_rank(unit):
            return
        if self._should_gain_status(unit) and not self._has_status(unit, self.value['status'], actions):
            actions.append(action.AddSkill(unit, self.value['status'], unit))


class RouseSelfAtUpkeep(_SelfStatusAtUpkeep):
    nid = 'rouse_self_at_upkeep'
    desc = 'At upkeep, grants the user a status when no valid ally is adjacent.'

    def _should_gain_status(self, unit):
        return not any(
            other is not unit and self._valid_living_unit(other)
            and skill_system.check_ally(unit, other)
            and utils.calculate_distance(unit.position, other.position) == 1
            for other in game.get_all_units())


class OathSelfAtUpkeep(_SelfStatusAtUpkeep):
    nid = 'oath_self_at_upkeep'
    desc = 'At upkeep, grants the user a status when a valid ally is within range.'

    options = {
        **_SelfStatusAtUpkeep.options,
        'range': ComponentType.Int,
    }

    def __init__(self, value=None):
        super().__init__(value)
        self.value.setdefault('range', 1)

    def _should_gain_status(self, unit):
        return any(
            other is not unit and self._valid_living_unit(other)
            and skill_system.check_ally(unit, other)
            and 1 <= utils.calculate_distance(unit.position, other.position) <= self.value['range']
            for other in game.get_all_units())


class _StrongestFamilyBonus(SkillComponent):
    nid = None
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {'stats': (ComponentType.Dict, ComponentType.Stat), 'damage': ComponentType.Int}

    def __init__(self, value=None):
        self.value = {'stats': [], 'damage': 0}
        if value:
            self.value.update(value)

    def _bonuses(self, unit):
        return [component for skill in unit.skills if skill_system.condition(skill, unit)
                for component in skill.components if component.nid == self.nid]

    @staticmethod
    def _winner(components, value):
        candidates = [(value(component), component.skill.uid, component) for component in components]
        candidates = [candidate for candidate in candidates if candidate[0] > 0]
        return min(candidates, key=lambda candidate: (-candidate[0], candidate[1]))[2] \
            if candidates else None

    def stat_change(self, unit):
        result = {}
        for stat, bonus in self.value['stats']:
            winner = self._winner(self._bonuses(unit),
                                  lambda component: dict(component.value['stats']).get(stat, 0))
            if winner is self:
                result[stat] = bonus
        return result

    def modify_damage(self, unit, item):
        winner = self._winner(self._bonuses(unit), lambda component: component.value['damage'])
        return self.value['damage'] if winner is self else 0


class RouseBonus(_StrongestFamilyBonus):
    nid = 'rouse_bonus'
    desc = 'Applies only the strongest positive Rouse bonus for each stat and damage independently.'


class OathBonus(_StrongestFamilyBonus):
    nid = 'oath_bonus'
    desc = 'Applies only the strongest positive Oath bonus for each stat and damage independently.'


class ReinPenalty(SkillComponent):
    nid = 'rein_penalty'
    desc = 'Applies the highest-ranked Rein penalty from each owner and line.'
    tag = SkillTags.CUSTOM

    expose = ComponentType.NewMultipleOptions
    options = {
        'group': ComponentType.String,
        'rank': ComponentType.Int,
        'stats': (ComponentType.Dict, ComponentType.Stat),
        'damage': ComponentType.Int,
    }

    def __init__(self, value=None):
        self.value = {'group': '', 'rank': 0, 'stats': [], 'damage': 0}
        if value:
            self.value.update(value)

    @staticmethod
    def _owner_nid(component):
        parent = getattr(component.skill, 'parent_skill', None)
        return getattr(parent, 'owner_nid', None)

    @staticmethod
    def _tie_key(component):
        parent = getattr(component.skill, 'parent_skill', None)
        return (getattr(parent, 'uid', 0), getattr(component.skill, 'uid', 0))

    def _is_winner(self, unit):
        owner_nid = self._owner_nid(self)
        candidates = [
            component for skill in unit.skills if skill_system.condition(skill, unit)
            for component in skill.components
            if component.nid == self.nid and component.value['group'] == self.value['group']
            and self._owner_nid(component) == owner_nid
        ]
        if not candidates:
            return False
        highest_rank = max(component.value['rank'] for component in candidates)
        return min((component for component in candidates
                    if component.value['rank'] == highest_rank), key=self._tie_key) is self

    def stat_change(self, unit):
        return dict(self.value['stats']) if self._is_winner(unit) else {}

    def modify_damage(self, unit, item):
        return self.value['damage'] if self._is_winner(unit) else 0
