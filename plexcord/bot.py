import asyncio
import contextlib
import os

import aiohttp
import discord
from discord import app_commands

from .activity import ActivityServer
from .player import Player
from .plex import Playlist, Plex, PlexError, Track, valid_url
from .presence import RichPresence
from .store import Settings, Store, UserLink

MESSAGES: dict[str, dict[str, str]] = {
    "dm_forbidden": {
        "en": "Please use commands within a Discord server, not in DMs.",
        "it": "Usa i comandi all'interno di un server Discord, non in DM.",
    },
    "activity_mode_prompt": {
        "en": "🎛️ **Activity Mode is active:** use the Discord Activity or Web Player below to search songs, manage queue, and configure Plex.\n*(To return to classic slash commands use `/mode`)*",
        "it": "🎛️ **Modalità Activity attiva:** usa l'Attività Discord o il Web Player qui sotto per cercare brani, gestire la coda e configurare Plex.\n*(Per tornare ai comandi slash classici usa `/mode`)*",
    },
    "activity_heading": {
        "en": "🎛️ **Plexcord Activity & Web Player**",
        "it": "🎛️ **Plexcord Activity & Web Player**",
    },
    "btn_launch_activity": {
        "en": "Launch Discord Activity",
        "it": "Avvia Discord Activity",
    },
    "activity_hint_launch": {
        "en": "• Click **Launch Discord Activity** (or the rocket 🚀 icon in the voice channel) to open it inside Discord.",
        "it": "• Premi **Avvia Discord Activity** (oppure l'icona del razzo 🚀 nel canale vocale) per aprirla dentro Discord.",
    },
    "btn_open_web": {
        "en": "Open Web Player",
        "it": "Apri Web Player",
    },
    "activity_hint_web": {
        "en": "• Click **Open Web Player** to search tracks, manage queue, volume, and configuration from your browser.",
        "it": "• Premi **Apri Web Player** per cercare brani, gestire coda, volume e configurazione dal browser.",
    },
    "err_manage_guild": {
        "en": "Manage Server permission is required to configure Plexcord.",
        "it": "Serve il permesso Gestisci server per configurare Plexcord.",
    },
    "err_cooldown": {
        "en": "Please wait {seconds} seconds before trying again.",
        "it": "Attendi {seconds} secondi prima di riprovare.",
    },
    "err_no_perms": {
        "en": "You do not have permission to use this command.",
        "it": "Non hai i permessi per questo comando.",
    },
    "err_failed": {
        "en": "Operation failed. Check configuration and try again.",
        "it": "Operazione fallita. Controlla la configurazione e riprova.",
    },
    "err_other_user_menu": {
        "en": "This menu belongs to another user.",
        "it": "Questo menu appartiene a un altro utente.",
    },
    "err_menu_failed": {
        "en": "Operation failed. Please try the command again.",
        "it": "Operazione fallita. Riprova con il comando.",
    },
    "login_prompt": {
        "en": "1. Authorize Plexcord on Plex.\n2. Return here and click **Complete login**.\nThe link expires in {expiry} minutes. Your account will be used for this Discord server.",
        "it": "1. Autorizza Plexcord su Plex.\n2. Torna qui e premi **Completa login**.\nIl link scade tra {expiry} minuti. Il tuo account sarà usato per questo server Discord.",
    },
    "login_done": {
        "en": "✅ Login completed. Use /plex servers and /plex server to choose your server.",
        "it": "✅ Login completato. Usa /plex servers e /plex server per scegliere il server.",
    },
    "login_superseded": {
        "en": "Login superseded by a new configuration. Please repeat /plex login.",
        "it": "Login superato da una nuova configurazione. Ripeti /plex login.",
    },
    "login_not_yet": {
        "en": "Please authorize the bot on Plex first, then click Complete login again.",
        "it": "Autorizza prima il bot su Plex, poi premi nuovamente Completa login.",
    },
    "user_link_prompt": {
        "en": "🎧 **Link your Plex Account to Discord**{status}\n1. Go to **https://plex.tv/link** and enter the 4-character PIN: **`{code}`**\n2. Return here and click **Complete linking**.",
        "it": "🎧 **Collega il tuo Account Plex a Discord**{status}\n1. Vai su **https://plex.tv/link** e inserisci il codice PIN a 4 caratteri: **`{code}`**\n2. Torna qui e premi **Completa collegamento**.",
    },
    "user_link_status_line": {
        "en": "\n*(Currently linked to: **{username}**)*",
        "it": "\n*(Attualmente collegato a: **{username}**)*",
    },
    "user_link_not_yet": {
        "en": "Please enter the 4-character code on https://plex.tv/link first, then click **Complete linking** again.",
        "it": "Inserisci prima il codice a 4 caratteri su https://plex.tv/link, poi premi nuovamente **Completa collegamento**.",
    },
    "user_link_done": {
        "en": "🎧 Plex account **{username}** linked to your Discord profile! Your listening activity will be shown on Plex and Discord.",
        "it": "🎧 Account Plex **{username}** collegato al tuo profilo Discord! La tua attività di ascolto verrà mostrata su Plex e Discord.",
    },
    "user_unlink_done": {
        "en": "🗑️ Your Plex account has been unlinked from your Discord profile.",
        "it": "🗑️ Il tuo account Plex è stato scollegato dal profilo Discord.",
    },
    "voice_join_first": {
        "en": "Join a voice channel first.",
        "it": "Entra prima in un canale vocale.",
    },
    "voice_no_stage": {
        "en": "Stage channels are not supported. Please use a normal voice channel.",
        "it": "Usa un normale canale vocale: i canali Stage non sono supportati.",
    },
    "voice_must_match": {
        "en": "You must be in the same voice channel as the bot.",
        "it": "Devi essere nello stesso canale vocale del bot.",
    },
    "voice_dj_restricted": {
        "en": "Music controls are restricted: Manage Server permission{role_hint} is required.",
        "it": "I controlli della musica sono riservati: serve il permesso Gestisci Server{role_hint}.",
    },
    "player_not_connected": {
        "en": "The bot is not connected to a voice channel.",
        "it": "Il bot non è connesso a un canale vocale.",
    },
    "resumed_by": {
        "en": "▶️ Resumed by **{user}**.",
        "it": "▶️ Riproduzione ripresa da **{user}**.",
    },
    "paused_by": {
        "en": "⏸️ Paused by **{user}**.",
        "it": "⏸️ In pausa da **{user}**.",
    },
    "skipped_by": {
        "en": "⏭️ Track skipped by **{user}**.",
        "it": "⏭️ Brano saltato da **{user}**.",
    },
    "shuffled_by": {
        "en": "🔀 Queue shuffled by **{user}**.",
        "it": "🔀 Coda mescolata da **{user}**.",
    },
    "stopped_by": {
        "en": "⏹️ Playback stopped and queue cleared by **{user}**.",
        "it": "⏹️ Riproduzione fermata e coda svuotata da **{user}**.",
    },
    "left_by": {
        "en": "👋 Disconnected by **{user}**.",
        "it": "👋 Disconnesso da **{user}**.",
    },
    "trackview_queued": {
        "en": "✅ Queued: **{title}** · {library}",
        "it": "✅ In coda: **{title}** · {library}",
    },
    "cfg_changed_play": {
        "en": "Configuration changed. Please repeat /play.",
        "it": "Configurazione cambiata. Ripeti /play.",
    },
    "cfg_changed_playlist": {
        "en": "Configuration changed. Please repeat /playlist.",
        "it": "Configurazione cambiata. Ripeti /playlist.",
    },
    "playlist_added": {
        "en": "🎶 Added **{count} tracks** from playlist **{title}**!",
        "it": "🎶 Aggiunti **{count} brani** dalla playlist **{title}**!",
    },
    "playlist_none": {
        "en": "No audio playlists found for Plex account **{username}**.",
        "it": "Nessuna playlist audio trovata per l'account Plex **{username}**.",
    },
    "playlist_require_link": {
        "en": "Link your Plex account first with `/link` (or in the 'Account' tab of the Activity) to see your personal playlists.",
        "it": "Collega prima il tuo account Plex con `/link` (o dalla scheda 'Account' dell'Activity) per vedere le tue playlist personali.",
    },
    "playlist_not_found": {
        "en": "Playlist not found. Choose one from the `/playlist` list.",
        "it": "Playlist non trovata. Sceglila dall'elenco di `/playlist`.",
    },
    "logout_done": {
        "en": "Local credentials removed. To revoke authorization, remove Plexcord from authorized devices in your Plex account.",
        "it": "Credenziali locali rimosse. Per revocare anche l'autorizzazione, rimuovi Plexcord dai dispositivi autorizzati del tuo account Plex.",
    },
    "plex_login_first": {
        "en": "Please run /plex login first.",
        "it": "Esegui prima /plex login.",
    },
    "plex_servers_heading": {
        "en": "Plex Servers (use ID with /plex server):",
        "it": "Server Plex (usa l'ID con /plex server):",
    },
    "plex_server_not_found": {
        "en": "ID not found. Use /plex servers.",
        "it": "ID non trovato. Usa /plex servers.",
    },
    "plex_server_selected": {
        "en": "✅ Server: **{server}**. All music libraries enabled. Use /plex libraries.",
        "it": "✅ Server: **{server}**. Tutte le librerie musicali sono abilitate. Usa /plex libraries.",
    },
    "plex_server_inaccessible": {
        "en": "Server no longer accessible. Repeat /plex server.",
        "it": "Server non più accessibile. Ripeti /plex server.",
    },
    "plex_address_updated": {
        "en": "Plex address updated.",
        "it": "Indirizzo aggiornato.",
    },
    "plex_address_auto": {
        "en": "Automatic detection restored.",
        "it": "Rilevamento automatico ripristinato.",
    },
    "plex_libs_heading": {
        "en": "Music Libraries:",
        "it": "Librerie musicali:",
    },
    "plex_lib_not_found": {
        "en": "Invalid music library ID. Use /plex libraries.",
        "it": "ID di libreria musicale non valido. Usa /plex libraries.",
    },
    "plex_lib_enabled": {
        "en": "Library enabled.",
        "it": "Libreria abilitata.",
    },
    "plex_lib_disabled": {
        "en": "Library disabled. Playback and queue stopped to apply new permissions.",
        "it": "Libreria disabilitata. Riproduzione e coda fermate per applicare i nuovi permessi.",
    },
    "plex_all_libs_done": {
        "en": "All music libraries enabled.",
        "it": "Tutte le librerie musicali abilitate.",
    },
    "settings_conflict_dj": {
        "en": "Use either dj_role or clear_dj, not both.",
        "it": "Usa dj_role oppure clear_dj, non entrambi.",
    },
    "play_query_len": {
        "en": "Please enter a title or artist between 1 and 200 characters.",
        "it": "Inserisci un titolo o autore da 1 a 200 caratteri.",
    },
    "play_no_tracks": {
        "en": "No tracks found. Try another title or artist, or another library.",
        "it": "Nessun brano trovato. Prova un altro titolo o autore, oppure un'altra libreria.",
    },
    "queue_empty": {
        "en": "Queue is empty.",
        "it": "Coda vuota.",
    },
    "now_nothing": {
        "en": "No track currently playing.",
        "it": "Nessun brano in riproduzione.",
    },
    "ctrl_msg_pause": {
        "en": "⏸️ Paused.",
        "it": "⏸️ In pausa.",
    },
    "ctrl_msg_resume": {
        "en": "▶️ Resumed.",
        "it": "▶️ Riproduzione ripresa.",
    },
    "ctrl_msg_skip": {
        "en": "⏭️ Track skipped.",
        "it": "⏭️ Brano saltato.",
    },
    "ctrl_msg_stop": {
        "en": "⏹️ Playback stopped and queue cleared.",
        "it": "⏹️ Riproduzione fermata e coda svuotata.",
    },
    "ctrl_msg_shuffle": {
        "en": "🔀 Queue shuffled.",
        "it": "🔀 Coda mescolata.",
    },
    "ctrl_msg_leave": {
        "en": "👋 Disconnected and queue cleared.",
        "it": "👋 Disconnesso e coda svuotata.",
    },
}


