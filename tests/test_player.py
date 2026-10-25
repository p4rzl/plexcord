import asyncio
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from plexcord.player import Player
from plexcord.plex import PlexError, Track
from plexcord.store import Store


class FakeVoice:
    def __init__(self):
        self.channel = SimpleNamespace(id=10)
        self.connected = True
        self.after = None
        self.source = None
        self.stops = 0

    def is_connected(self):
        return self.connected

    async def disconnect(self, **kwargs):
        self.connected = False

    def play(self, source, after):
        self.source, self.after = source, after

    def stop(self):
        self.stops += 1


class PlayerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(self.directory.name)
        settings = self.store.get(1)
        settings.server_token = "secret"
        self.store.save(1, settings)
        self.voice = FakeVoice()
        self.guild = SimpleNamespace(id=1, voice_client=self.voice)
        self.plex = SimpleNamespace(streams=AsyncMock(return_value=["http://plex/library/parts/1/file.mp3"]))
        self.player = Player(self.guild, self.plex, self.store)
        self.track = Track("1", "Song", "Artist", "Album", "Music", 1000)

    async def asyncTearDown(self):
        await self.player.close()
        self.store.close()
        self.directory.cleanup()

    async def wait_for(self, predicate):
        async def wait():
            while not predicate():
                await asyncio.sleep(0.001)
        await asyncio.wait_for(wait(), 1)

    async def test_playback_skip_and_queue(self):
        with patch("plexcord.player.ManagedOpusAudio") as audio:
            audio.return_value.prepare = AsyncMock()
            await self.player.add(self.voice.channel, self.track, None)
            await self.wait_for(lambda: self.voice.source is not None)
            # Non passare codec='libopus': discord.py lo interpreta come COPY!
            self.assertNotIn("codec", audio.call_args.kwargs)
            self.assertNotIn("secret", audio.call_args.args[0])
            self.assertIn("X-Plex-Token", audio.call_args.kwargs["before_options"])
            await self.player.add(self.voice.channel, self.track, None)
            self.assertEqual(len(self.player.queue), 1)
            self.player.skip()
            await self.wait_for(lambda: audio.call_count == 2)
            self.assertEqual(len(self.player.queue), 0)
            self.player.stop()
            await self.wait_for(lambda: self.player.current is None)

    async def test_cannot_hijack_other_channel(self):
        with self.assertRaises(PlexError):
            await self.player.add(SimpleNamespace(id=20), self.track, None)

    async def test_skip_during_stream_resolution(self):
        started = asyncio.Event()
        release = asyncio.Event()

        async def stream(*args):
            started.set()
            await release.wait()
            return ["http://plex/file"]

        self.plex.streams = stream
        with patch("plexcord.player.ManagedOpusAudio") as audio:
            await self.player.add(self.voice.channel, self.track, None)
            await started.wait()
            self.player.skip()
            release.set()
            await self.wait_for(lambda: self.player.current is None)
            audio.assert_not_called()

    async def test_queue_limit(self):
        settings = self.store.get(1)
        settings.max_queue = 1
        self.store.save(1, settings)
        self.player.queue.append(self.track)
        with self.assertRaises(PlexError):
            await self.player.add(self.voice.channel, self.track, None)

    async def test_broken_version_retries_before_voice_playback(self):
        self.plex.streams.return_value = ["http://plex/broken", "http://plex/working"]
        with patch("plexcord.player.ManagedOpusAudio") as audio:
            broken, working = audio.return_value, MagicMock()
            broken.prepare = AsyncMock(side_effect=PlexError("File non valido."))
            working.prepare = AsyncMock()
            audio.side_effect = [broken, working]
            await self.player.add(self.voice.channel, self.track, None)
            await self.wait_for(lambda: self.voice.source is working)
            self.assertEqual(audio.call_count, 2)
            broken.cleanup.assert_called_once()
            self.assertEqual(len(self.player.queue), 0)

    async def test_all_broken_versions_do_not_block_next_track(self):
        self.player.notify = AsyncMock()
        with patch("plexcord.player.ManagedOpusAudio") as audio:
            audio.return_value.prepare = AsyncMock(side_effect=PlexError("File non valido."))
            await self.player.add(self.voice.channel, self.track, None)
            await self.player.add(self.voice.channel, self.track, None)
            await self.wait_for(lambda: self.player.notify.await_count == 2)
            self.assertIsNone(self.voice.source)
            self.assertEqual(audio.call_count, 2)

    async def test_skip_cancels_slow_audio_preparation(self):
        started = asyncio.Event()

        async def prepare():
            started.set()
            await asyncio.Event().wait()

        with patch("plexcord.player.ManagedOpusAudio") as audio:
            audio.return_value.prepare = prepare
            await self.player.add(self.voice.channel, self.track, None)
            await asyncio.wait_for(started.wait(), 1)
            self.player.skip()
            await self.wait_for(lambda: self.player.current is None)
            self.assertIsNone(self.voice.source)
            audio.return_value.cleanup.assert_called_once()
