import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord

from plexcord.bot import PlayerView, Plexcord, TrackView
from plexcord.plex import PlexError, Track


class BotTests(unittest.IsolatedAsyncioTestCase):
    async def test_command_registration_and_shutdown(self):
        with tempfile.TemporaryDirectory() as directory:
            bot = Plexcord(directory)
            commands = {command.name: command for command in bot.tree.get_commands()}
            self.assertEqual(set(commands), {"plex", "settings", "play", "playlist", "queue", "now", "pause", "resume", "skip", "stop", "leave", "shuffle", "activity", "mode", "link", "unlink", "help"})
            self.assertFalse(bot.intents.message_content)
            self.assertFalse(bot.intents.members)
            self.assertTrue(bot.intents.voice_states)
            self.assertEqual(commands["plex"].default_permissions, discord.Permissions(manage_guild=True))
            for command in commands["plex"].commands:
                self.assertTrue(command.checks, command.name)
            for command in commands.values():
                command.to_dict(bot.tree)  # Verifica serializzazione opzioni e Range.
            await bot.close()

    async def test_track_menu_pages_use_absolute_indices(self):
        interaction = SimpleNamespace(user=SimpleNamespace(id=1), response=SimpleNamespace(edit_message=AsyncMock()))
        tracks = [Track(str(i), f"Song {i}", "Artist", "Album", "Music", 1000) for i in range(60)]
        view = TrackView(None, interaction, tracks, 0)
        try:
            self.assertEqual(len(view.select.options), 25)
            self.assertTrue(view.previous.disabled)
            await view.next_page.callback(interaction)
            self.assertEqual(view.page, 1)
            self.assertEqual(view.select.options[0].value, "25")
            await view.next_page.callback(interaction)
            self.assertEqual(len(view.select.options), 10)
            self.assertEqual(view.select.options[0].value, "50")
            self.assertTrue(view.next_page.disabled)
            await view.previous.callback(interaction)
            self.assertEqual(view.select.options[0].value, "25")
        finally:
            view.stop()

    async def test_any_user_in_voice_channel_can_control_views(self):
        with tempfile.TemporaryDirectory() as directory:
            bot = Plexcord(directory)
            settings = bot.store.get(1)
            settings.dj_role = 999
            bot.store.save(1, settings)
            channel = SimpleNamespace(id=10)
            guild = SimpleNamespace(id=1, voice_client=SimpleNamespace(channel=channel))

            class FakeMember(discord.Member):
                def __init__(self, user_id, voice_channel):
                    self.id = user_id
                    self.voice = SimpleNamespace(channel=voice_channel) if voice_channel else None
                    self.roles = []

            member_in_voice = FakeMember.__new__(FakeMember)
            FakeMember.__init__(member_in_voice, 42, channel)
            other_interaction = SimpleNamespace(
                user=member_in_voice, guild=guild, guild_id=1,
                permissions=SimpleNamespace(manage_guild=False),
            )
            player_view = PlayerView(bot)
            try:
                self.assertTrue(await player_view.interaction_check(other_interaction))
                outsider = FakeMember.__new__(FakeMember)
                FakeMember.__init__(outsider, 99, SimpleNamespace(id=20))
                outsider_interaction = SimpleNamespace(user=outsider, guild=guild, guild_id=1)
                with self.assertRaises(PlexError):
                    await player_view.interaction_check(outsider_interaction)
            finally:
                player_view.stop()
                await bot.close()

    async def test_activity_token_and_context_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            bot = Plexcord(directory)
            try:
                channel = SimpleNamespace(id=10, members=[SimpleNamespace(bot=False)])
                guild = SimpleNamespace(
                    id=1,
                    voice_client=SimpleNamespace(channel=channel),
                    get_channel=lambda cid: channel if cid == 10 else None,
                    voice_channels=[channel],
                )
                bot.get_guild = lambda gid: guild if gid == 1 else None
                token = bot.activity_server.sign(1, 10)
                request = SimpleNamespace(query={"token": token})
                resolved_guild, resolved_channel = bot.activity_server.resolve_context(request, require_active=True)
                self.assertIs(resolved_guild, guild)
                self.assertIs(resolved_channel, channel)

                bad_request = SimpleNamespace(query={"token": "1:10:9999999999:invalid"})
                with self.assertRaises(PlexError):
                    bot.activity_server.resolve_context(bad_request)
            finally:
                await bot.close()
