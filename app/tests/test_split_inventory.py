import unittest
from unittest.mock import patch

from app.data.database.constants import Constant, ConstantCatalog, ConstantType
from app.data.database.database import DB
from app.engine import item_funcs, trade
from app.engine.objects.item import ItemObject
from app.engine.objects.unit import UnitObject


class SplitInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.constant_values = {
            nid: DB.constants.value(nid)
            for nid in ('split_inventory', 'num_weapons', 'num_items', 'num_accessories')
        }
        DB.constants.get('split_inventory').set_value(True)
        DB.constants.get('num_weapons').set_value(2)
        DB.constants.get('num_items').set_value(2)
        DB.constants.get('num_accessories').set_value(1)

        self.patchers = [
            patch(
                'app.engine.item_funcs.item_system.is_accessory',
                side_effect=lambda unit, item: item.data.get('test_section') == 'accessory'),
            patch(
                'app.engine.item_funcs.item_system.is_weapon',
                side_effect=lambda unit, item: item.data.get('test_section') == 'weapon'),
            patch(
                'app.engine.item_funcs.item_system.is_spell',
                side_effect=lambda unit, item: item.data.get('test_section') == 'spell'),
            patch('app.engine.item_funcs.skill_system.num_items_offset', return_value=0),
            patch('app.engine.item_funcs.skill_system.num_accessories_offset', return_value=0),
            patch('app.engine.trade.item_system.tradeable', return_value=True),
            patch('app.engine.objects.unit.item_system.on_add_item'),
            patch('app.engine.objects.unit.item_system.on_remove_item'),
            patch('app.engine.objects.unit.skill_system.on_add_item'),
            patch('app.engine.objects.unit.skill_system.on_remove_item'),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        for nid, value in self.constant_values.items():
            DB.constants.get(nid).set_value(value)

    @staticmethod
    def make_item(nid: str, section: str) -> ItemObject:
        item = ItemObject(nid, nid, nid)
        item.data['test_section'] = section
        return item

    def test_constant_catalog_resets_missing_values_between_projects(self) -> None:
        catalog = ConstantCatalog([
            Constant('feature', 'Feature', ConstantType.BOOL, False),
        ])
        catalog.restore([('feature', True)])
        self.assertTrue(catalog.value('feature'))

        catalog.restore([])
        self.assertFalse(catalog.value('feature'))

    def test_weapon_spell_item_and_accessory_sections(self) -> None:
        unit = UnitObject('SectionUnit')
        weapon = self.make_item('Sword', 'weapon')
        spell = self.make_item('Wind', 'spell')
        regular_item = self.make_item('Vulnerary', 'item')
        accessory = self.make_item('Costume', 'accessory')
        wrapper = self.make_item('Multi', 'item')
        wrapper.multi_item = True
        wrapper.subitems = [weapon]

        self.assertEqual(item_funcs.InventorySection.WEAPON,
                         item_funcs.get_inventory_section(unit, weapon))
        self.assertEqual(item_funcs.InventorySection.WEAPON,
                         item_funcs.get_inventory_section(unit, spell))
        self.assertEqual(item_funcs.InventorySection.WEAPON,
                         item_funcs.get_inventory_section(unit, wrapper))
        self.assertEqual(item_funcs.InventorySection.ITEM,
                         item_funcs.get_inventory_section(unit, regular_item))
        self.assertEqual(item_funcs.InventorySection.ACCESSORY,
                         item_funcs.get_inventory_section(unit, accessory))

    def test_capacity_and_inventory_order_are_section_aware(self) -> None:
        unit = UnitObject('CapacityUnit')
        regular_item = self.make_item('Vulnerary', 'item')
        accessory = self.make_item('Costume', 'accessory')
        spell = self.make_item('Wind', 'spell')
        weapon = self.make_item('Sword', 'weapon')

        for item in (regular_item, accessory, spell, weapon):
            unit.add_item(item)

        self.assertEqual([spell, weapon, regular_item, accessory], unit.items)
        self.assertEqual([spell, weapon], unit.weapon_items)
        self.assertEqual([regular_item], unit.regular_items)
        self.assertTrue(item_funcs.inventory_full(unit, weapon))
        self.assertFalse(item_funcs.inventory_full(unit, regular_item))

    def test_legacy_mode_keeps_shared_nonaccessory_capacity(self) -> None:
        DB.constants.get('split_inventory').set_value(False)
        DB.constants.get('num_items').set_value(2)
        DB.constants.get('num_accessories').set_value(0)
        unit = UnitObject('LegacyUnit')
        unit.items = [
            self.make_item('Sword', 'weapon'),
            self.make_item('Vulnerary', 'item'),
        ]

        self.assertTrue(item_funcs.inventory_full(
            unit, self.make_item('Wind', 'spell')))
        self.assertEqual(2, item_funcs.get_total_inventory_capacity(unit))

    def test_trade_allows_valid_cross_section_swap(self) -> None:
        unit1 = UnitObject('TradeOne')
        unit2 = UnitObject('TradeTwo')
        weapon = self.make_item('Sword', 'weapon')
        regular_item = self.make_item('Vulnerary', 'item')
        unit1.items = [weapon]
        unit2.items = [regular_item]

        self.assertTrue(trade.check_trade(weapon, unit1, regular_item, unit2))

    def test_trade_rejects_wrong_empty_section_and_worsening_overflow(self) -> None:
        DB.constants.get('num_weapons').set_value(1)
        unit1 = UnitObject('OverflowOne')
        unit2 = UnitObject('OverflowTwo')
        weapon1 = self.make_item('Sword', 'weapon')
        weapon2 = self.make_item('Lance', 'weapon')
        unit1.items = [weapon1, weapon2]

        item_slot = item_funcs.InventorySlot(item_funcs.InventorySection.ITEM, 0)
        self.assertFalse(trade.check_trade(weapon1, unit1, item_slot, unit2))

        weapon3 = self.make_item('Axe', 'weapon')
        unit2.items = [weapon3]
        self.assertFalse(trade.check_trade(
            item_funcs.InventorySlot(item_funcs.InventorySection.WEAPON, 2),
            unit1, weapon3, unit2))


if __name__ == '__main__':
    unittest.main()