def tr(lang: str, key: str, **kwargs) -> str:
    sub = MESSAGES.get(key, {})
    tmpl = sub.get(lang) or sub.get("en") or key
    if kwargs:
        return tmpl.format(**kwargs)
    return tmpl


def text(value: str, limit: int = 150) -> str:
    return discord.utils.escape_markdown(discord.utils.escape_mentions(value))[:limit]


def duration(seconds: int) -> str:
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}:{seconds:02d}"


async def reply(interaction, content, **kwargs):
    content = content[:1900]
    kwargs.setdefault("ephemeral", True)
    kwargs.setdefault("allowed_mentions", discord.AllowedMentions.none())
    if interaction.response.is_done():
        await interaction.followup.send(content, **kwargs)
    else:
        await interaction.response.send_message(content, **kwargs)


class Tree(app_commands.CommandTree):
    async def sync(self, *, guild=None):
        if guild is not None or not self.client.application_id:
            return await super().sync(guild=guild)
        commands = self._get_all_commands(guild=None)
        payload = [command.to_dict(self) for command in commands]
        with contextlib.suppress(discord.HTTPException):
            existing = await self._http.get_global_commands(self.client.application_id)
            payload.extend(cmd for cmd in existing if cmd.get("type") == 4)
        return await self._http.bulk_upsert_global_commands(self.client.application_id, payload=payload)

    async def interaction_check(self, interaction):
        if not interaction.guild:
            await reply(interaction, self.client.t(interaction.guild_id, "dm_forbidden"))
            return False
        cmd = interaction.command
        root = cmd.root_parent.name if cmd and getattr(cmd, "root_parent", None) else (cmd.name if cmd else "")
        if root and root not in ("mode", "activity", "link", "unlink", "leave", "help"):
            settings = self.client.store.get(interaction.guild_id)
            if settings.mode == "activity":
                heading = self.client.t(interaction.guild_id, "activity_mode_prompt")
                await self.client.send_activity_prompt(interaction, heading=heading)
                return False
        return True

    async def on_error(self, interaction, error):
        original = getattr(error, "original", error)
        if isinstance(original, PlexError):
            message = str(original)
        elif isinstance(error, app_commands.MissingPermissions):
            message = self.client.t(interaction.guild_id, "err_manage_guild")
        elif isinstance(error, app_commands.CommandOnCooldown):
            message = self.client.t(interaction.guild_id, "err_cooldown", seconds=f"{error.retry_after:.0f}")
        elif isinstance(error, app_commands.CheckFailure):
            message = self.client.t(interaction.guild_id, "err_no_perms")
        else:
            message = self.client.t(interaction.guild_id, "err_failed")
        with contextlib.suppress(discord.HTTPException):
            await reply(interaction, message)


class OwnedView(discord.ui.View):
    def __init__(self, owner: int, timeout=180, lang: str = "en"):
        super().__init__(timeout=timeout)
        self.owner = owner
        self.lang = lang

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner:
            bot = getattr(interaction, "client", None) or getattr(self, "bot", None)
            msg = bot.t(interaction.guild_id, "err_other_user_menu") if bot else tr(self.lang, "err_other_user_menu")
            await reply(interaction, msg)
            return False
        return True

    async def on_error(self, interaction, error, item):
        bot = getattr(interaction, "client", None) or getattr(self, "bot", None)
        default_err = bot.t(interaction.guild_id, "err_menu_failed") if bot else tr(self.lang, "err_menu_failed")
        await reply(interaction, str(error) if isinstance(error, PlexError) else default_err)


