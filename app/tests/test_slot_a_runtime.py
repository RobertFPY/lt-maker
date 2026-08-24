import logging
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import action, evaluate, item_funcs
from app.engine.combat import playback as pb
from app.engine.query_engine import GameQueryEngine


PROJECT = 'Fire Emblem Tales of The Golden Knight.ltproj'


class SlotARuntimeTests(TestCase):
    @classmethod
    def setUpClass(cls):
        RESOURCES.load(PROJECT, CURRENT_SERIALIZATION_VERSION)
        DB.load(PROJECT, CURRENT_SERIALIZATION_VERSION)
    def setUp(self):
        self.user = SimpleNamespace(nid='user', team='enemy', position=(4, 4), tags=[])
        self.enemy_ally = SimpleNamespace(nid='enemy_ally', team='enemy', position=(5, 4), tags=[])
        self.enemy2_ally = SimpleNamespace(nid='enemy2_ally', team='enemy2', position=(4, 6), tags=[])
        self.foe = SimpleNamespace(nid='foe', team='player', position=(3, 4), tags=[])
        self.tile = SimpleNamespace(nid='tile', team='enemy', position=(4, 5), tags=['Tile'])
        self.off_map = SimpleNamespace(nid='off_map', team='enemy', position=None, tags=[])
        self.game = SimpleNamespace(get_all_units=lambda: [self.user, self.enemy_ally, self.enemy2_ally,
                                                            self.foe, self.tile, self.off_map])
        self.engine = GameQueryEngine(logging.Logger('slot-a'), self.game)

    def test_combat_allies_excludes_self_tiles_and_off_map_and_respects_alliance(self):
        alliance = {('enemy', 'enemy'), ('enemy', 'enemy2'), ('enemy2', 'enemy')}
        with patch('app.engine.query_engine.skill_system.check_ally',
                   side_effect=lambda left, right: (left.team, right.team) in alliance):
            self.assertEqual([self.enemy_ally], self.engine.get_combat_allies_within_distance(self.user, 1))
            self.assertEqual([self.enemy_ally, self.enemy2_ally],
                             self.engine.get_combat_allies_within_distance(self.user, 2))
        self.user.position = None
        self.assertEqual([], self.engine.get_combat_allies_within_distance(self.user, 2))

    def test_is_magic_in_combat_uses_passed_item_and_combat_distance(self):
        physical = SimpleNamespace(magic=False, magic_at_range=False)
        range_magic = SimpleNamespace(magic=False, magic_at_range=True)
        self.user.position = (0, 0)
        self.foe.position = (1, 0)
        self.assertFalse(item_funcs.is_magic_in_combat(self.user, None, self.foe))
        self.assertFalse(item_funcs.is_magic_in_combat(self.user, range_magic, self.foe))
        self.foe.position = (2, 0)
        self.assertTrue(item_funcs.is_magic_in_combat(self.user, range_magic, self.foe))
        self.assertFalse(item_funcs.is_magic_in_combat(self.user, physical, self.foe))
        self.user.position = None
        self.assertFalse(item_funcs.is_magic_in_combat(self.user, range_magic, self.foe))


    def component(self, nid, component_nid):
        return next(component for component in DB.skills.get(nid).components
                    if component.nid == component_nid)

    def eval_component(self, expression, unit, target, **local_args):
        game = SimpleNamespace(target_system=SimpleNamespace(),
                               query_engine=SimpleNamespace(func_dict={}))
        return evaluate.evaluate(expression, unit, target, unit.position,
                                 local_args=local_args, game=game)

    def test_loaded_fury_recoil_damages_owner_only_and_is_nonlethal(self):
        recoil = self.component('Fury_T1', 'recoil')
        owner = SimpleNamespace(hp=2)
        owner.get_hp = lambda: owner.hp
        owner.set_hp = lambda value: setattr(owner, 'hp', value)
        target = SimpleNamespace(hp=9)
        target.get_hp = lambda: target.hp
        target.set_hp = lambda value: setattr(target, 'hp', value)

        def apply_set_hp(act):
            if isinstance(act, action.SetHP):
                act.do()

        with patch('app.engine.skill_components.combat2_components.skill_system.check_enemy', return_value=True), \
                patch('app.engine.skill_components.combat2_components.action.do', side_effect=apply_set_hp):
            recoil.end_combat([], owner, None, target, None, 'attack')

        self.assertEqual(1, owner.hp)
        self.assertEqual(9, target.hp)

    def test_loaded_stance_t4_resist_uses_actual_item2_and_keeps_crit(self):
        unit = SimpleNamespace(position=(0, 0))
        target = SimpleNamespace(position=(2, 0))
        magic = SimpleNamespace(magic=True, magic_at_range=False)
        physical = SimpleNamespace(magic=False, magic_at_range=False)
        for nid, matching, opposite in (('Warding_Stance_T4', magic, physical),
                                        ('Steady_Stance_T4', physical, magic)):
            with self.subTest(nid=nid):
                dynamic_resist = self.component(nid, 'dynamic_resist')
                crit = self.component(nid, 'crit')
                condition = self.component(nid, 'combat_condition')
                self.assertTrue(self.eval_component(condition.value, unit, target,
                                                    item=None, item2=matching, mode='defense'))
                self.assertEqual(20, crit.value)
                self.assertEqual(6, self.eval_component(dynamic_resist.value, unit, target,
                                                        item=None, item2=matching, mode='defense'))
                self.assertEqual(0, self.eval_component(dynamic_resist.value, unit, target,
                                                        item=None, item2=opposite, mode='defense'))
                self.assertEqual(0, self.eval_component(dynamic_resist.value, unit, target,
                                                        item=None, item2=None, mode='defense'))

    def test_loaded_counter_condition_requires_actual_physical_item_at_one_or_two_range(self):
        counter = self.component('Counter_T1', 'combat_condition')
        unit = SimpleNamespace(position=(0, 0))
        target = SimpleNamespace(position=(1, 0))
        physical = SimpleNamespace(magic=False, magic_at_range=False)
        magic = SimpleNamespace(magic=True, magic_at_range=False)
        self.assertTrue(self.eval_component(counter.value, unit, target, item=None, item2=physical, mode='defense'))
        target.position = (2, 0)
        self.assertTrue(self.eval_component(counter.value, unit, target, item=None, item2=physical, mode='defense'))
        self.assertFalse(self.eval_component(counter.value, unit, target, item=None, item2=magic, mode='defense'))
        self.assertFalse(self.eval_component(counter.value, unit, target, item=None, item2=None, mode='defense'))
        target.position = (3, 0)
        self.assertFalse(self.eval_component(counter.value, unit, target, item=None, item2=physical, mode='defense'))

    def test_loaded_faire_condition_uses_passed_item_not_equipped_weapon(self):
        condition = self.component('Swordfaire_T1', 'condition')
        unit = SimpleNamespace(position=(0, 0), get_weapon=lambda: SimpleNamespace(weapon_type='Axe'))
        sword = SimpleNamespace(weapon_type='Sword', tags=[])
        axe = SimpleNamespace(weapon_type='Axe', tags=[])
        true_damage_sword = SimpleNamespace(weapon_type='Sword', tags=['TrueDamage'])
        with patch('app.engine.item_system.weapon_type', side_effect=lambda _unit, item: item.weapon_type):
            self.assertTrue(self.eval_component(condition.value, unit, self.foe, item=sword))
            self.assertFalse(self.eval_component(condition.value, unit, self.foe, item=axe))
            self.assertFalse(self.eval_component(condition.value, unit, self.foe, item=true_damage_sword))

    def test_loaded_counter_effect_lifelink_reflects_each_damage_hit_once(self):
        lifelink = self.component('Counter_Effect', 'lifelink')
        holder = SimpleNamespace(hp=20)
        holder.get_hp = lambda: holder.hp
        holder.set_hp = lambda value: setattr(holder, 'hp', value)
        target = SimpleNamespace(hp=20)
        target.get_hp = lambda: target.hp
        target.set_hp = lambda value: setattr(target, 'hp', value)

        hit_playback = [pb.DamageHit(holder, None, target, 7, 7)]
        hit_actions = []
        lifelink.after_strike(hit_actions, hit_playback, holder, None, target, None,
                              'defense', (0, 0), None)
        hit_damage = [act for act in hit_actions if isinstance(act, action.ChangeHP)]
        self.assertEqual(1, len(hit_damage))
        self.assertIs(holder, hit_damage[0].unit)
        self.assertEqual(-7, hit_damage[0].num)

        miss_actions = []
        miss_playback = [pb.MarkMiss(holder, target, holder, None)]
        lifelink.after_strike(miss_actions, miss_playback, holder, None, target, None,
                              'defense', (0, 1), None)
        self.assertEqual(20, holder.hp)
        self.assertFalse(any(isinstance(act, action.ChangeHP) and act.num < 0 for act in miss_actions))

        zero_actions = []
        zero_playback = [pb.DamageHit(holder, None, target, 0, 0)]
        lifelink.after_strike(zero_actions, zero_playback, holder, None, target, None,
                              'defense', (1, 0), None)
        self.assertEqual(20, holder.hp)
        self.assertFalse(any(isinstance(act, action.ChangeHP) and act.num < 0 for act in zero_actions))

if __name__ == '__main__':
    import unittest
    unittest.main()
