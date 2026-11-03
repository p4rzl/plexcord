import asyncio
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from plexcord.plex import Track
from plexcord.presence import RichPresence
from plexcord.store import Store


class PresenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(self.directory.name)
        self.bot = SimpleNamespace(
            store=self.store,
            application_id="123456789",
            http_session=None,
            players={},
            get_guild=lambda gid: SimpleNamespace(id=gid),
        )
        self.presence = RichPresence(self.bot)

    async def asyncTearDown(self):
        await self.presence.close()
        self.store.close()
        self.directory.cleanup()

    def test_user_key_and_check(self):
        key = self.presence.user_key(12345)
        self.assertTrue(self.presence.check_user_key(12345, key))
        self.assertFalse(self.presence.check_user_key(12345, "invalid_key"))
        self.assertFalse(self.presence.check_user_key(99999, key))

    def test_cover_sig(self):
        sig1 = self.presence.cover_sig(1, "100")
        sig2 = self.presence.cover_sig(1, "100")
        sig3 = self.presence.cover_sig(2, "100")
        self.assertEqual(sig1, sig2)
        self.assertNotEqual(sig1, sig3)

    def test_store_discord_oauth(self):
        self.assertIsNone(self.store.get_discord_oauth(42))
        data = {
            "access_token": "acc_tok",
            "refresh_token": "ref_tok",
            "scope": "identify activities.write",
            "expires_at": 9999999999,
        }
        self.store.save_discord_oauth(42, data)
        loaded = self.store.get_discord_oauth(42)
        self.assertEqual(loaded["access_token"], "acc_tok")
        self.assertEqual(loaded["scope"], "identify activities.write")
        self.assertTrue(self.presence.has_scope(42))

        ids = self.store.discord_oauth_ids([42, 99])
        self.assertEqual(ids, [42])

        self.store.delete_discord_oauth(42)
        self.assertIsNone(self.store.get_discord_oauth(42))
        self.assertFalse(self.presence.has_scope(42))

    async def test_build_activity(self):
        guild = SimpleNamespace(id=1)
        player = SimpleNamespace(guild=guild, elapsed=30, paused_at=0)
        track = Track("55", "Test Song", "Test Artist", "Test Album", "Music", 180000)

        act = await self.presence.build_activity(player, "playing", track)
        self.assertEqual(act["type"], 2)
        self.assertEqual(act["name"], "Plex")
        self.assertEqual(act["details"], "Test Song")
        self.assertIn("Test Artist", act["state"])
        self.assertIn("timestamps", act)
        self.assertEqual(act["assets"]["large_text"], "Test Album")

        # Test paused state
        act_paused = await self.presence.build_activity(player, "paused", track)
        self.assertIn("⏸️", act_paused["details"])
        self.assertNotIn("timestamps", act_paused)

    async def test_sync_player_clears_exited_listeners(self):
        self.presence.owner[42] = 1
        self.presence.sessions[42] = "sess_42"

        # No listeners in player
        player = SimpleNamespace(guild=SimpleNamespace(id=1, voice_client=None), current=None, paused_at=0)
        with patch.object(self.presence, "clear", new_callable=AsyncMock) as mock_clear:
            await self.presence.sync_player(player, "stopped")
            mock_clear.assert_called_with(42)
