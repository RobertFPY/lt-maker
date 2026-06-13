import unittest

from app.events.event_prefab import EventCatalog, EventPrefab

class EventCatalogGetTests(unittest.TestCase):
    def setUp(self):
        # An event with no trigger set (call-only), and one bound to a real region trigger
        self.no_trigger_event = EventPrefab('no_trigger')
        self.no_trigger_event.trigger = None

        self.region_event = EventPrefab('region_event')
        self.region_event.trigger = 'MyRegion'

        self.catalog = EventCatalog([self.no_trigger_event, self.region_event])

    def test_falsy_trigger_matches_nothing(self):
        # A region created without a trigger name yields a falsy trigger nid. It must not
        # fire every triggerless event (the reported bug).
        self.assertEqual(self.catalog.get(None, None), [])
        self.assertEqual(self.catalog.get('', None), [])

    def test_real_trigger_still_matches(self):
        matched = self.catalog.get('MyRegion', None)
        self.assertEqual(matched, [self.region_event])

if __name__ == '__main__':
    unittest.main()
