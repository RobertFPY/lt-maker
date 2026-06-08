from app.engine.objects.unit import UnitObject
from app.data.database.skill_components import SkillComponent, SkillTags
from app.data.database.components import ComponentType

from app.engine import action
from app.engine.game_state import game
from app.engine.combat import playback as pb

class DeathTether(SkillComponent):
    nid = 'death_tether'
    desc = "Remove all skills in the game that I initiated on my death"
    tag = SkillTags.ADVANCED

    def on_death(self, unit):
        for other_unit in game.units:
            for skill in other_unit.skills:
                if skill.initiator_nid == unit.nid:
                    action.do(action.RemoveSkill(other_unit, skill))

class Oversplash(SkillComponent):
    nid = 'oversplash'
    desc = "Grants unit +X area of effect for regular and blast items"
    tag = SkillTags.ADVANCED

    expose = ComponentType.Int
    value = 1

    def empower_splash(self, unit):
        return self.value

    def alternate_splash(self, unit):
        from app.engine.item_components.aoe_components import BlastAOE
        return BlastAOE(0)

class EnemyOversplash(Oversplash):
    nid = 'enemy_oversplash'
    desc = "Grants unit +X area of effect for regular and blast items that only affects enemies"

    def alternate_splash(self, unit):
        from app.engine.item_components.aoe_components import EnemyBlastAOE
        return EnemyBlastAOE(0)

class SmartOversplash(Oversplash):
    nid = 'smart_oversplash'
    desc = """
        Grants unit +X area of effect for regular and blast items. If the main target is an enemy, then splash will only affect enemies. 
        The same holds true for allies.
        """

    def alternate_splash(self, unit):
        from app.engine.item_components.aoe_components import SmartBlastAOE
        return SmartBlastAOE(0)

class EmpowerHeal(SkillComponent):
    nid = 'empower_heal'
    desc = "Gives +X extra healing"
    tag = SkillTags.ADVANCED

    expose = ComponentType.String

    def empower_heal(self, unit, target):
        from app.engine import evaluate
        try:
            return int(evaluate.evaluate(self.value, unit, target, unit.position, local_args={'skill': self.skill}))
        except:
            print("Couldn't evaluate %s conditional" % self.value)
            return 0

class EmpowerHealReceived(SkillComponent):
    nid = 'empower_heal_received'
    desc = "Gives +X extra healing received"
    tag = SkillTags.ADVANCED

    expose = ComponentType.String

    def empower_heal_received(self, target, unit):
        from app.engine import evaluate
        try:
            return int(evaluate.evaluate(self.value, target, unit, local_args={'skill': self.skill}))
        except:
            print("Couldn't evaluate %s conditional" % self.value)
            return 0

class EmpowerMana(SkillComponent):
    nid = 'empower_mana'
    desc = "Gives +X extra mana gain"
    tag = SkillTags.ADVANCED

    expose = ComponentType.String

    def empower_mana(self, unit, target):
        from app.engine import evaluate
        try:
            return int(evaluate.evaluate(self.value, unit, target, unit.position))
        except:
            print("Couldn't evaluate %s conditional" % self.value)
            return 0

class EmpowerManaReceived(SkillComponent):
    nid = 'empower_mana_received'
    desc = "Gives +X extra mana gain received"
    tag = SkillTags.ADVANCED

    expose = ComponentType.String

    def empower_mana_received(self, target, unit):
        from app.engine import evaluate
        try:
            return int(evaluate.evaluate(self.value, target, unit))
        except:
            print("Couldn't evaluate %s conditional" % self.value)
            return 0

class ManaOnHit(SkillComponent):
    nid = 'mana_on_hit'
    desc = 'Gives +X mana on hit'
    tag = SkillTags.ADVANCED
    author = 'BigMood'

    expose = ComponentType.Int

    def mana(self, playback, unit, item, target):
        mark_playbacks = [p for p in playback if p.nid in ('mark_hit', 'mark_crit')]

        if target and any(p.defender == target for p in mark_playbacks):
            return self.value
        return 0

