"""Regression coverage for project-scoped item and skill component catalogs."""
from __future__ import annotations

import json
from pathlib import Path
import types
import unittest

from app.data.database.item_components import ItemComponent
from app.data.database.skill_components import SkillComponent
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.utilities.class_utils import recursive_subclasses


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROJECT = ROOT / 'default.ltproj'
GOLDEN_KNIGHT_PROJECT = ROOT / 'Fire Emblem Tales of The Golden Knight.ltproj'


class ComponentCatalogLoadingTests(unittest.TestCase):
    def tearDown(self) -> None:
        # Do not leave project-local Python modules active for unrelated tests.
        RESOURCES.load(str(DEFAULT_PROJECT), CURRENT_SERIALIZATION_VERSION)

    def test_catalog_uses_only_active_module_namespaces(self) -> None:
        from app.engine.component_catalog import build_component_catalog

        engine_module = types.ModuleType('test.engine_components')
        active = type('Active', (ItemComponent,), {
            '__module__': engine_module.__name__, 'nid': 'active_component'})
        engine_module.Active = active

        # This class is globally registered as a subclass, but its module is not
        # active. A catalog must not discover it through __subclasses__().
        type('Polluted', (ItemComponent,), {
            '__module__': 'test.dynamic_import_pollution', 'nid': 'polluted_component'})

        catalog = build_component_catalog(
            ItemComponent, (engine_module,), (), 'item')
        self.assertEqual(['active_component'], catalog.keys())

    def test_duplicate_nid_error_identifies_every_origin(self) -> None:
        from app.engine.component_catalog import ComponentCatalogError, build_component_catalog

        first = types.ModuleType('test.first_components')
        second = types.ModuleType('test.second_components')
        first.First = type('First', (ItemComponent,), {
            '__module__': first.__name__, 'nid': 'duplicate'})
        second.Second = type('Second', (ItemComponent,), {
            '__module__': second.__name__, 'nid': 'duplicate'})

        with self.assertRaisesRegex(ComponentCatalogError, 'test.first_components.First') as exc:
            build_component_catalog(ItemComponent, (first, second), (), 'item')
        self.assertIn('test.second_components.Second', str(exc.exception))

    def test_recursive_subclasses_deduplicates_diamond_inheritance(self) -> None:
        class Root:
            pass

        class Left(Root):
            pass

        class Right(Root):
            pass

        class Diamond(Left, Right):
            pass

        subclasses = recursive_subclasses(Root)
        self.assertEqual(1, subclasses.count(Diamond))

    def test_repeated_and_cross_project_loads_do_not_leak_custom_classes(self) -> None:
        from app.engine import item_component_access, skill_component_access

        RESOURCES.load(str(DEFAULT_PROJECT), CURRENT_SERIALIZATION_VERSION)
        default_skill_components = skill_component_access.get_cached_skill_components('catalog-default')
        self.assertNotIn('golden_upkeep_event', default_skill_components.keys())

        RESOURCES.load(str(GOLDEN_KNIGHT_PROJECT), CURRENT_SERIALIZATION_VERSION)
        first = skill_component_access.get_cached_skill_components('catalog-golden-first')
        first_class = first.get('golden_upkeep_event')
        self.assertIsNotNone(first_class)
        self.assertEqual('custom_components.custom_skill_components', first_class.__module__)

        RESOURCES.load(str(GOLDEN_KNIGHT_PROJECT), CURRENT_SERIALIZATION_VERSION)
        second = skill_component_access.get_cached_skill_components('catalog-golden-second')
        self.assertIs(first_class, second.get('golden_upkeep_event'))
        self.assertEqual(len(second.keys()), len(set(second.keys())))

        RESOURCES.load(str(DEFAULT_PROJECT), CURRENT_SERIALIZATION_VERSION)
        default_again = skill_component_access.get_cached_skill_components('catalog-default-again')
        self.assertNotIn('golden_upkeep_event', default_again.keys())
        self.assertEqual(len(default_again.keys()), len(set(default_again.keys())))
        self.assertEqual(len(item_component_access.get_cached_item_components('catalog-items').keys()),
                         len(set(item_component_access.get_cached_item_components('catalog-items').keys())))

    def test_golden_knight_migrations_keep_canonical_engine_and_project_components(self) -> None:
        items = json.loads((GOLDEN_KNIGHT_PROJECT / 'game_data' / 'items.json').read_text(encoding='utf-8'))
        skills = json.loads((GOLDEN_KNIGHT_PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8'))

        hp_cost_items = [item for item in items if 'eval_hp_cost' in dict(item['components'])]
        sabotage = [skill for skill in skills if skill['nid'].startswith('Sabotage_') and
                    not skill['nid'].endswith('_Effect')]
        self.assertEqual(53, len(hp_cost_items))
        self.assertTrue(all('hp_uses_options' in dict(item['components']) for item in hp_cost_items))
        self.assertEqual(15, len(sabotage))
        self.assertTrue(all('golden_upkeep_event' in dict(skill['components']) for skill in sabotage))
        self.assertTrue(all('upkeep_event' not in dict(skill['components']) for skill in sabotage))

        RESOURCES.load(str(GOLDEN_KNIGHT_PROJECT), CURRENT_SERIALIZATION_VERSION)
        from app.engine import item_component_access, skill_component_access
        self.assertEqual('app.engine.item_components.usable_components',
                         item_component_access.get_component('eval_hp_cost').__class__.__module__)
        self.assertEqual('custom_components.custom_skill_components',
                         skill_component_access.get_component('golden_upkeep_event').__class__.__module__)


if __name__ == '__main__':
    unittest.main()