class LoginView(OwnedView):
    def __init__(self, bot, owner, guild_id, pin_id, url, timeout, revision, lang: str = "en"):
        super().__init__(owner, timeout, lang=lang)
        self.bot = bot
        self.guild_id = guild_id
        self.pin_id = pin_id
        self.revision = revision
        lbl_auth = "Autorizza su Plex" if lang == "it" else "Authorize on Plex"
        self.complete.label = "Completa login" if lang == "it" else "Complete login"
        self.add_item(discord.ui.Button(label=lbl_auth, url=url))

    @discord.ui.button(label="Complete login", style=discord.ButtonStyle.success)
    async def complete(self, interaction, button):
        if not interaction.permissions.manage_guild:
            raise PlexError(self.bot.t(self.guild_id, "err_manage_guild"))
        await interaction.response.defer(ephemeral=True)
        async with self.bot.config_lock(self.guild_id):
            settings = self.bot.store.get(self.guild_id)
            if settings.revision != self.revision or self.bot.logins.get(self.guild_id) is not self:
                raise PlexError(self.bot.t(self.guild_id, "login_superseded"))
            token = await self.bot.plex.check_pin(self.pin_id)
            if not token:
                await reply(interaction, self.bot.t(self.guild_id, "login_not_yet"))
                return
            await self.bot.disconnect(self.guild_id)
            settings.token = token
            settings.server_token = settings.server_id = settings.server_name = settings.server_url = ""
            settings.libraries = None
            self.bot.store.save(self.guild_id, settings)
            self.stop()
            await interaction.edit_original_response(content=self.bot.t(self.guild_id, "login_done"), view=None)


class UserLinkView(OwnedView):
    def __init__(self, bot, owner, pin_id, client_id, url, timeout, lang: str = "en"):
        super().__init__(owner, timeout, lang=lang)
        self.bot = bot
        self.pin_id = pin_id
        self.client_id = client_id
        lbl_open = "Apri plex.tv/link" if lang == "it" else "Open plex.tv/link"
        lbl_direct = "Link diretto" if lang == "it" else "Direct link"
        self.complete.label = "Completa collegamento" if lang == "it" else "Complete linking"
        self.add_item(discord.ui.Button(label=lbl_open, url="https://plex.tv/link"))
        self.add_item(discord.ui.Button(label=lbl_direct, url=url))

    @discord.ui.button(label="Complete linking", style=discord.ButtonStyle.success)
    async def complete(self, interaction, button):
        await interaction.response.defer(ephemeral=True)
        token = await self.bot.plex.check_pin(self.pin_id, client_id=self.client_id)
        if not token:
            await reply(interaction, self.bot.t(interaction.guild_id, "user_link_not_yet"))
            return
        plex_user = await self.bot.plex.user_info(token)
        d_name = getattr(interaction.user, "display_name", None) or interaction.user.name
        self.bot.store.save_user(UserLink(discord_id=interaction.user.id, plex_token=token, plex_username=plex_user, discord_name=d_name))
        self.stop()
        player = self.bot.players.get(interaction.guild_id)
        if player and player.current:
            asyncio.create_task(player.sync_timeline("paused" if player.paused_at else "playing", player.current))
        await interaction.edit_original_response(
            content=self.bot.t(interaction.guild_id, "user_link_done", username=text(plex_user)),
            view=None,
        )


class VoiceView(discord.ui.View):
    """Menu and controls usable by anyone in voice channel (or subject to DJ permissions)."""

    def __init__(self, bot, timeout=300):
        super().__init__(timeout=timeout)
        self.bot = bot

    async def interaction_check(self, interaction):
        if self.bot is not None:
            self.bot.require_voice(interaction)
        return True

    async def on_error(self, interaction, error, item):
        original = getattr(error, "original", error)
        fallback = self.bot.t(interaction.guild_id, "err_menu_failed") if self.bot else "Operation failed. Please try the command again."
        await reply(interaction, str(original) if isinstance(original, PlexError) else fallback)