class ManaOnKill(SkillComponent):
    nid = 'mana_on_kill'
    desc = 'Gives +X mana on kill'
    tag = SkillTags.ADVANCED

    expose = ComponentType.Int

    def mana(self, playback, unit, item, target):
        if target and target.is_dying:
            return self.value
        return 0


class EventAfterInitiatedCombat(SkillComponent):
    nid = 'event_after_initiated_combat'
    desc = 'calls event after combat initated by user'
    tag = SkillTags.ADVANCED

    expose = ComponentType.Event
    value = ''

    def end_combat(self, playback, unit: UnitObject, item, target: UnitObject, item2, mode):
        if mode == 'attack':
            game.events.trigger_specific_event(self.value, unit, target, unit.position, {'item': item, 'item2': item2, 'mode': mode})

class ReduceToOneAndEventOnFirstHit(SkillComponent):
    nid = 'reduce_to_one_and_event_on_first_hit'
    desc = ("The first time this unit is struck by any damaging hit, the damage is reduced "
            "so the unit is left with exactly 1 HP, and for the rest of that combat the unit "
            "cannot drop below 1 HP. After that combat ends, the chosen event is triggered "
            "(unit=this unit, target=the attacker) and this skill removes itself so it only "
            "ever happens once.")
    tag = SkillTags.ADVANCED

    expose = ComponentType.Event
    value = ''

    _should_trigger_event = False

    def after_take_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        # Only react while the skill has not already done its thing.
        if self._should_trigger_event:
            # Already triggered this combat - just make sure we never die before the event.
            for act in reversed(actions):
                if isinstance(act, action.ChangeHP) and -act.num >= act.old_hp and act.unit == unit:
                    act.num = -act.old_hp + 1
            return

        did_something = False
        for act in reversed(actions):
            # Any incoming damage to this unit.
            if isinstance(act, action.ChangeHP) and act.num < 0 and act.unit == unit:
                # Leave the unit with exactly 1 HP no matter how big the hit was.
                act.num = -act.old_hp + 1
                did_something = True
                playback.append(pb.DefenseHitProc(unit, self.skill))

        if did_something:
            self._should_trigger_event = True
            actions.append(action.TriggerCharge(unit, self.skill))

    def end_combat(self, playback, unit: UnitObject, item, target: UnitObject, item2, mode):
        if self._should_trigger_event:
            self._should_trigger_event = False
            if self.value:
                game.events.trigger_specific_event(
                    self.value, unit, target, unit.position,
                    {'item': item, 'item2': item2, 'mode': mode})
            # Remove the skill so this only ever happens once.
            action.do(action.RemoveSkill(unit, self.skill))


class Nihil(SkillComponent):
    nid = 'nihil'
    desc = "Takes a list of skills as its value. If a skill from this list is present on `target`, then *this* skill does not work."
    tag = SkillTags.CUSTOM
    author = 'Eretein/rainlash'

    expose = (ComponentType.List, ComponentType.Skill)
    value = []

    ignore_conditional = True
    _condition = True

    def pre_combat(self, playback, unit, item, target, item2, mode):
        all_target_nihils = set(self.value)
        if target:
            for skill in target.skills:
                if skill.nid in all_target_nihils:
                    self._condition = False
                    return
        self._condition = True

    def post_combat_unconditional(self, playback, unit, item, target, item2, mode):
        game.on_alter_game_state()
        self._condition = True

    def condition(self, unit, item):
        return self._condition

    def test_on(self, playback, unit, item, target, item2, mode):
        game.on_alter_game_state()
        self.pre_combat(playback, unit, item, target, item2, mode)

    def test_off(self, playback, unit, item, target, item2, mode):
        game.on_alter_game_state()
        self._condition = True
