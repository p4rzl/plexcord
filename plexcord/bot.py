import asyncio
import contextlib
import os

import aiohttp
import discord
from discord import app_commands

from .activity import ActivityServer
from .player import Player
from .plex import Playlist, Plex, PlexError, Track, valid_url
from .store import Store, UserLink


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
            await reply(interaction, "Usa i comandi all'interno di un server Discord, non in DM.")
            return False
        cmd = interaction.command
        root = cmd.root_parent.name if cmd and getattr(cmd, "root_parent", None) else (cmd.name if cmd else "")
        if root and root not in ("mode", "activity", "link", "unlink", "leave", "help"):
            settings = self.client.store.get(interaction.guild_id)
            if settings.mode == "activity":
                await self.client.send_activity_prompt(
                    interaction,
                    heading="🎛️ **Modalità Activity attiva:** usa l'Attività Discord o il Web Player qui sotto per cercare brani, gestire la coda e configurare Plex.\n*(Per tornare ai comandi slash classici usa `/mode`)*",
                )
                return False
        return True

    async def on_error(self, interaction, error):
        original = getattr(error, "original", error)
        if isinstance(original, PlexError):
            message = str(original)
        elif isinstance(error, app_commands.MissingPermissions):
            message = "Serve il permesso Gestisci server per configurare Plexcord."
        elif isinstance(error, app_commands.CommandOnCooldown):
            message = f"Attendi {error.retry_after:.0f} secondi prima di riprovare."
        elif isinstance(error, app_commands.CheckFailure):
            message = "Non hai i permessi per questo comando."
        else:
            message = "Operazione fallita. Controlla la configurazione e riprova."
        with contextlib.suppress(discord.HTTPException):
            await reply(interaction, message)


class OwnedView(discord.ui.View):
    def __init__(self, owner: int, timeout=180):
        super().__init__(timeout=timeout)
        self.owner = owner

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner:
            await reply(interaction, "Questo menu appartiene a un altro utente.")
            return False
        return True

    async def on_error(self, interaction, error, item):
        await reply(interaction, str(error) if isinstance(error, PlexError) else "Operazione fallita. Riprova con il comando.")


class LoginView(OwnedView):
    def __init__(self, bot, owner, guild_id, pin_id, url, timeout, revision):
        super().__init__(owner, timeout)
        self.bot = bot
        self.guild_id = guild_id
        self.pin_id = pin_id
        self.revision = revision
        self.add_item(discord.ui.Button(label="Autorizza su Plex", url=url))

    @discord.ui.button(label="Completa login", style=discord.ButtonStyle.success)
    async def complete(self, interaction, button):
        if not interaction.permissions.manage_guild:
            raise PlexError("Serve il permesso Gestisci server.")
        await interaction.response.defer(ephemeral=True)
        async with self.bot.config_lock(self.guild_id):
            settings = self.bot.store.get(self.guild_id)
            if settings.revision != self.revision or self.bot.logins.get(self.guild_id) is not self:
                raise PlexError("Login superato da una nuova configurazione. Ripeti /plex login.")
            token = await self.bot.plex.check_pin(self.pin_id)
            if not token:
                await reply(interaction, "Autorizza prima il bot su Plex, poi premi nuovamente Completa login.")
                return
            await self.bot.disconnect(self.guild_id)
            settings.token = token
            settings.server_token = settings.server_id = settings.server_name = settings.server_url = ""
            settings.libraries = None
            self.bot.store.save(self.guild_id, settings)
            self.stop()
            await interaction.edit_original_response(content="✅ Login completato. Usa /plex servers e /plex server per scegliere il server.", view=None)


class UserLinkView(OwnedView):
    def __init__(self, bot, owner, pin_id, client_id, url, timeout):
        super().__init__(owner, timeout)
        self.bot = bot
        self.pin_id = pin_id
        self.client_id = client_id
        self.add_item(discord.ui.Button(label="Apri plex.tv/link", url="https://plex.tv/link"))
        self.add_item(discord.ui.Button(label="Link diretto", url=url))

    @discord.ui.button(label="Completa collegamento", style=discord.ButtonStyle.success)
    async def complete(self, interaction, button):
        await interaction.response.defer(ephemeral=True)
        token = await self.bot.plex.check_pin(self.pin_id, client_id=self.client_id)
        if not token:
            await reply(interaction, "Inserisci prima il codice a 4 caratteri su https://plex.tv/link, poi premi nuovamente **Completa collegamento**.")
            return
        plex_user = await self.bot.plex.user_info(token)
        d_name = getattr(interaction.user, "display_name", None) or interaction.user.name
        self.bot.store.save_user(UserLink(discord_id=interaction.user.id, plex_token=token, plex_username=plex_user, discord_name=d_name))
        self.stop()
        player = self.bot.players.get(interaction.guild_id)
        if player and player.current:
            asyncio.create_task(player.sync_timeline("paused" if player.paused_at else "playing", player.current))
        await interaction.edit_original_response(
            content=f"🎧 Account Plex **{text(plex_user)}** collegato al tuo profilo Discord! La tua attività di ascolto verrà mostrata su Plex e Discord.",
            view=None,
        )


