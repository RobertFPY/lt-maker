from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch


class AddGroupTests(unittest.TestCase):
    def test_event_places_all_eligible_members_before_returning(self):
        from app.events import event_functions

        group = SimpleNamespace(units=['unit_a', 'unit_b'])
        units = {
            'unit_a': SimpleNamespace(nid='unit_a', position=None, dead=False),
            'unit_b': SimpleNamespace(nid='unit_b', position=None, dead=False),
        }
        placed = []
        event = SimpleNamespace(
            game=SimpleNamespace(
                level=SimpleNamespace(unit_groups={'group': group}),
                get_unit=lambda nid: units[nid]),
            should_update={}, should_remain_blocked=[], state='processing',
            logger=SimpleNamespace(error=lambda *_args: None),
            _get_position=lambda *_args: (1, 1),
            _check_placement=lambda _unit, position, _placement: position,
            _place_unit=lambda unit, position, entry_type: placed.append(
                (unit.nid, position, entry_type)),
        )

        with patch.object(event_functions.DB.constants, 'value', return_value=False):
            event_functions.add_group(event, 'group')

        self.assertEqual([
            ('unit_a', (1, 1), 'fade'),
            ('unit_b', (1, 1), 'fade'),
        ], placed)
        self.assertEqual('processing', event.state)
        self.assertNotIn('add_group', event.should_update)
        self.assertEqual([], event.should_remain_blocked)
