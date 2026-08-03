import unittest
from dataclasses import dataclass, field
from unittest.mock import patch

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
                patch.object(RuntimeDebugger, '_queue_event') as queue_event:
            self.assertTrue(RuntimeDebugger.go_to_chapter('Next'))

        queue_event.assert_called_once_with('set_next_chapter;Next\nwin_game')

    def test_go_to_unknown_chapter_does_not_queue_an_event(self) -> None:
        with patch('app.engine.runtime_debugger.DB.levels', {}), \
                patch.object(RuntimeDebugger, '_queue_event') as queue_event:
            self.assertFalse(RuntimeDebugger.go_to_chapter('Missing'))

        queue_event.assert_not_called()


if __name__ == '__main__':
    unittest.main()