class VoiceView(discord.ui.View):
    """Menu e controlli utilizzabili da chiunque si trovi nel canale vocale."""

    def __init__(self, bot, timeout=300):
        super().__init__(timeout=timeout)
        self.bot = bot

    async def interaction_check(self, interaction):
        if self.bot is not None:
            self.bot.require_voice(interaction)
        return True

    async def on_error(self, interaction, error, item):
        original = getattr(error, "original", error)
        await reply(interaction, str(original) if isinstance(original, PlexError) else "Operazione fallita. Riprova con il comando.")


class PlayerView(VoiceView):
    def __init__(self, bot, guild_id: int = 0, channel_id: int = 0):
        super().__init__(bot, timeout=600)
        if bot and getattr(bot, "activity_url", "") and guild_id:
            token = bot.activity_server.sign(guild_id, channel_id)
            url = f"{bot.activity_url}/?guild_id={guild_id}&channel_id={channel_id}&token={token}"
            self.add_item(discord.ui.Button(label="Web Player", emoji="🎛️", url=url, row=1))

    @discord.ui.button(label="Pausa/Riprendi", emoji="⏯️", style=discord.ButtonStyle.primary)
    async def toggle_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        async with self.bot.config_lock(interaction.guild_id):
            self.bot.require_voice(interaction)
            player = self.bot.players.get(interaction.guild_id)
            voice = interaction.guild.voice_client
            if not player or not voice:
                raise PlexError("Il bot non è connesso a un canale vocale.")
            if voice.is_paused():
                player.resume()
                state = "▶️ Riproduzione ripresa"
            else:
                player.pause()
                state = "⏸️ In pausa"
        await reply(interaction, f"{state} da **{text(interaction.user.display_name, 40)}**.", ephemeral=False)

    @discord.ui.button(label="Salta", emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        async with self.bot.config_lock(interaction.guild_id):
            self.bot.require_voice(interaction)
            player = self.bot.players.get(interaction.guild_id)
            if not player or not interaction.guild.voice_client:
                raise PlexError("Il bot non è connesso a un canale vocale.")
            player.skip()
        await reply(interaction, f"⏭️ Brano saltato da **{text(interaction.user.display_name, 40)}**.", ephemeral=False)

    @discord.ui.button(label="Mescola", emoji="🔀", style=discord.ButtonStyle.secondary)
    async def shuffle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        async with self.bot.config_lock(interaction.guild_id):
            self.bot.require_voice(interaction)
            player = self.bot.players.get(interaction.guild_id)
            if not player or not interaction.guild.voice_client:
                raise PlexError("Il bot non è connesso a un canale vocale.")
            player.shuffle()
        await reply(interaction, f"🔀 Coda mescolata da **{text(interaction.user.display_name, 40)}**.", ephemeral=False)

    @discord.ui.button(label="Stop", emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        async with self.bot.config_lock(interaction.guild_id):
            self.bot.require_voice(interaction)
            player = self.bot.players.get(interaction.guild_id)
            if not player or not interaction.guild.voice_client:
                raise PlexError("Il bot non è connesso a un canale vocale.")
            player.stop()
        await reply(interaction, f"⏹️ Riproduzione fermata e coda svuotata da **{text(interaction.user.display_name, 40)}**.", ephemeral=False)

    @discord.ui.button(label="Esci", emoji="👋", style=discord.ButtonStyle.danger)
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        async with self.bot.config_lock(interaction.guild_id):
            self.bot.require_voice(interaction)
            player = self.bot.players.get(interaction.guild_id)
            if not player or not interaction.guild.voice_client:
                raise PlexError("Il bot non è connesso a un canale vocale.")
            await player.close()
        await reply(interaction, f"👋 Disconnesso da **{text(interaction.user.display_name, 40)}**.", ephemeral=False)


class TrackView(VoiceView):
    def __init__(self, bot, interaction, tracks: list[Track], revision):
        super().__init__(bot, timeout=180)
        self.revision = revision
        self.tracks = tracks
        self.page = 0
        self.select = discord.ui.Select(row=0)
        self.select.callback = self.selected
        self.add_item(self.select)
        self.refresh()

    @property
    def caption(self):
        pages = (len(self.tracks) + 24) // 25
        return (f"{len(self.tracks)} risultati · pagina {self.page + 1}/{pages}. "
                "Chiunque nel canale vocale può scegliere un brano o scorrere le pagine.")

    def refresh(self):
        start = self.page * 25
        self.select.options = [
            discord.SelectOption(
                label=t.label[:100], value=str(i),
                description=(f"{duration(t.duration // 1000)} · {t.library} · {t.album}" if t.duration else f"{t.library} · {t.album}")[:100],
            )
            for i, t in enumerate(self.tracks[start:start + 25], start)
        ]
        self.select.placeholder = f"Scegli un brano · pagina {self.page + 1}"
        self.previous.disabled = self.page == 0
        self.next_page.disabled = start + 25 >= len(self.tracks)

    @discord.ui.button(label="Indietro", row=1)
    async def previous(self, interaction, button):
        self.page = max(0, self.page - 1)
        self.refresh()
        await interaction.response.edit_message(content=self.caption, view=self)

    @discord.ui.button(label="Avanti", row=1)
    async def next_page(self, interaction, button):
        self.page = min((len(self.tracks) - 1) // 25, self.page + 1)
        self.refresh()
        await interaction.response.edit_message(content=self.caption, view=self)

    async def selected(self, interaction):
        await interaction.response.defer()
        async with self.bot.config_lock(interaction.guild_id):
            if self.bot.store.get(interaction.guild_id).revision != self.revision:
                raise PlexError("Configurazione cambiata. Ripeti /play.")
            track = self.tracks[int(self.select.values[0])]
            await self.bot.enqueue(interaction, track)
            self.stop()
            await interaction.edit_original_response(
                content=f"✅ In coda: **{text(track.label)}** · {text(track.library)}",
                view=self.bot.player_view(interaction),
            )


class PlaylistView(VoiceView):
    def __init__(self, bot, playlists: list[Playlist], user_token: str, revision: int, shuffle: bool = False):
        super().__init__(bot, timeout=180)
        self.playlists = playlists[:25]
        self.user_token = user_token
        self.revision = revision
        self.shuffle = shuffle
        self.select = discord.ui.Select(
            placeholder="Scegli una tua playlist Plex da riprodurre...",
            options=[
                discord.SelectOption(
                    label=p.title[:100],
                    value=p.id,
                    description=f"{p.track_count} brani · {duration(p.duration // 1000)}"[:100],
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
                raise PlexError("Configurazione cambiata. Ripeti /playlist.")
            channel = self.bot.require_voice(interaction)
            pid = self.select.values[0]
            pl = next((p for p in self.playlists if p.id == pid), None)
            tracks = await self.bot.plex.playlist_tracks(settings, pid, user_token=self.user_token)
            added = await self.bot.player(interaction.guild).add_many(
                channel, tracks, interaction.channel, shuffle_tracks=self.shuffle
            )
            self.stop()
            title = pl.title if pl else pid
            await interaction.edit_original_response(
                content=f"🎶 Aggiunti **{added} brani** dalla playlist **{text(title)}**!",
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
        self.register_commands()

    async def setup_hook(self):
        self.http_session = aiohttp.ClientSession()
        self.plex = Plex(self.http_session, self.store.client_id)
        await self.activity_server.start()
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
        print(f"Plexcord connesso come {self.user} · {len(self.guilds)} server", flush=True)

    def config_lock(self, guild_id):
        return self.locks.setdefault(guild_id, asyncio.Lock())

    def player(self, guild):
        if guild.id not in self.players:
            self.players[guild.id] = Player(guild, self.plex, self.store, bot=self)
        return self.players[guild.id]

    def player_view(self, interaction):
        voice = getattr(interaction.guild, "voice_client", None)
        channel_id = voice.channel.id if voice and getattr(voice, "channel", None) else 0
        if not channel_id and getattr(interaction.user, "voice", None) and interaction.user.voice.channel:
            channel_id = interaction.user.voice.channel.id
        return PlayerView(self, interaction.guild_id or 0, channel_id)

    async def send_activity_prompt(self, interaction: discord.Interaction, heading: str = "🎛️ **Plexcord Activity & Web Player**"):
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
                view.add_item(discord.ui.Button(label="Avvia Discord Activity", emoji="🚀", url=invite.url))
                lines.append("• Premi **Avvia Discord Activity** (oppure l'icona del razzo 🚀 nel canale vocale) per aprirla dentro Discord.")
        base_url = self.activity_url or f"http://localhost:{self.activity_server.port}"
        web_url = f"{base_url}/?guild_id={interaction.guild_id}&channel_id={channel_id}&token={token}"
        view.add_item(discord.ui.Button(label="Apri Web Player", emoji="🌐", url=web_url))
        lines.append("• Premi **Apri Web Player** per cercare brani, gestire coda, volume e configurazione dal browser.")
        await reply(interaction, "\n".join(lines), view=view)

    async def disconnect(self, guild_id):
        if guild_id in self.players:
            await self.players[guild_id].close()

    def require_voice(self, interaction, *, dj=False):
        member = interaction.user
        if not isinstance(member, discord.Member) or not member.voice or not member.voice.channel:
            raise PlexError("Entra prima in un canale vocale.")
        if isinstance(member.voice.channel, discord.StageChannel):
            raise PlexError("Usa un normale canale vocale: i canali Stage non sono supportati.")
        voice = interaction.guild.voice_client
        if voice and voice.channel.id != member.voice.channel.id:
            raise PlexError("Devi essere nello stesso canale vocale del bot.")
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
        await self.activity_server.close()
        if self.http_session:
            await self.http_session.close()
        self.store.close()
        await super().close()

    def register_commands(self):
        plex = app_commands.Group(name="plex", description="Login, server e librerie Plex", guild_only=True,
                                  default_permissions=discord.Permissions(manage_guild=True))
        self.tree.add_command(plex)

        @plex.command(name="login", description="Collega Plex tramite autorizzazione sicura nel browser")
        @app_commands.checks.has_permissions(manage_guild=True)
        @app_commands.checks.cooldown(1, 15, key=lambda i: i.guild_id)
        async def login(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            async with self.config_lock(interaction.guild_id):
                pin, url, expiry = await self.plex.pin()
                old = self.logins.get(interaction.guild_id)
                if old:
                    old.stop()
                view = LoginView(self, interaction.user.id, interaction.guild_id, pin, url, expiry,
                                 self.store.get(interaction.guild_id).revision)
                self.logins[interaction.guild_id] = view
                await reply(interaction, f"1. Autorizza Plexcord su Plex.\n2. Torna qui e premi **Completa login**.\nIl link scade tra {expiry // 60} minuti. Il tuo account sarà usato per questo server Discord.", view=view)

        @plex.command(name="logout", description="Rimuove credenziali Plex e interrompe la musica")
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
            await reply(interaction, "Credenziali locali rimosse. Per revocare anche l'autorizzazione, rimuovi Plexcord dai dispositivi autorizzati del tuo account Plex.")

        @plex.command(name="servers", description="Elenca i server Plex accessibili al tuo account")
        @app_commands.checks.has_permissions(manage_guild=True)
        async def servers(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            settings = self.store.get(interaction.guild_id)
            if not settings.token:
                raise PlexError("Esegui prima /plex login.")
            resources = await self.plex.resources(settings.token)
            lines = [f"**{text(r['name'])}** — `{r['clientIdentifier']}`" for r in resources]
            # Pagine separate per non nascondere server oltre il limite di Discord.
            await self.send_lines(interaction, "Server Plex (usa l'ID con /plex server):", lines)

        @plex.command(name="server", description="Seleziona un server Plex per questo server Discord")
        @app_commands.describe(id="ID del server mostrato da /plex servers")
        @app_commands.checks.has_permissions(manage_guild=True)
        async def server(interaction: discord.Interaction, id: str):
            await interaction.response.defer(ephemeral=True)
            async with self.config_lock(interaction.guild_id):
                settings = self.store.get(interaction.guild_id)
                if not settings.token:
                    raise PlexError("Esegui prima /plex login.")
                resources = await self.plex.resources(settings.token)
                resource = next((r for r in resources if r["clientIdentifier"] == id), None)
                if not resource:
                    raise PlexError("ID non trovato. Usa /plex servers.")
                url, token = await self.plex.connect(resource, settings.address_override)
                await self.disconnect(interaction.guild_id)
                settings.server_id, settings.server_name = id, resource["name"]
                settings.server_url, settings.server_token = url, token
                settings.libraries = None
                self.store.save(interaction.guild_id, settings)
            await reply(interaction, f"✅ Server: **{text(settings.server_name)}**. Tutte le librerie musicali sono abilitate. Usa /plex libraries.")

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

        @plex.command(name="address", description="Indirizzo Plex manuale (LAN/Docker); senza URL torna automatico")
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
                        raise PlexError("Server non più accessibile. Ripeti /plex server.")
                    actual_url, token = await self.plex.connect(resource, override)
                    await self.disconnect(interaction.guild_id)
                    settings.server_url, settings.server_token = actual_url, token
                settings.address_override = override
                self.store.save(interaction.guild_id, settings)
            await reply(interaction, "Indirizzo aggiornato." if override else "Rilevamento automatico ripristinato.")

        @plex.command(name="libraries", description="Elenca tutte le librerie musicali e i loro ID")
        @app_commands.checks.has_permissions(manage_guild=True)
        async def libraries(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            settings = self.store.get(interaction.guild_id)
            libraries = await self.plex.libraries(settings)
            await self.send_lines(interaction, "Librerie musicali:", [
                f"{'✅' if settings.libraries is None or lib.id in settings.libraries else '❌'} **{text(lib.title)}** — ID `{lib.id}`"
                for lib in libraries
            ])

        @plex.command(name="library", description="Abilita/disabilita una libreria nelle ricerche")
        @app_commands.checks.has_permissions(manage_guild=True)
        async def library(interaction: discord.Interaction, id: str, enabled: bool):
            await interaction.response.defer(ephemeral=True)
            async with self.config_lock(interaction.guild_id):
                settings = self.store.get(interaction.guild_id)
                libraries = await self.plex.libraries(settings)
                if id not in [lib.id for lib in libraries]:
                    raise PlexError("ID di libreria musicale non valido. Usa /plex libraries.")
                ids = set(settings.libraries if settings.libraries is not None else [lib.id for lib in libraries])
                ids.add(id) if enabled else ids.discard(id)
                await self.disconnect(interaction.guild_id)
                settings.libraries = sorted(ids)
                self.store.save(interaction.guild_id, settings)
            await reply(interaction, "Libreria abilitata." if enabled else "Libreria disabilitata. Riproduzione e coda fermate per applicare i nuovi permessi.")

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

        @plex.command(name="all", description="Abilita tutte le librerie musicali, anche quelle aggiunte in futuro")
        @app_commands.checks.has_permissions(manage_guild=True)
        async def all_libraries(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            async with self.config_lock(interaction.guild_id):
                settings = self.store.get(interaction.guild_id)
                settings.libraries = None
                self.store.save(interaction.guild_id, settings)
            await reply(interaction, "Tutte le librerie musicali abilitate.")

        @self.tree.command(name="settings", description="Mostra/modifica volume, qualità, coda, timeout e ruolo DJ")
        @app_commands.guild_only()
        @app_commands.default_permissions(manage_guild=True)
        @app_commands.checks.has_permissions(manage_guild=True)
        @app_commands.describe(volume="0–150%, applicato istantaneamente", bitrate="Qualità Opus, kbps (prossimo brano)",
                               idle_seconds="Secondi prima di uscire a coda vuota", max_queue="Massimo numero di brani in attesa",
                               dj_role="Ruolo DJ opzionale", clear_dj="Rimuove il ruolo DJ")
        async def settings_command(interaction: discord.Interaction,
                                   volume: app_commands.Range[int, 0, 150] | None = None,
                                   bitrate: app_commands.Range[int, 32, 320] | None = None,
                                   idle_seconds: app_commands.Range[int, 15, 1800] | None = None,
                                   max_queue: app_commands.Range[int, 1, 500] | None = None,
                                   dj_role: discord.Role | None = None, clear_dj: bool = False):
            await interaction.response.defer(ephemeral=True)
            if dj_role and clear_dj:
                raise PlexError("Usa dj_role oppure clear_dj, non entrambi.")
            async with self.config_lock(interaction.guild_id):
                settings = self.store.get(interaction.guild_id)
                changed = False
                for name, value in (("volume", volume), ("bitrate", bitrate), ("idle_seconds", idle_seconds), ("max_queue", max_queue)):
                    if value is not None:
                        setattr(settings, name, value)
                        changed = True
                if dj_role or clear_dj:
                    settings.dj_role = dj_role.id if dj_role else None
                    changed = True
                if changed:
                    self.store.save(interaction.guild_id, settings)
                if volume is not None and interaction.guild_id in self.players:
                    self.players[interaction.guild_id].set_volume(settings.volume)
            await reply(interaction, f"Server Plex: **{text(settings.server_name or 'non configurato')}**\n"
                        f"Volume: {settings.volume}% (in tempo reale) · Opus: {settings.bitrate} kbps\n"
                        f"Uscita dopo: {settings.idle_seconds}s · Limite coda: {settings.max_queue}\n"
                        "Controllo musica: tutti gli utenti presenti nel canale vocale.")

        @self.tree.command(name="play", description="Cerca un brano Plex per titolo o autore e aggiungilo alla coda")
        @app_commands.guild_only()
        @app_commands.describe(query="Titolo del brano o nome dell'autore", library="Facoltativo: libreria musicale")
        @app_commands.checks.cooldown(1, 3, key=lambda i: (i.guild_id, i.user.id))
        async def play(interaction: discord.Interaction, query: str, library: str | None = None):
            self.require_voice(interaction)
            query = query.strip()
            if not query or len(query) > 200:
                raise PlexError("Inserisci un titolo o autore da 1 a 200 caratteri.")
            await interaction.response.defer(ephemeral=False)
            settings = self.store.get(interaction.guild_id)
            cached = self.track_cache.get((interaction.guild_id, query))
            if cached:
                tracks = [cached]
            else:
                tracks = await self.plex.search(settings, query, library)
            if not tracks:
                await reply(interaction, "Nessun brano trovato. Prova un altro titolo o autore, oppure un'altra libreria.", ephemeral=False)
            elif len(tracks) == 1:
                async with self.config_lock(interaction.guild_id):
                    if self.store.get(interaction.guild_id).revision != settings.revision:
                        raise PlexError("Configurazione cambiata. Ripeti /play.")
                    await self.enqueue(interaction, tracks[0])
                await reply(interaction, f"✅ In coda: **{text(tracks[0].label)}** · {text(tracks[0].library)}",
                            view=self.player_view(interaction), ephemeral=False)
            else:
                view = TrackView(self, interaction, tracks, settings.revision)
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

        @self.tree.command(name="queue", description="Mostra il brano attuale, la coda e i pulsanti di controllo")
        @app_commands.guild_only()
        async def queue(interaction: discord.Interaction, page: app_commands.Range[int, 1, 50] = 1):
            player = self.players.get(interaction.guild_id)
            if not player or (not player.current and not player.queue):
                await reply(interaction, "Coda vuota.", ephemeral=False)
                return
            items = list(player.queue)
            start = (page - 1) * 10
            current = text(player.current.label) if player.current else "nessuno"
            lines = [f"{i + start + 1}. {text(t.label, 110)} · {text(t.library, 35)}" for i, t in enumerate(items[start:start + 10])]
            await reply(
                interaction,
                f"**In riproduzione:** {current}\n**Coda:** {len(items)} brani · pagina {page}\n" + ("\n".join(lines) or "Nessun brano in questa pagina."),
                view=self.player_view(interaction), ephemeral=False,
            )

        @self.tree.command(name="now", description="Mostra brano, tempo di riproduzione e pulsanti di controllo")
        @app_commands.guild_only()
        async def now(interaction: discord.Interaction):
            player = self.players.get(interaction.guild_id)
            if not player or not player.current:
                await reply(interaction, "Nessun brano in riproduzione.", ephemeral=False)
                return
            track = player.current
            state = "⏸️" if player.paused_at else "🎵"
            await reply(
                interaction,
                f"{state} **{text(track.label)}**\n{text(track.album)} · {text(track.library)}\n"
                f"{duration(player.elapsed)} / {duration(track.duration // 1000)}",
                view=self.player_view(interaction), ephemeral=False,
            )

        # Comandi di controllo utilizzabili da chiunque si trovi nel canale vocale.
        def register_control(name, description):
            async def control(interaction: discord.Interaction):
                await interaction.response.defer(ephemeral=False)
                async with self.config_lock(interaction.guild_id):
                    self.require_voice(interaction)
                    player = self.players.get(interaction.guild_id)
                    voice = interaction.guild.voice_client
                    if not player or not voice:
                        raise PlexError("Il bot non è connesso a un canale vocale.")
                    if name == "leave":
                        await player.close()
                        message = "👋 Disconnesso e coda svuotata."
                    elif name == "pause" and voice.is_paused():
                        player.resume()
                        message = "▶️ Riproduzione ripresa."
                    else:
                        getattr(player, name)()
                        messages = {
                            "pause": "⏸️ In pausa.", "resume": "▶️ Riproduzione ripresa.", "skip": "⏭️ Brano saltato.",
                            "stop": "⏹️ Riproduzione fermata e coda svuotata.", "shuffle": "🔀 Coda mescolata.",
                        }
                        message = messages[name]
                view = None if name in ("stop", "leave") else self.player_view(interaction)
                await reply(interaction, message, view=view, ephemeral=False)
            control.__name__ = name
            self.tree.add_command(app_commands.guild_only()(app_commands.Command(name=name, description=description, callback=control)))

        for name, description in (("pause", "Mette in pausa o riprende la riproduzione"), ("resume", "Riprende la riproduzione"),
                                  ("skip", "Salta il brano attuale"), ("stop", "Ferma e svuota la coda"),
                                  ("leave", "Esce dal canale vocale"), ("shuffle", "Mescola i brani in attesa")):
            register_control(name, description)

        @self.tree.command(name="activity", description="Avvia la Discord Activity (Embedded App SDK) o apre il Web Player nel canale vocale")
        @app_commands.guild_only()
        async def activity_command(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            self.require_voice(interaction)
            await self.send_activity_prompt(interaction)

        @self.tree.command(name="mode", description="Passa dalla modalità con i comandi slash alla modalità Activity (o viceversa)")
        @app_commands.guild_only()
        @app_commands.describe(modalita="Scegli la modalità (lascia vuoto per alternare tra Comandi e Activity)")
        @app_commands.choices(modalita=[
            app_commands.Choice(name="🎛️ Activity (Controlla e configura tutto dall'Attività)", value="activity"),
            app_commands.Choice(name="💬 Comandi Slash (Modalità classica coi comandi)", value="commands"),
        ])
        async def mode_command(interaction: discord.Interaction, modalita: str | None = None):
            await interaction.response.defer(ephemeral=False)
            async with self.config_lock(interaction.guild_id):
                settings = self.store.get(interaction.guild_id)
                new_mode = modalita if modalita in ("activity", "commands") else ("activity" if settings.mode != "activity" else "commands")
                settings.mode = new_mode
                self.store.save(interaction.guild_id, settings)
            if new_mode == "activity":
                await self.send_activity_prompt(
                    interaction,
                    heading="✅ **Modalità Activity attivata!**\nOra puoi cercare canzoni, riprodurle subito o metterle in coda e configurare Plex direttamente dall'Attività.\n*(Usa `/mode` in qualsiasi momento per tornare ai comandi classici)*",
                )
            else:
                await reply(
                    interaction,
                    "✅ **Modalità Comandi Slash attivata!**\nTutti i comandi classici (`/play`, `/plex`, `/settings`, `/queue`, ecc.) sono nuovamente attivi. Usa `/mode` per passare alla modalità Activity.",
                    ephemeral=False,
                )

        @self.tree.command(name="link", description="Collega il tuo account Plex a Discord per mostrare la tua attività di ascolto su Plex e Discord")
        @app_commands.guild_only()
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def link_command(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            cid = f"{self.store.client_id}-u{interaction.user.id}"
            pin_id, code, auth_url, expiry = await self.plex.pin_code(client_id=cid)
            view = UserLinkView(self, interaction.user.id, pin_id, cid, auth_url, expiry)
            existing = self.store.get_user(interaction.user.id)
            status = f"\n*(Attualmente collegato a: **{text(existing.plex_username)}**)*" if existing and existing.plex_username else ""
            await reply(
                interaction,
                f"🎧 **Collega il tuo Account Plex a Discord**{status}\n"
                f"1. Vai su **https://plex.tv/link** e inserisci il codice PIN a 4 caratteri: **`{code}`**\n"
                f"2. Torna qui e premi **Completa collegamento**.",
                view=view,
            )

        @self.tree.command(name="playlist", description="Visualizza e riproduci le playlist del tuo account Plex collegato")
        @app_commands.guild_only()
        @app_commands.describe(id="Facoltativo: scegli una tua playlist Plex", shuffle="Mescola i brani della playlist")
        async def playlist_command(interaction: discord.Interaction, id: str | None = None, shuffle: bool = False):
            channel = self.require_voice(interaction)
            link = self.store.get_user(interaction.user.id)
            if not link or not link.plex_token:
                raise PlexError("Collega prima il tuo account Plex con `/link` (o dalla scheda '🎧 RPC & Account' dell'Activity) per vedere le tue playlist personali.")
            await interaction.response.defer(ephemeral=False)
            settings = self.store.get(interaction.guild_id)
            playlists = await self.plex.playlists(settings, user_token=link.plex_token)
            if not playlists:
                await reply(interaction, f"Nessuna playlist audio trovata per l'account Plex **{text(link.plex_username)}**.", ephemeral=False)
                return
            if id:
                pl = next((p for p in playlists if p.id == id or p.title.casefold() == id.strip().casefold()), None)
                if not pl:
                    raise PlexError("Playlist non trovata. Sceglila dall'elenco di `/playlist`.")
                async with self.config_lock(interaction.guild_id):
                    tracks = await self.plex.playlist_tracks(settings, pl.id, user_token=link.plex_token)
                    added = await self.player(interaction.guild).add_many(
                        channel, tracks, interaction.channel, shuffle_tracks=shuffle
                    )
                await reply(
                    interaction,
                    f"🎶 Aggiunti **{added} brani** dalla tua playlist **{text(pl.title)}**!",
                    view=self.player_view(interaction),
                    ephemeral=False,
                )
            else:
                view = PlaylistView(self, playlists, link.plex_token, settings.revision, shuffle=shuffle)
                await reply(
                    interaction,
                    f"🎶 **Playlist di {text(link.plex_username)}** ({len(playlists)} trovate):",
                    view=view,
                    ephemeral=False,
                )

        @playlist_command.autocomplete("id")
        async def playlist_autocomplete(interaction: discord.Interaction, current: str):
            with contextlib.suppress(Exception):
                link = self.store.get_user(interaction.user.id)
                if not link or not link.plex_token:
                    return []
                settings = self.store.get(interaction.guild_id)
                playlists = await self.plex.playlists(settings, user_token=link.plex_token)
                needle = current.casefold()
                return [
                    app_commands.Choice(name=f"{p.title} ({p.track_count} brani)"[:100], value=p.id[:100])
                    for p in playlists
                    if not needle or needle in p.title.casefold()
                ][:25]
            return []

        @self.tree.command(name="unlink", description="Scollega il tuo account personale Plex dal tuo profilo Discord")
        @app_commands.guild_only()
        async def unlink_command(interaction: discord.Interaction):
            self.store.delete_user(interaction.user.id)
            await reply(interaction, "🗑️ Il tuo account Plex è stato scollegato dal profilo Discord.")

        @self.tree.command(name="help", description="Guida rapida ai comandi Plexcord")
        @app_commands.guild_only()
        async def help_command(interaction: discord.Interaction):
            await reply(interaction, "**Modalità, Activity, Playlist e Sincronizzazione Ascolto**\n"
                        "`/mode`: passa tra la **Modalità Comandi** e la **Modalità Activity** (dove puoi cercare, vedere le tue playlist, riprodurre e configurare tutto dall'interfaccia grafica).\n"
                        "`/activity`: apre la Discord Activity o il Web Player.\n"
                        "`/link` · `/unlink`: collega il tuo account Plex personale a Discord (con codice a 4 cifre su `plex.tv/link`) per mostrare l'attività di ascolto su Plex/Discord e accedere alle tue playlist.\n"
                        "`/playlist`: mostra e riproduce le playlist personali del tuo account Plex collegato.\n\n"
                        "**Configurazione (Gestisci server o da Activity)**\n"
                        "/plex login → /plex servers → /plex server → /plex libraries\n"
                        "/plex address: URL LAN/Docker opzionale\n/plex library: abilita/disabilita librerie · /plex all: tutte\n"
                        "/settings: volume (in tempo reale), bitrate, timeout e limite coda\n/plex logout: scollega Plex\n\n"
                        "**Musica (per tutti nel canale vocale)**\n"
                        "Entra nel canale vocale e usa `/play query` (cerca per titolo o autore), `/playlist` o `/activity`.\n"
                        "Usa i **pulsanti sotto al player** (⏯️ ⏭️ 🔀 ⏹️ 👋) oppure i comandi:\n"
                        "/mode · /activity · /link · /playlist · /now · /queue [page] · /pause · /resume · /skip · /shuffle · /stop · /leave")

    @staticmethod
    async def send_lines(interaction, heading, lines):
        if not lines:
            await reply(interaction, heading + "\nNessun elemento trovato.")
            return
        chunk = heading
        for line in lines:
            if len(chunk) + len(line) > 1800:
                await reply(interaction, chunk)
                chunk = heading
            chunk += "\n" + line
        await reply(interaction, chunk)
