import tempfile
import unittest

from plexcord.store import Store


class StoreTests(unittest.TestCase):
    def test_persistence_and_guild_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            client_id = store.client_id
            settings = store.get(1)
            settings.token = "secret"
            settings.libraries = []
            settings.volume = 75
            store.save(1, settings)
            self.assertEqual(settings.revision, 1)
            self.assertEqual(store.get(2).token, "")
            self.assertIsNone(store.get(2).libraries)
            self.assertNotIn("secret", repr(settings))
            store.close()
            store = Store(directory)
            self.assertEqual(store.client_id, client_id)
            self.assertEqual(store.get(1).token, "secret")
            self.assertEqual(store.get(1).volume, 75)
            self.assertEqual(store.get(1).libraries, [])
            store.close()