class PlayerView(VoiceView):
    def __init__(self, bot, guild_id: int = 0, channel_id: int = 0, lang: str = "en"):
        super().__init__(bot, timeout=600)
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.lang = lang
        self.toggle_pause.label = "Pausa/Riprendi" if lang == "it" else "Pause/Resume"
        self.skip_button.label = "Salta" if lang == "it" else "Skip"
        self.shuffle_button.label = "Mescola" if lang == "it" else "Shuffle"
        self.stop_button.label = "Stop"
        self.leave_button.label = "Esci" if lang == "it" else "Leave"
        if bot and getattr(bot, "activity_url", "") and guild_id:
            token = bot.activity_server.sign(guild_id, channel_id)
            url = f"{bot.activity_url}/?guild_id={guild_id}&channel_id={channel_id}&token={token}"
            self.add_item(discord.ui.Button(label="Web Player", emoji="🎛️", url=url, row=1))

    @discord.ui.button(label="Pause/Resume", emoji="⏯️", style=discord.ButtonStyle.primary)
    async def toggle_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        async with self.bot.config_lock(interaction.guild_id):
            self.bot.require_voice(interaction)
            player = self.bot.players.get(interaction.guild_id)
            voice = interaction.guild.voice_client
            if not player or not voice:
                raise PlexError(self.bot.t(interaction.guild_id, "player_not_connected"))
            if voice.is_paused():
                player.resume()
                res = self.bot.t(interaction.guild_id, "resumed_by", user=text(interaction.user.display_name, 40))
            else:
                player.pause()
                res = self.bot.t(interaction.guild_id, "paused_by", user=text(interaction.user.display_name, 40))
        await reply(interaction, res, ephemeral=False)

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        async with self.bot.config_lock(interaction.guild_id):
            self.bot.require_voice(interaction)
            player = self.bot.players.get(interaction.guild_id)
            if not player or not interaction.guild.voice_client:
                raise PlexError(self.bot.t(interaction.guild_id, "player_not_connected"))
            player.skip()
        msg = self.bot.t(interaction.guild_id, "skipped_by", user=text(interaction.user.display_name, 40))
        await reply(interaction, msg, ephemeral=False)

    @discord.ui.button(label="Shuffle", emoji="🔀", style=discord.ButtonStyle.secondary)
    async def shuffle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        async with self.bot.config_lock(interaction.guild_id):
            self.bot.require_voice(interaction)
            player = self.bot.players.get(interaction.guild_id)
            if not player or not interaction.guild.voice_client:
                raise PlexError(self.bot.t(interaction.guild_id, "player_not_connected"))
            player.shuffle()
        msg = self.bot.t(interaction.guild_id, "shuffled_by", user=text(interaction.user.display_name, 40))
        await reply(interaction, msg, ephemeral=False)

    @discord.ui.button(label="Stop", emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        async with self.bot.config_lock(interaction.guild_id):
            self.bot.require_voice(interaction)
            player = self.bot.players.get(interaction.guild_id)
            if not player or not interaction.guild.voice_client:
                raise PlexError(self.bot.t(interaction.guild_id, "player_not_connected"))
            player.stop()
        msg = self.bot.t(interaction.guild_id, "stopped_by", user=text(interaction.user.display_name, 40))
        await reply(interaction, msg, ephemeral=False)

    @discord.ui.button(label="Leave", emoji="👋", style=discord.ButtonStyle.danger)
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        async with self.bot.config_lock(interaction.guild_id):
            self.bot.require_voice(interaction)
            player = self.bot.players.get(interaction.guild_id)
            if not player or not interaction.guild.voice_client:
                raise PlexError(self.bot.t(interaction.guild_id, "player_not_connected"))
            await player.close()
        msg = self.bot.t(interaction.guild_id, "left_by", user=text(interaction.user.display_name, 40))
        await reply(interaction, msg, ephemeral=False)


class TrackView(VoiceView):
    def __init__(self, bot, interaction, tracks: list[Track], revision, lang: str = "en"):
        super().__init__(bot, timeout=180)
        self.revision = revision
        self.tracks = tracks
        self.page = 0
        self.lang = lang
        self.select = discord.ui.Select(row=0)
        self.select.callback = self.selected
        self.previous.label = "Indietro" if lang == "it" else "Back"
        self.next_page.label = "Avanti" if lang == "it" else "Next"
        self.add_item(self.select)
        self.refresh()

    @property
    def caption(self):
        pages = (len(self.tracks) + 24) // 25
        if self.lang == "it":
            return (f"{len(self.tracks)} risultati · pagina {self.page + 1}/{pages}. "
                    "Chiunque nel canale vocale può scegliere un brano o scorrere le pagine.")
        return (f"{len(self.tracks)} results · page {self.page + 1}/{pages}. "
                "Anyone in the voice channel can pick a track or change pages.")

    def refresh(self):
        start = self.page * 25
        self.select.options = [
            discord.SelectOption(
                label=t.label[:100], value=str(i),
                description=(f"{duration(t.duration // 1000)} · {t.library} · {t.album}" if t.duration else f"{t.library} · {t.album}")[:100],
            )
            for i, t in enumerate(self.tracks[start:start + 25], start)
        ]
        ph = f"Scegli un brano · pagina {self.page + 1}" if self.lang == "it" else f"Pick a track · page {self.page + 1}"
        self.select.placeholder = ph
        self.previous.disabled = self.page == 0
        self.next_page.disabled = start + 25 >= len(self.tracks)

    @discord.ui.button(label="Back", row=1)
    async def previous(self, interaction, button):
        self.page = max(0, self.page - 1)
        self.refresh()
        await interaction.response.edit_message(content=self.caption, view=self)

    @discord.ui.button(label="Next", row=1)
    async def next_page(self, interaction, button):
        self.page = min((len(self.tracks) - 1) // 25, self.page + 1)
        self.refresh()
        await interaction.response.edit_message(content=self.caption, view=self)

    async def selected(self, interaction):
        await interaction.response.defer()
        async with self.bot.config_lock(interaction.guild_id):
            if self.bot.store.get(interaction.guild_id).revision != self.revision:
                raise PlexError(self.bot.t(interaction.guild_id, "cfg_changed_play"))
            track = self.tracks[int(self.select.values[0])]
            await self.bot.enqueue(interaction, track)
            self.stop()
            msg = self.bot.t(interaction.guild_id, "trackview_queued", title=text(track.label), library=text(track.library))
            await interaction.edit_original_response(
                content=msg,
                view=self.bot.player_view(interaction),
            )


class PlaylistView(VoiceView):
    def __init__(self, bot, playlists: list[Playlist], user_token: str, revision: int, shuffle: bool = False, lang: str = "en"):
        super().__init__(bot, timeout=180)
        self.playlists = playlists[:25]
        self.user_token = user_token
        self.revision = revision
        self.shuffle = shuffle
        self.lang = lang
        ph = "Scegli una tua playlist Plex da riprodurre..." if lang == "it" else "Choose one of your Plex playlists to play..."
        unit = "brani" if lang == "it" else "tracks"
        self.select = discord.ui.Select(
            placeholder=ph,
            options=[
                discord.SelectOption(
                    label=p.title[:100],
                    value=p.id,
                    description=f"{p.track_count} {unit} · {duration(p.duration // 1000)}"[:100],
                )
                for p in self.playlists
            ],
        )
        self.select.callback = self.selected
        self.add_item(self.select)

    async def selected(self, interaction: discord.Interaction):
        await interaction.response.defer()
        async with self.bot.config_lock(interaction.guild_id):
            settings = self.bot.store.get(interaction.guild_id)
            if settings.revision != self.revision:
                raise PlexError(self.bot.t(interaction.guild_id, "cfg_changed_playlist"))
            channel = self.bot.require_voice(interaction)
            pid = self.select.values[0]
            pl = next((p for p in self.playlists if p.id == pid), None)
            tracks = await self.bot.plex.playlist_tracks(settings, pid, user_token=self.user_token)
            added = await self.bot.player(interaction.guild).add_many(
                channel, tracks, interaction.channel, shuffle_tracks=self.shuffle
            )
            self.stop()
            title = pl.title if pl else pid
            msg = self.bot.t(interaction.guild_id, "playlist_added", count=added, title=text(title))
            await interaction.edit_original_response(
                content=msg,
                view=self.bot.player_view(interaction),
            )


class Plexcord(discord.Client):
    def __init__(self, directory):
        intents = discord.Intents.none()
        intents.guilds = True
        intents.voice_states = True
        super().__init__(intents=intents, allowed_mentions=discord.AllowedMentions.none())
        self.tree = Tree(self)
        self.store = Store(directory)
        self.players: dict[int, Player] = {}
        self.locks: dict[int, asyncio.Lock] = {}
        self.logins: dict[int, LoginView] = {}
        self.track_cache: dict[tuple[int, str], Track] = {}
        port = int(os.environ.get("PLEXCORD_ACTIVITY_PORT", "8080") or "0")
        self.activity_server = ActivityServer(self, port=port)
        self.activity_url = os.environ.get("PLEXCORD_ACTIVITY_URL", "").strip().rstrip("/")
        self.http_session = None
        self.presence = RichPresence(self)
        self.register_commands()

    def get_lang(self, guild_id: int | None) -> str:
        if not guild_id:
            return "en"
        settings = self.store.get(guild_id)
        return getattr(settings, "language", "en") or "en"

    def t(self, guild_id: int | None, key: str, **kwargs) -> str:
        lang = self.get_lang(guild_id)
        return tr(lang, key, **kwargs)

    async def setup_hook(self):
        self.http_session = aiohttp.ClientSession()
        self.plex = Plex(self.http_session, self.store.client_id)
        await self.activity_server.start()
        self.presence.start()
        self.sync_task = asyncio.create_task(self.sync_commands())

    async def sync_commands(self):
        with contextlib.suppress(Exception):
            guild_id = os.environ.get("DISCORD_GUILD_ID", "").strip()
            if guild_id:
                guild = discord.Object(id=int(guild_id))
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
            else:
                await self.tree.sync()

    async def on_ready(self):
        print(f"Plexcord connected as {self.user} · {len(self.guilds)} guilds", flush=True)

    def config_lock(self, guild_id):
        return self.locks.setdefault(guild_id, asyncio.Lock())

    def player(self, guild):
        if guild.id not in self.players:
            self.players[guild.id] = Player(guild, self.plex, self.store, bot=self)
        return self.players[guild.id]

    def player_view(self, interaction, lang: str | None = None):
        voice = getattr(interaction.guild, "voice_client", None)
        channel_id = voice.channel.id if voice and getattr(voice, "channel", None) else 0
        if not channel_id and getattr(interaction.user, "voice", None) and interaction.user.voice.channel:
            channel_id = interaction.user.voice.channel.id
        if lang is None:
            lang = self.get_lang(interaction.guild_id)
        return PlayerView(self, interaction.guild_id or 0, channel_id, lang=lang)

    async def send_activity_prompt(self, interaction: discord.Interaction, heading: str | None = None):
        lang = self.get_lang(interaction.guild_id)
        if not heading:
            heading = self.t(interaction.guild_id, "activity_heading")
        voice = getattr(interaction.guild, "voice_client", None)
        channel = voice.channel if voice and getattr(voice, "channel", None) else None
        if not channel and getattr(interaction.user, "voice", None) and interaction.user.voice.channel:
            channel = interaction.user.voice.channel
        channel_id = channel.id if channel else 0
        token = self.activity_server.sign(interaction.guild_id, channel_id)
        view = discord.ui.View(timeout=300)
        lines = [heading]
        if channel and self.application_id:
            with contextlib.suppress(Exception):
                invite = await channel.create_invite(
                    max_age=3600,
                    target_type=discord.InviteTarget.embedded_application,
                    target_application_id=self.application_id,
                )
                lbl_act = "Avvia Discord Activity" if lang == "it" else "Launch Discord Activity"
                view.add_item(discord.ui.Button(label=lbl_act, emoji="🚀", url=invite.url))
                lines.append(self.t(interaction.guild_id, "activity_hint_launch"))
        base_url = self.activity_url or f"http://localhost:{self.activity_server.port}"
        web_url = f"{base_url}/?guild_id={interaction.guild_id}&channel_id={channel_id}&token={token}"
        lbl_web = "Apri Web Player" if lang == "it" else "Open Web Player"
        view.add_item(discord.ui.Button(label=lbl_web, emoji="🌐", url=web_url))
        lines.append(self.t(interaction.guild_id, "activity_hint_web"))
        await reply(interaction, "\n".join(lines), view=view)

    async def disconnect(self, guild_id):
        if guild_id in self.players:
            await self.players[guild_id].close()

    def is_admin(self, guild, member) -> bool:
        """Check if user has admin/manage guild permissions or is guild owner."""
        if not guild or not member:
            return False
        if getattr(guild, "owner_id", None) == getattr(member, "id", None):
            return True
        perms = getattr(member, "guild_permissions", None)
        return bool(perms and (getattr(perms, "manage_guild", False) or getattr(perms, "administrator", False)))

    def can_control(self, guild, member, settings: Settings | None = None) -> bool:
        """Check if user is authorized to control playback."""
        if not guild or not member:
            return False
        if settings is None:
            settings = self.store.get(guild.id)
        if not settings.dj_only:
            return True
        if self.is_admin(guild, member):
            return True
        if settings.dj_role:
            try:
                target_role = int(settings.dj_role)
            except (ValueError, TypeError):
                target_role = None
            if target_role:
                member_roles = getattr(member, "roles", [])
                if any(getattr(r, "id", None) == target_role for r in member_roles):
                    return True
        return False

    def require_voice(self, interaction, *, dj=False):
        member = interaction.user
        lang = self.get_lang(interaction.guild_id)
        if not isinstance(member, discord.Member) or not member.voice or not member.voice.channel:
            raise PlexError("Entra prima in un canale vocale." if lang == "it" else "Join a voice channel first.")
        if isinstance(member.voice.channel, discord.StageChannel):
            raise PlexError("Usa un normale canale vocale: i canali Stage non sono supportati." if lang == "it" else "Stage channels are not supported. Please use a normal voice channel.")
        voice = interaction.guild.voice_client
        if voice and voice.channel.id != member.voice.channel.id:
            raise PlexError("Devi essere nello stesso canale vocale del bot." if lang == "it" else "You must be in the same voice channel as the bot.")
        settings = self.store.get(interaction.guild_id)
        if (dj or settings.dj_only) and not self.can_control(interaction.guild, member, settings):
            dj_role_obj = interaction.guild.get_role(settings.dj_role) if settings.dj_role and hasattr(interaction.guild, "get_role") else None
            if lang == "it":
                role_hint = f" o il ruolo @{dj_role_obj.name}" if dj_role_obj else ""
                raise PlexError(f"I controlli della musica sono riservati: serve il permesso Gestisci Server{role_hint}.")
            role_hint = f" or the @{dj_role_obj.name} role" if dj_role_obj else ""
            raise PlexError(f"Music controls are restricted: Manage Server permission{role_hint} is required.")
        return member.voice.channel

    async def enqueue(self, interaction, track):
        channel = self.require_voice(interaction)
        await self.player(interaction.guild).add(channel, track, interaction.channel)

    async def on_voice_state_update(self, member, before, after):
        if self.user and member.id == self.user.id and after.channel is None:
            player = self.players.get(member.guild.id)
            if player:
                player.stop()
                player.wake.set()
        elif before.channel != after.channel:
            player = self.players.get(member.guild.id)
            if player and player.current:
                self.presence.notify(player, None)

    async def on_guild_remove(self, guild):
        await self.disconnect(guild.id)
        self.players.pop(guild.id, None)
        self.locks.pop(guild.id, None)
        login = self.logins.pop(guild.id, None)
        if login:
            login.stop()

    async def close(self):
        if self.is_closed():
            return
        for view in self.logins.values():
            view.stop()
        for player in list(self.players.values()):
            with contextlib.suppress(Exception):
                await player.close()
        with contextlib.suppress(Exception):
            await self.presence.close()
        await self.activity_server.close()
        if self.http_session:
            await self.http_session.close()
        self.store.close()
        await super().close()

    def register_commands(self):
        plex = app_commands.Group(name="plex", description="Plex login, servers, and libraries", guild_only=True,
                                  default_permissions=discord.Permissions(manage_guild=True))
        self.tree.add_command(plex)

        @plex.command(name="login", description="Connect Plex via secure browser authentication")
        @app_commands.checks.has_permissions(manage_guild=True)
        @app_commands.checks.cooldown(1, 15, key=lambda i: i.guild_id)
        async def login(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            async with self.config_lock(interaction.guild_id):
                pin, url, expiry = await self.plex.pin()
                old = self.logins.get(interaction.guild_id)
                if old:
                    old.stop()
                lang = self.get_lang(interaction.guild_id)
                view = LoginView(self, interaction.user.id, interaction.guild_id, pin, url, expiry,
                                 self.store.get(interaction.guild_id).revision, lang=lang)
                self.logins[interaction.guild_id] = view
                prompt = self.t(interaction.guild_id, "login_prompt", expiry=expiry // 60)
                await reply(interaction, prompt, view=view)

        @plex.command(name="logout", description="Disconnect Plex and remove local credentials")
        @app_commands.checks.has_permissions(manage_guild=True)
        async def logout(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            async with self.config_lock(interaction.guild_id):
                await self.disconnect(interaction.guild_id)
                settings = self.store.get(interaction.guild_id)
                settings.token = settings.server_token = settings.server_id = settings.server_name = settings.server_url = ""
                settings.address_override = ""
                settings.libraries = None
                self.store.save(interaction.guild_id, settings)
                view = self.logins.pop(interaction.guild_id, None)
                if view:
                    view.stop()
            await reply(interaction, self.t(interaction.guild_id, "logout_done"))

        @plex.command(name="servers", description="List Plex servers accessible to your account")
        @app_commands.checks.has_permissions(manage_guild=True)
        async def servers(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            settings = self.store.get(interaction.guild_id)
            if not settings.token:
                raise PlexError(self.t(interaction.guild_id, "plex_login_first"))
            resources = await self.plex.resources(settings.token)
            lines = [f"**{text(r['name'])}** — `{r['clientIdentifier']}`" for r in resources]
            heading = self.t(interaction.guild_id, "plex_servers_heading")
            await self.send_lines(interaction, heading, lines)

        @plex.command(name="server", description="Select a Plex server for this Discord server")
        @app_commands.describe(id="Server ID shown by /plex servers")
        @app_commands.checks.has_permissions(manage_guild=True)
        async def server(interaction: discord.Interaction, id: str):
            await interaction.response.defer(ephemeral=True)
            async with self.config_lock(interaction.guild_id):
                settings = self.store.get(interaction.guild_id)
                if not settings.token:
                    raise PlexError(self.t(interaction.guild_id, "plex_login_first"))
                resources = await self.plex.resources(settings.token)
                resource = next((r for r in resources if r["clientIdentifier"] == id), None)
                if not resource:
                    raise PlexError(self.t(interaction.guild_id, "plex_server_not_found"))
                url, token = await self.plex.connect(resource, settings.address_override)
                await self.disconnect(interaction.guild_id)
                settings.server_id, settings.server_name = id, resource["name"]
                settings.server_url, settings.server_token = url, token
                settings.libraries = None
                self.store.save(interaction.guild_id, settings)
            msg = self.t(interaction.guild_id, "plex_server_selected", server=text(settings.server_name))
            await reply(interaction, msg)

        @server.autocomplete("id")
        async def server_autocomplete(interaction: discord.Interaction, current: str):
            with contextlib.suppress(Exception):
                settings = self.store.get(interaction.guild_id)
                if settings.token:
                    resources = await self.plex.resources(settings.token)
                    needle = current.casefold()
                    return [
                        app_commands.Choice(name=f"{r['name']} ({r['clientIdentifier'][:8]})"[:100], value=r["clientIdentifier"][:100])
                        for r in resources
                        if not needle or needle in r["name"].casefold() or needle in r["clientIdentifier"].casefold()
                    ][:25]
            return []

        @plex.command(name="address", description="Manual Plex address (LAN/Docker); leave empty for automatic")
        @app_commands.checks.has_permissions(manage_guild=True)
        async def address(interaction: discord.Interaction, url: str | None = None):
            await interaction.response.defer(ephemeral=True)
            override = valid_url(url) if url else ""
            async with self.config_lock(interaction.guild_id):
                settings = self.store.get(interaction.guild_id)
                if settings.server_id:
                    resources = await self.plex.resources(settings.token)
                    resource = next((r for r in resources if r["clientIdentifier"] == settings.server_id), None)
                    if not resource:
                        raise PlexError(self.t(interaction.guild_id, "plex_server_inaccessible"))
                    actual_url, token = await self.plex.connect(resource, override)
                    await self.disconnect(interaction.guild_id)
                    settings.server_url, settings.server_token = actual_url, token
                settings.address_override = override
                self.store.save(interaction.guild_id, settings)
            msg = self.t(interaction.guild_id, "plex_address_updated" if override else "plex_address_auto")
            await reply(interaction, msg)

        @plex.command(name="libraries", description="List music libraries and their IDs")
        @app_commands.checks.has_permissions(manage_guild=True)
        async def libraries(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            settings = self.store.get(interaction.guild_id)
            libs = await self.plex.libraries(settings)
            heading = self.t(interaction.guild_id, "plex_libs_heading")
            await self.send_lines(interaction, heading, [
                f"{'✅' if settings.libraries is None or lib.id in settings.libraries else '❌'} **{text(lib.title)}** — ID `{lib.id}`"
                for lib in libs
            ])

        @plex.command(name="library", description="Enable or disable a library in searches")
        @app_commands.checks.has_permissions(manage_guild=True)
        async def library(interaction: discord.Interaction, id: str, enabled: bool):
            await interaction.response.defer(ephemeral=True)
            async with self.config_lock(interaction.guild_id):
                settings = self.store.get(interaction.guild_id)
                libs = await self.plex.libraries(settings)
                if id not in [lib.id for lib in libs]:
                    raise PlexError(self.t(interaction.guild_id, "plex_lib_not_found"))
                ids = set(settings.libraries if settings.libraries is not None else [lib.id for lib in libs])
                ids.add(id) if enabled else ids.discard(id)
                await self.disconnect(interaction.guild_id)
                settings.libraries = sorted(ids)
                self.store.save(interaction.guild_id, settings)
            msg = self.t(interaction.guild_id, "plex_lib_enabled" if enabled else "plex_lib_disabled")
            await reply(interaction, msg)

        @library.autocomplete("id")
        async def plex_library_autocomplete(interaction: discord.Interaction, current: str):
            with contextlib.suppress(Exception):
                settings = self.store.get(interaction.guild_id)
                libs = await self.plex.libraries(settings)
                needle = current.casefold()
                return [
                    app_commands.Choice(name=f"{lib.title} (ID {lib.id})"[:100], value=lib.id[:100])
                    for lib in libs
                    if not needle or needle in lib.title.casefold() or needle in lib.id.casefold()
                ][:25]
            return []

        @plex.command(name="all", description="Enable all music libraries, including future additions")
        @app_commands.checks.has_permissions(manage_guild=True)
        async def all_libraries(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            async with self.config_lock(interaction.guild_id):
                settings = self.store.get(interaction.guild_id)
                settings.libraries = None
                self.store.save(interaction.guild_id, settings)
            await reply(interaction, self.t(interaction.guild_id, "plex_all_libs_done"))

        @self.tree.command(name="settings", description="View or adjust volume, bitrate, queue limit, timeout, DJ controls, and language")
        @app_commands.guild_only()
        @app_commands.default_permissions(manage_guild=True)
        @app_commands.checks.has_permissions(manage_guild=True)
        @app_commands.describe(volume="0–150%, applied instantly", bitrate="Opus quality, kbps (next track)",
                               idle_seconds="Seconds before leaving when queue is empty", max_queue="Maximum songs allowed in queue",
                               dj_only="Restrict controls to Admin and DJ role (True) or allow everyone (False)",
                               dj_role="Optional DJ role", clear_dj="Remove the DJ role",
                               language="Bot language ('en' for English, 'it' for Italian)")
        @app_commands.choices(language=[
            app_commands.Choice(name="English (Default)", value="en"),
            app_commands.Choice(name="Italiano", value="it"),
        ])
        async def settings_command(interaction: discord.Interaction,
                                   volume: app_commands.Range[int, 0, 150] | None = None,
                                   bitrate: app_commands.Range[int, 32, 320] | None = None,
                                   idle_seconds: app_commands.Range[int, 15, 1800] | None = None,
                                   max_queue: app_commands.Range[int, 1, 500] | None = None,
                                   dj_only: bool | None = None,
                                   dj_role: discord.Role | None = None, clear_dj: bool = False,
                                   language: str | None = None):
            await interaction.response.defer(ephemeral=True)
            if dj_role and clear_dj:
                raise PlexError(self.t(interaction.guild_id, "settings_conflict_dj"))
            async with self.config_lock(interaction.guild_id):
                settings = self.store.get(interaction.guild_id)
                changed = False
                for name, value in (("volume", volume), ("bitrate", bitrate), ("idle_seconds", idle_seconds), ("max_queue", max_queue), ("dj_only", dj_only)):
                    if value is not None:
                        setattr(settings, name, value)
                        changed = True
                if dj_role or clear_dj:
                    settings.dj_role = dj_role.id if dj_role else None
                    changed = True
                if language is not None and language in ("en", "it"):
                    settings.language = language
                    changed = True
                if changed:
                    self.store.save(interaction.guild_id, settings)
                if volume is not None and interaction.guild_id in self.players:
                    self.players[interaction.guild_id].set_volume(settings.volume)
            lang = settings.language or "en"
            if settings.dj_only:
                dj_role_obj = interaction.guild.get_role(settings.dj_role) if settings.dj_role and hasattr(interaction.guild, "get_role") else None
                if lang == "it":
                    dj_text = f"Admin + @{dj_role_obj.name}" if dj_role_obj else "Solo Amministratori (nessun ruolo DJ impostato)"
                    control_text = f"Riservato ({dj_text})"
                else:
                    dj_text = f"Admin + @{dj_role_obj.name}" if dj_role_obj else "Admins only (no DJ role set)"
                    control_text = f"Restricted ({dj_text})"
            else:
                control_text = "Tutti gli utenti nel canale vocale" if lang == "it" else "All users in voice channel"
            srv_label = settings.server_name or ("non configurato" if lang == "it" else "not configured")
            lang_label = "Italiano" if lang == "it" else "English"
            if lang == "it":
                res = (f"Server Plex: **{text(srv_label)}**\n"
                       f"Volume: {settings.volume}% (in tempo reale) · Opus: {settings.bitrate} kbps\n"
                       f"Uscita dopo: {settings.idle_seconds}s · Limite coda: {settings.max_queue}\n"
                       f"Lingua: {lang_label}\n"
                       f"Controllo musica: {control_text}.")
            else:
                res = (f"Plex Server: **{text(srv_label)}**\n"
                       f"Volume: {settings.volume}% (real-time) · Opus: {settings.bitrate} kbps\n"
                       f"Idle timeout: {settings.idle_seconds}s · Queue limit: {settings.max_queue}\n"
                       f"Language: {lang_label}\n"
                       f"Music controls: {control_text}.")
            await reply(interaction, res)

        @self.tree.command(name="play", description="Search for a Plex track by title or artist and queue it")
        @app_commands.guild_only()
        @app_commands.describe(query="Track title or artist name", library="Optional: music library")
        @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
        async def play(interaction: discord.Interaction, query: str, library: str | None = None):
            self.require_voice(interaction)
            query = query.strip()
            if not query or len(query) > 200:
                raise PlexError(self.t(interaction.guild_id, "play_query_len"))
            await interaction.response.defer(ephemeral=False)
            settings = self.store.get(interaction.guild_id)
            cached = self.track_cache.get((interaction.guild_id, query))
            if cached:
                tracks = [cached]
            else:
                tracks = await self.plex.search(settings, query, library)
            if not tracks:
                await reply(interaction, self.t(interaction.guild_id, "play_no_tracks"), ephemeral=False)
            elif len(tracks) == 1:
                async with self.config_lock(interaction.guild_id):
                    if self.store.get(interaction.guild_id).revision != settings.revision:
                        raise PlexError(self.t(interaction.guild_id, "cfg_changed_play"))
                    await self.enqueue(interaction, tracks[0])
                msg = self.t(interaction.guild_id, "trackview_queued", title=text(tracks[0].label), library=text(tracks[0].library))
                await reply(interaction, msg, view=self.player_view(interaction), ephemeral=False)
            else:
                lang = self.get_lang(interaction.guild_id)
                view = TrackView(self, interaction, tracks, settings.revision, lang=lang)
                await reply(interaction, view.caption, view=view, ephemeral=False)

        @play.autocomplete("query")
        async def play_query_autocomplete(interaction: discord.Interaction, current: str):
            query = current.strip()
            if len(query) < 2:
                return []
            with contextlib.suppress(Exception):
                settings = self.store.get(interaction.guild_id)
                lib = getattr(interaction.namespace, "library", None)
                tracks = await self.plex.search(settings, query, lib)
                choices = []
                for t in tracks[:25]:
                    key = f"track:{t.id}"
                    self.track_cache[(interaction.guild_id, key)] = t
                    if len(self.track_cache) > 500:
                        self.track_cache.pop(next(iter(self.track_cache)))
                    choices.append(app_commands.Choice(name=f"{t.label} · {t.library}"[:100], value=key))
                return choices
            return []

        @play.autocomplete("library")
        async def play_library_autocomplete(interaction: discord.Interaction, current: str):
            with contextlib.suppress(Exception):
                settings = self.store.get(interaction.guild_id)
                libs = await self.plex.libraries(settings)
                enabled = [lib for lib in libs if settings.libraries is None or lib.id in settings.libraries]
                needle = current.casefold()
                return [
                    app_commands.Choice(name=f"{lib.title} (ID {lib.id})"[:100], value=lib.id[:100])
                    for lib in enabled
                    if not needle or needle in lib.title.casefold() or needle in lib.id.casefold()
                ][:25]
            return []

        @self.tree.command(name="queue", description="Show current track, playback queue, and controls")
        @app_commands.guild_only()
        async def queue(interaction: discord.Interaction, page: app_commands.Range[int, 1, 50] = 1):
            player = self.players.get(interaction.guild_id)
            if not player or (not player.current and not player.queue):
                await reply(interaction, self.t(interaction.guild_id, "queue_empty"), ephemeral=False)
                return
            items = list(player.queue)
            start = (page - 1) * 10
            lang = self.get_lang(interaction.guild_id)
            current = text(player.current.label) if player.current else ("nessuno" if lang == "it" else "none")
            lines = [f"{i + start + 1}. {text(t.label, 110)} · {text(t.library, 35)}" for i, t in enumerate(items[start:start + 10])]
            if lang == "it":
                empty_page = "Nessun brano in questa pagina."
                body = f"**In riproduzione:** {current}\n**Coda:** {len(items)} brani · pagina {page}\n" + ("\n".join(lines) or empty_page)
            else:
                empty_page = "No tracks on this page."
                body = f"**Now Playing:** {current}\n**Queue:** {len(items)} tracks · page {page}\n" + ("\n".join(lines) or empty_page)
            await reply(interaction, body, view=self.player_view(interaction), ephemeral=False)

        @self.tree.command(name="now", description="Show current track, elapsed time, and controls")
        @app_commands.guild_only()
        async def now(interaction: discord.Interaction):
            player = self.players.get(interaction.guild_id)
            if not player or not player.current:
                await reply(interaction, self.t(interaction.guild_id, "now_nothing"), ephemeral=False)
                return
            track = player.current
            state = "⏸️" if player.paused_at else "🎵"
            await reply(
                interaction,
                f"{state} **{text(track.label)}**\n{text(track.album)} · {text(track.library)}\n"
                f"{duration(player.elapsed)} / {duration(track.duration // 1000)}",
                view=self.player_view(interaction), ephemeral=False,
            )

        def register_control(name, description):
            async def control(interaction: discord.Interaction):
                await interaction.response.defer(ephemeral=False)
                async with self.config_lock(interaction.guild_id):
                    self.require_voice(interaction)
                    player = self.players.get(interaction.guild_id)
                    voice = interaction.guild.voice_client
                    if not player or not voice:
                        raise PlexError(self.t(interaction.guild_id, "player_not_connected"))
                    if name == "leave":
                        await player.close()
                        message = self.t(interaction.guild_id, "ctrl_msg_leave")
                    elif name == "pause" and voice.is_paused():
                        player.resume()
                        message = self.t(interaction.guild_id, "ctrl_msg_resume")
                    else:
                        getattr(player, name)()
                        message = self.t(interaction.guild_id, f"ctrl_msg_{name}")
                view = None if name in ("stop", "leave") else self.player_view(interaction)
                await reply(interaction, message, view=view, ephemeral=False)
            control.__name__ = name
            self.tree.add_command(app_commands.guild_only()(app_commands.Command(name=name, description=description, callback=control)))

        for name, description in (("pause", "Pause or resume playback"), ("resume", "Resume playback"),
                                  ("skip", "Skip the current track"), ("stop", "Stop playback and clear queue"),
                                  ("leave", "Leave the voice channel"), ("shuffle", "Shuffle upcoming songs in queue")):
            register_control(name, description)

        @self.tree.command(name="activity", description="Launch Discord Activity (Embedded App SDK) or open Web Player in voice channel")
        @app_commands.guild_only()
        async def activity_command(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            self.require_voice(interaction)
            await self.send_activity_prompt(interaction)

        @self.tree.command(name="mode", description="Switch between Slash Commands and Activity Mode")
        @app_commands.guild_only()
        @app_commands.describe(modalita="Choose operating mode (leave empty to toggle)")
        @app_commands.choices(modalita=[
            app_commands.Choice(name="🎛️ Activity (Control and configure everything from Activity)", value="activity"),
            app_commands.Choice(name="💬 Slash Commands (Classic command mode)", value="commands"),
        ])
        async def mode_command(interaction: discord.Interaction, modalita: str | None = None):
            await interaction.response.defer(ephemeral=False)
            async with self.config_lock(interaction.guild_id):
                settings = self.store.get(interaction.guild_id)
                new_mode = modalita if modalita in ("activity", "commands") else ("activity" if settings.mode != "activity" else "commands")
                settings.mode = new_mode
                self.store.save(interaction.guild_id, settings)
            lang = settings.language or "en"
            if new_mode == "activity":
                heading = (
                    "✅ **Modalità Activity attivata!**\nOra puoi cercare canzoni, riprodurle subito o metterle in coda e configurare Plex direttamente dall'Attività.\n*(Usa `/mode` in qualsiasi momento per tornare ai comandi classici)*"
                    if lang == "it" else
                    "✅ **Activity Mode activated!**\nYou can now search songs, play them instantly or queue them, and configure Plex directly from the Activity.\n*(Use `/mode` anytime to return to classic slash commands)*"
                )
                await self.send_activity_prompt(interaction, heading=heading)
            else:
                msg = (
                    "✅ **Modalità Comandi Slash attivata!**\nTutti i comandi classici (`/play`, `/plex`, `/settings`, `/queue`, ecc.) sono nuovamente attivi. Usa `/mode` per passare alla modalità Activity."
                    if lang == "it" else
                    "✅ **Slash Commands Mode activated!**\nAll classic commands (`/play`, `/plex`, `/settings`, `/queue`, etc.) are now active. Use `/mode` to switch to Activity mode."
                )
                await reply(interaction, msg, ephemeral=False)

        @self.tree.command(name="link", description="Link your personal Plex account to Discord for listening sync and playlists")
        @app_commands.guild_only()
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def link_command(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            cid = f"{self.store.client_id}-u{interaction.user.id}"
            pin_id, code, auth_url, expiry = await self.plex.pin_code(client_id=cid)
            lang = self.get_lang(interaction.guild_id)
            view = UserLinkView(self, interaction.user.id, pin_id, cid, auth_url, expiry, lang=lang)
            existing = self.store.get_user(interaction.user.id)
            status = self.t(interaction.guild_id, "user_link_status_line", username=text(existing.plex_username)) if existing and existing.plex_username else ""
            prompt = self.t(interaction.guild_id, "user_link_prompt", status=status, code=code)
            await reply(interaction, prompt, view=view)

        @self.tree.command(name="playlist", description="Browse and play playlists from your linked Plex account")
        @app_commands.guild_only()
        @app_commands.describe(id="Optional: choose a Plex playlist", shuffle="Shuffle playlist tracks")
        async def playlist_command(interaction: discord.Interaction, id: str | None = None, shuffle: bool = False):
            channel = self.require_voice(interaction)
            link = self.store.get_user(interaction.user.id)
            if not link or not link.plex_token:
                raise PlexError(self.t(interaction.guild_id, "playlist_require_link"))
            await interaction.response.defer(ephemeral=False)
            settings = self.store.get(interaction.guild_id)
            playlists = await self.plex.playlists(settings, user_token=link.plex_token)
            if not playlists:
                await reply(interaction, self.t(interaction.guild_id, "playlist_none", username=text(link.plex_username)), ephemeral=False)
                return
            if id:
                pl = next((p for p in playlists if p.id == id or p.title.casefold() == id.strip().casefold()), None)
                if not pl:
                    raise PlexError(self.t(interaction.guild_id, "playlist_not_found"))
                async with self.config_lock(interaction.guild_id):
                    tracks = await self.plex.playlist_tracks(settings, pl.id, user_token=link.plex_token)
                    added = await self.player(interaction.guild).add_many(
                        channel, tracks, interaction.channel, shuffle_tracks=shuffle
                    )
                msg = self.t(interaction.guild_id, "playlist_added", count=added, title=text(pl.title))
                await reply(interaction, msg, view=self.player_view(interaction), ephemeral=False)
            else:
                lang = self.get_lang(interaction.guild_id)
                view = PlaylistView(self, playlists, link.plex_token, settings.revision, shuffle=shuffle, lang=lang)
                if lang == "it":
                    heading = f"🎶 **Playlist di {text(link.plex_username)}** ({len(playlists)} trovate):"
                else:
                    heading = f"🎶 **Playlists of {text(link.plex_username)}** ({len(playlists)} found):"
                await reply(interaction, heading, view=view, ephemeral=False)

        @playlist_command.autocomplete("id")
        async def playlist_autocomplete(interaction: discord.Interaction, current: str):
            with contextlib.suppress(Exception):
                link = self.store.get_user(interaction.user.id)
                if not link or not link.plex_token:
                    return []
                settings = self.store.get(interaction.guild_id)
                playlists = await self.plex.playlists(settings, user_token=link.plex_token)
                needle = current.casefold()
                unit = "brani" if settings.language == "it" else "tracks"
                return [
                    app_commands.Choice(name=f"{p.title} ({p.track_count} {unit})"[:100], value=p.id[:100])
                    for p in playlists
                    if not needle or needle in p.title.casefold()
                ][:25]
            return []

        @self.tree.command(name="unlink", description="Unlink your personal Plex account from Discord")
        @app_commands.guild_only()
        async def unlink_command(interaction: discord.Interaction):
            self.store.delete_user(interaction.user.id)
            await reply(interaction, self.t(interaction.guild_id, "user_unlink_done"))

        @self.tree.command(name="help", description="Quick reference guide to Plexcord commands")
        @app_commands.guild_only()
        async def help_command(interaction: discord.Interaction):
            lang = self.get_lang(interaction.guild_id)
            if lang == "it":
                help_text = (
                    "**Modalità, Activity, Playlist e Sincronizzazione Ascolto**\n"
                    "`/mode`: passa tra la **Modalità Comandi** e la **Modalità Activity** (dove puoi cercare, vedere le tue playlist, riprodurre e configurare tutto dall'interfaccia grafica).\n"
                    "`/activity`: apre la Discord Activity o il Web Player.\n"
                    "`/link` · `/unlink`: collega il tuo account Plex personale a Discord (con codice a 4 cifre su `plex.tv/link`) per mostrare l'attività di ascolto su Plex/Discord e accedere alle tue playlist.\n"
                    "`/playlist`: mostra e riproduce le playlist personali del tuo account Plex collegato.\n\n"
                    "**Configurazione (Gestisci server o da Activity)**\n"
                    "/plex login → /plex servers → /plex server → /plex libraries\n"
                    "/plex address: URL LAN/Docker opzionale\n/plex library: abilita/disabilita librerie · /plex all: tutte\n"
                    "/settings: volume (in tempo reale), bitrate, timeout, limite coda, permessi DJ e lingua\n/plex logout: scollega Plex\n\n"
                    "**Musica (per tutti nel canale vocale)**\n"
                    "Entra nel canale vocale e usa `/play query` (cerca per titolo o autore), `/playlist` o `/activity`.\n"
                    "Usa i **pulsanti sotto al player** (⏯️ ⏭️ 🔀 ⏹️ 👋) oppure i comandi:\n"
                    "/mode · /activity · /link · /playlist · /now · /queue [page] · /pause · /resume · /skip · /shuffle · /stop · /leave"
                )
            else:
                help_text = (
                    "**Modes, Activity, Playlists & Listening Sync**\n"
                    "`/mode`: switch between **Slash Commands** and **Activity Mode** (where you can search, view playlists, play tracks, and configure everything in a modern UI).\n"
                    "`/activity`: launch the Discord Activity (Embedded App) or open the Web Player.\n"
                    "`/link` · `/unlink`: link your personal Plex account to Discord (via a 4-digit PIN at `plex.tv/link`) to show your real-time listening status on Plex/Discord and access your playlists.\n"
                    "`/playlist`: browse and play your personal Plex playlists.\n\n"
                    "**Configuration (Manage Server or via Activity)**\n"
                    "/plex login → /plex servers → /plex server → /plex libraries\n"
                    "/plex address: optional LAN/Docker manual URL\n/plex library: enable/disable libraries · /plex all: enable all\n"
                    "/settings: real-time volume, Opus bitrate, idle timeout, queue limit, DJ controls, and language\n/plex logout: disconnect Plex\n\n"
                    "**Music Controls (for voice channel members)**\n"
                    "Join a voice channel and use `/play query` (search by title or artist), `/playlist`, or `/activity`.\n"
                    "Use the **buttons below the player** (⏯️ ⏭️ 🔀 ⏹️ 👋) or slash commands:\n"
                    "/mode · /activity · /link · /playlist · /now · /queue [page] · /pause · /resume · /skip · /shuffle · /stop · /leave"
                )
            await reply(interaction, help_text)

    @staticmethod
    async def send_lines(interaction, heading, lines):
        if not lines:
            await reply(interaction, heading + "\nNo items found.")
            return
        chunk = heading
        for line in lines:
            if len(chunk) + len(line) > 1800:
                await reply(interaction, chunk)
                chunk = heading
            chunk += "\n" + line
        await reply(interaction, chunk)
