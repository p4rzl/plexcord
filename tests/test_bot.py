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
                    self._user_id = user_id
                    self._voice_channel = voice_channel
                    self._roles = []

                @property
                def id(self):
                    return self._user_id

                @property
                def voice(self):
                    return SimpleNamespace(channel=self._voice_channel) if self._voice_channel else None

                @property
                def roles(self):
                    return self._roles

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

    async def test_dj_only_permission_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            bot = Plexcord(directory)
            channel = SimpleNamespace(id=10)
            dj_role = SimpleNamespace(id=777, name="DJ", position=2, is_default=lambda: False, managed=False)
            guild = SimpleNamespace(
                id=1,
                owner_id=500,
                voice_client=SimpleNamespace(channel=channel),
                get_role=lambda rid: dj_role if rid == 777 else None,
                roles=[dj_role],
            )

            class FakeMember(discord.Member):
                def __init__(self, user_id, voice_channel, roles=None, manage_guild=False, administrator=False):
                    self._user_id = user_id
                    self._voice_channel = voice_channel
                    self._roles = roles or []
                    self._guild_perms = SimpleNamespace(manage_guild=manage_guild, administrator=administrator)

                @property
                def id(self):
                    return self._user_id

                @property
                def voice(self):
                    return SimpleNamespace(channel=self._voice_channel) if self._voice_channel else None

                @property
                def roles(self):
                    return self._roles

                @property
                def guild_permissions(self):
                    return self._guild_perms

            user_normal = FakeMember.__new__(FakeMember)
            FakeMember.__init__(user_normal, 100, channel)

            user_admin = FakeMember.__new__(FakeMember)
            FakeMember.__init__(user_admin, 200, channel, manage_guild=True)

            user_dj = FakeMember.__new__(FakeMember)
            FakeMember.__init__(user_dj, 300, channel, roles=[dj_role])

            user_owner = FakeMember.__new__(FakeMember)
            FakeMember.__init__(user_owner, 500, channel)

            # Quando dj_only è False: chiunque può controllare
            settings = bot.store.get(1)
            settings.dj_only = False
            bot.store.save(1, settings)
            self.assertTrue(bot.can_control(guild, user_normal, settings))
            self.assertTrue(bot.can_control(guild, user_admin, settings))

            # Quando dj_only è True: solo admin, owner o ruolo DJ
            settings.dj_only = True
            settings.dj_role = 777
            bot.store.save(1, settings)

            self.assertFalse(bot.can_control(guild, user_normal, settings))
            self.assertTrue(bot.can_control(guild, user_admin, settings))
            self.assertTrue(bot.can_control(guild, user_dj, settings))
            self.assertTrue(bot.can_control(guild, user_owner, settings))

            # Verifica require_voice e PlayerView con dj_only
            interaction_normal = SimpleNamespace(user=user_normal, guild=guild, guild_id=1)
            interaction_dj = SimpleNamespace(user=user_dj, guild=guild, guild_id=1)

            with self.assertRaises(PlexError) as ctx:
                bot.require_voice(interaction_normal)
            self.assertIn("@DJ", str(ctx.exception))

            self.assertIs(bot.require_voice(interaction_dj), channel)

            player_view = PlayerView(bot)
            try:
                with self.assertRaises(PlexError):
                    await player_view.interaction_check(interaction_normal)
                self.assertTrue(await player_view.interaction_check(interaction_dj))
            finally:
                player_view.stop()
                await bot.close()

    async def test_activity_permissions_and_state(self):
        with tempfile.TemporaryDirectory() as directory:
            bot = Plexcord(directory)
            channel = SimpleNamespace(id=10, members=[SimpleNamespace(bot=False, id=100)])
            dj_role = SimpleNamespace(id=888, name="MusicMaster", position=5, is_default=lambda: False, managed=False)
            guild = SimpleNamespace(
                id=1,
                voice_client=SimpleNamespace(channel=channel),
                get_channel=lambda cid: channel if cid == 10 else None,
                get_role=lambda rid: dj_role if rid == 888 else None,
                voice_channels=[channel],
                roles=[dj_role],
            )
            bot.get_guild = lambda gid: guild if gid == 1 else None

            settings = bot.store.get(1)
            settings.dj_only = True
            settings.dj_role = 888
            bot.store.save(1, settings)

            try:
                state = await bot.activity_server.build_state(guild, channel)
                self.assertTrue(state["dj_only"])
                self.assertEqual(state["dj_role"], "888")
                self.assertEqual(state["dj_role_name"], "MusicMaster")
                self.assertEqual(state["language"], "en")
                self.assertEqual(len(state["roles"]), 1)
                self.assertEqual(state["roles"][0]["name"], "MusicMaster")

                # Test config_handler save_settings aggiorna dj_only, dj_role e lingua
                req = SimpleNamespace(
                    query={"guild_id": "1", "channel_id": "10"},
                    match_info={},
                    json=AsyncMock(return_value={"action": "save_settings", "dj_only": True, "dj_role": "888", "language": "it"})
                )
                await bot.activity_server.config_handler(req)
                saved = bot.store.get(1)
                self.assertTrue(saved.dj_only)
                self.assertEqual(saved.dj_role, 888)
                self.assertEqual(saved.language, "it")

                # Test control_handler blocca utenti non DJ se dj_only è attivo
                guild.get_member = lambda uid: SimpleNamespace(id=uid, guild_permissions=SimpleNamespace(manage_guild=False, administrator=False), roles=[])
                ctrl_req = SimpleNamespace(
                    query={"guild_id": "1", "channel_id": "10"},
                    match_info={},
                    json=AsyncMock(return_value={"action": "skip", "user_id": "999"})
                )
                ctrl_res = await bot.activity_server.control_handler(ctrl_req)
                self.assertEqual(ctrl_res.status, 400)
            finally:
                await bot.close()

    async def test_activity_asset_handlers(self):
        with tempfile.TemporaryDirectory() as directory:
            bot = Plexcord(directory)
            try:
                req = SimpleNamespace()
                res_logo = await bot.activity_server.logo_handler(req)
                self.assertEqual(res_logo.status, 200)
                self.assertEqual(res_logo.content_type, "image/jpeg")
                self.assertTrue(len(res_logo.body) > 0)

                res_banner = await bot.activity_server.banner_handler(req)
                self.assertEqual(res_banner.status, 200)
                self.assertEqual(res_banner.content_type, "image/jpeg")
                self.assertTrue(len(res_banner.body) > 0)
            finally:
                await bot.close()
