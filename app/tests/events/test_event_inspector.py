import unittest

from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.events.event_commands import ChangeMusic, GiveItem, Music
from app.events.event_prefab import EventCatalog, EventPrefab

class EventInspectorTests(unittest.TestCase):
    def setUp(self):
        from app.data.database.database import Database
        self.db = Database()
        self.db.load('testing_proj.ltproj', CURRENT_SERIALIZATION_VERSION)
        self.event_inspector = self.db.events.inspector

    def tearDown(self) -> None:
        pass

    def test_unit_dump(self):
        give_item_events = self.event_inspector.find_all_calls_of_command(GiveItem())
        self.assertEqual(len(give_item_events), 1)
        self.assertEqual(list(give_item_events.values())[0].to_plain_text(), 'give_item;101;Hand Axe')

    def test_find_music_in_python_event(self):
        # Python-style ($-prefixed) events were invisible to the inspector, so music they
        # played was never preloaded - causing a stutter when the song loaded at runtime.
        event = EventPrefab('pyev_music')
        event.source = "#pyev1\n$load_unit 'Franz'\n$m 'Main Theme'\n$change_music 'player_phase' 'Other Theme'"
        catalog = EventCatalog([event])

        music_calls = catalog.inspector.find_all_calls_of_command(Music())
        self.assertEqual(len(music_calls), 1)
        self.assertEqual(list(music_calls.values())[0].parameters.get('Music'), 'Main Theme')

        change_music_calls = catalog.inspector.find_all_calls_of_command(ChangeMusic())
        self.assertEqual(len(change_music_calls), 1)
        self.assertEqual(list(change_music_calls.values())[0].parameters.get('Music'), 'Other Theme')

if __name__ == '__main__':
    unittest.main()
