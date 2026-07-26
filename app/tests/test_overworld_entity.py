import unittest

from app.engine.objects.overworld import OverworldEntityObject, OverworldEntityTypes


class _StubSprite:
    """Minimal stand-in for OverworldUnitSprite mirroring the two behaviors
    relevant to disable_overworld_entity: fade_out captures the parent's current
    display_position into fake_position, and 'normal' clears it."""
    def __init__(self, parent):
        self.parent = parent
        self.fake_position = None
        self.transition_state = 'normal'

    def set_transition(self, new_state):
        self.transition_state = new_state
        if new_state in ('fade_out', 'fade_move', 'warp_out', 'warp_move'):
            self.fake_position = self.parent.display_position
        elif new_state == 'normal':
            self.fake_position = None


class OverworldEntityDisableTests(unittest.TestCase):
    def _make_entity(self):
        entity = OverworldEntityObject()
        entity.nid = 'test_entity'
        entity.dtype = OverworldEntityTypes.UNIT
        entity.dnid = 'test_unit'
        entity.on_node = None
        entity.display_position = (3, 4)
        entity.sprite = _StubSprite(entity)
        return entity

    def _disable(self, entity):
        # mirror disable_overworld_entity (overworld_event_functions.py)
        entity.sprite.set_transition('fade_out')
        entity.on_node = None
        entity.display_position = None

    def test_frozen_fade_resurrects_without_reset(self):
        """If the fade never finishes (fake_position not cleared), the disabled
        entity keeps a display_position via the sprite.fake_position fallback."""
        entity = self._make_entity()
        self._disable(entity)
        # fade_out captured the old position; fallback resurrects it
        self.assertEqual(entity.display_position, (3, 4))

    def test_reset_stale_transition_clears_position(self):
        """The overworld-entry reset (set_transition('normal')) makes a
        logically-disabled entity report no position, so it stays gone."""
        entity = self._make_entity()
        self._disable(entity)

        # reset loop condition from set_up_overworld_game_state
        if entity.sprite and entity._display_position is None and entity.on_node is None:
            entity.sprite.set_transition('normal')

        self.assertIsNone(entity.display_position)

    def test_reset_leaves_active_entity_untouched(self):
        """An entity that is still placed must not be cleared by the reset."""
        entity = self._make_entity()  # display_position (3, 4), not disabled

        if entity.sprite and entity._display_position is None and entity.on_node is None:
            entity.sprite.set_transition('normal')

        self.assertEqual(entity.display_position, (3, 4))


if __name__ == '__main__':
    unittest.main()
