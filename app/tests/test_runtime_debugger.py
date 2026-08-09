import unittest
from dataclasses import dataclass, field
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.engine import android_runtime, save
from app.engine.objects.unit import UnitObject
from app.engine.runtime_debugger import RuntimeDebugger


@dataclass
class _FakeItem:
    nid: str
    is_accessory: bool = False
    data: dict = field(default_factory=dict)
    owner_nid: str = None

    def change_owner(self, owner_nid) -> None:
        self.owner_nid = owner_nid


class RuntimeDebuggerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.unit = UnitObject('DebugUnit')
        self.unit.can_equip = lambda item: True
        self.items = {}
        self.patches = [
            patch(
                'app.engine.runtime_debugger.item_funcs.create_item',
                side_effect=lambda unit, nid: self.items.get(nid)),
            patch(
                'app.engine.runtime_debugger.action.do',
                side_effect=lambda action_obj: action_obj.do()),
            patch('app.engine.runtime_debugger.game.register_item'),
            patch('app.engine.runtime_debugger.game.unregister_item'),
            patch('app.engine.runtime_debugger.game.on_alter_game_state'),
            patch(
                'app.engine.objects.unit.item_funcs.get_all_items',
                side_effect=lambda unit: list(unit.items)),
            patch(
                'app.engine.objects.unit.item_system.is_accessory',
                side_effect=lambda unit, item: item.is_accessory),
            patch('app.engine.objects.unit.item_system.on_add_item'),
            patch('app.engine.objects.unit.item_system.on_equip_item'),
            patch('app.engine.objects.unit.item_system.on_unequip_item'),
            patch('app.engine.objects.unit.skill_system.on_add_item'),
            patch('app.engine.objects.unit.skill_system.on_equip_item'),
            patch('app.engine.objects.unit.skill_system.on_unequip_item'),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        android_runtime.set_android_touch_consumer(None)

    def test_give_weapon_autoequips_when_weapon_slot_is_empty(self) -> None:
        weapon = _FakeItem('DebugSword')
        self.items[weapon.nid] = weapon

        self.assertTrue(RuntimeDebugger.give_item(self.unit, weapon.nid))

        self.assertIn(weapon, self.unit.items)
        self.assertIs(self.unit.equipped_weapon, weapon)
        self.assertIsNone(self.unit.equipped_accessory)

    def test_give_accessory_autoequips_when_accessory_slot_is_empty(self) -> None:
        accessory = _FakeItem('DebugAccessory', is_accessory=True)
        self.items[accessory.nid] = accessory

        self.assertTrue(RuntimeDebugger.give_item(self.unit, accessory.nid))

        self.assertIn(accessory, self.unit.items)
        self.assertIs(self.unit.equipped_accessory, accessory)
        self.assertIsNone(self.unit.equipped_weapon)

    def test_give_item_does_not_replace_existing_equipment(self) -> None:
        equipped_weapon = _FakeItem('EquippedSword')
        equipped_accessory = _FakeItem('EquippedAccessory', is_accessory=True)
        new_weapon = _FakeItem('NewSword')
        new_accessory = _FakeItem('NewAccessory', is_accessory=True)
        self.unit.items = [equipped_weapon, equipped_accessory]
        self.unit.equipped_weapon = equipped_weapon
        self.unit.equipped_accessory = equipped_accessory
        self.items = {
            new_weapon.nid: new_weapon,
            new_accessory.nid: new_accessory,
        }

        self.assertTrue(RuntimeDebugger.give_item(self.unit, new_weapon.nid))
        self.assertTrue(RuntimeDebugger.give_item(self.unit, new_accessory.nid))

        self.assertIs(self.unit.equipped_weapon, equipped_weapon)
        self.assertIs(self.unit.equipped_accessory, equipped_accessory)

    def test_go_to_chapter_queues_target_and_win_as_one_event(self) -> None:
        with patch('app.engine.runtime_debugger.DB.levels', {'Next': object()}), \
                patch('app.engine.runtime_debugger.DB.difficulty_modes', {'Hard': object()}), \
                patch.object(RuntimeDebugger, '_queue_event') as queue_event:
            self.assertTrue(RuntimeDebugger.go_to_chapter('Next', 'Hard'))

        queue_event.assert_called_once_with(
            'set_difficulty_mode;Hard\nset_next_chapter;Next\nwin_game')

    def test_go_to_current_chapter_does_not_queue_an_event(self) -> None:
        fake_game = SimpleNamespace(level=SimpleNamespace(nid='Current'))
        with patch('app.engine.runtime_debugger.game', fake_game), \
                patch('app.engine.runtime_debugger.DB.levels', {'Current': object()}), \
                patch('app.engine.runtime_debugger.DB.difficulty_modes', {'Normal': object()}), \
                patch.object(RuntimeDebugger, '_queue_event') as queue_event:
            self.assertFalse(RuntimeDebugger.go_to_chapter('Current', 'Normal'))

        queue_event.assert_not_called()

    def test_go_to_unknown_chapter_does_not_queue_an_event(self) -> None:
        with patch('app.engine.runtime_debugger.DB.levels', {}), \
                patch('app.engine.runtime_debugger.DB.difficulty_modes', {'Normal': object()}), \
                patch.object(RuntimeDebugger, '_queue_event') as queue_event:
            self.assertFalse(RuntimeDebugger.go_to_chapter('Missing', 'Normal'))

        queue_event.assert_not_called()

    def test_go_to_chapter_with_unknown_difficulty_does_not_queue_an_event(self) -> None:
        with patch('app.engine.runtime_debugger.DB.levels', {'Next': object()}), \
                patch('app.engine.runtime_debugger.DB.difficulty_modes', {}), \
                patch.object(RuntimeDebugger, '_queue_event') as queue_event:
            self.assertFalse(RuntimeDebugger.go_to_chapter('Next', 'Missing'))

        queue_event.assert_not_called()

    def test_auto_level_increases_selected_unit_by_one_level(self) -> None:
        self.unit.level = 3
        with patch('app.engine.runtime_debugger.DB.classes.get', return_value=type('Klass', (), {'max_level': 20})()), \
                patch('app.engine.runtime_debugger.action.AutoLevel') as auto_level, \
                patch('app.engine.runtime_debugger.action.SetLevel') as set_level:
            RuntimeDebugger.auto_level_unit(self.unit)

        auto_level.assert_called_once_with(self.unit, 1)
        set_level.assert_called_once_with(self.unit, 4)

    def test_restart_chapter_restores_the_start_snapshot_before_loading_the_level(self) -> None:
        snapshot = {'units': ['at-chapter-start']}
        level = SimpleNamespace(nid='Chapter1')
        fake_game = SimpleNamespace(
            level=level,
            chapter_start_snapshot=snapshot,
            build_new=MagicMock(),
            load=MagicMock(),
            start_level=MagicMock(),
        )
        hard_mode = object()
        with patch('app.engine.runtime_debugger.game', fake_game), \
                patch('app.engine.runtime_debugger.DB.difficulty_modes', {'Hard': hard_mode}), \
                patch('app.engine.save.set_next_uids') as set_next_uids:
            self.assertTrue(RuntimeDebugger.restart_chapter('Hard'))

        fake_game.build_new.assert_not_called()
        context = fake_game.load.call_args.kwargs['load_context']
        self.assertEqual(save.LoadDestination.RESTART_LEVEL,
                         context.destination)
        self.assertEqual('Chapter1', context.level_nid)
        self.assertEqual('Hard', context.difficulty_mode_nid)
        fake_game.load.assert_called_once_with(snapshot, load_context=context)
        set_next_uids.assert_not_called()
        fake_game.start_level.assert_not_called()

    def test_restart_chapter_releases_android_debugger_touch_capture(self) -> None:
        snapshot = {'units': ['at-chapter-start']}
        fake_game = SimpleNamespace(
            level=SimpleNamespace(nid='Chapter1'),
            chapter_start_snapshot=snapshot,
            build_new=MagicMock(),
            load=MagicMock(),
            start_level=MagicMock(),
        )
        android_runtime.set_android_touch_consumer(
            lambda _phase, _position, _finger: True,
            passthrough_buttons=('UP', 'DOWN', 'LEFT', 'RIGHT'),
        )

        with patch('app.engine.runtime_debugger.game', fake_game), \
                patch('app.engine.runtime_debugger.DB.difficulty_modes', {'Hard': object()}), \
                patch('app.engine.save.set_next_uids'), \
                patch('app.engine.objects.difficulty_mode.DifficultyModeObject.from_prefab',
                      return_value='hard-mode'):
            self.assertTrue(RuntimeDebugger.restart_chapter('Hard'))

        self.assertFalse(android_runtime.is_android_touch_consumer_active())
        self.assertEqual(
            frozenset(), android_runtime.get_android_touch_passthrough_buttons())

    def test_restart_chapter_requires_a_start_snapshot(self) -> None:
        fake_game = SimpleNamespace(level=SimpleNamespace(nid='Chapter1'),
                                    chapter_start_snapshot=None, current_save_slot=None)
        with patch('app.engine.runtime_debugger.game', fake_game), \
                patch('app.engine.runtime_debugger.DB.difficulty_modes', {'Hard': object()}):
            self.assertFalse(RuntimeDebugger.restart_chapter('Hard'))

    def test_restart_chapter_uses_saved_restart_point_after_loading_a_game(self) -> None:
        fake_game = SimpleNamespace(
            level=SimpleNamespace(nid='Chapter1'), chapter_start_snapshot=None,
            current_save_slot=2, start_level=MagicMock(),
        )
        restart_slot = SimpleNamespace(kind='start')
        with patch('app.engine.runtime_debugger.game', fake_game), \
                patch('app.engine.runtime_debugger.DB.difficulty_modes', {'Hard': object()}), \
                patch('app.engine.save.RESTART_SLOTS', [None, None, restart_slot]), \
                patch('app.engine.save.load_game') as load_game, \
                patch('app.engine.save.set_next_uids') as set_next_uids, \
                patch('app.engine.objects.difficulty_mode.DifficultyModeObject.from_prefab',
                      return_value='hard-mode'):
            self.assertTrue(RuntimeDebugger.restart_chapter('Hard'))

        context = load_game.call_args.kwargs['context']
        self.assertEqual(save.LoadDestination.RESTART_LEVEL,
                         context.destination)
        self.assertEqual('Chapter1', context.level_nid)
        self.assertEqual('Hard', context.difficulty_mode_nid)
        load_game.assert_called_once_with(
            fake_game, restart_slot, context=context)
        set_next_uids.assert_not_called()
        fake_game.start_level.assert_not_called()


if __name__ == '__main__':
    unittest.main()
