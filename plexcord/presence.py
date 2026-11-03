"""Discord Rich Presence lato server per tutti gli ascoltatori che hanno autorizzato Plexcord.

Per ogni utente nel canale vocale del bot con un token OAuth2 Discord salvato
(scope ``activities.write``) viene creata/aggiornata una *headless session*
(``POST /users/@me/headless-sessions``): lo stato "Sta ascoltando" compare sul
profilo dell'utente anche senza tenere aperta la Discord Activity.

Se l'applicazione Discord non dispone dello scope ``activities.write`` la
sessione headless fallisce in modo silenzioso e l'Activity ripiega sul comando
RPC ``SET_ACTIVITY`` del client (visibile solo mentre l'Activity è aperta).

Nessun token (Discord o Plex) né URL interno del server Plex viene mai loggato
o inviato a Discord.
"""

import asyncio
import contextlib
import hashlib
import hmac
import os
import time

import discord

API = "https://discord.com/api/v10"
KEEPALIVE = 8 * 60  # Discord elimina le sessioni headless dopo 20 minuti senza aggiornamenti.
TICK = 30


class RichPresence:
    def __init__(self, bot):
        self.bot = bot
        self.sessions: dict[int, str] = {}  # discord_id -> token sessione headless
        self.last_key: dict[int, tuple] = {}
        self.last_push: dict[int, float] = {}
        self.owner: dict[int, int] = {}  # discord_id -> guild_id che ha impostato lo stato
        self.unsupported: set[int] = set()
        self.cover_assets: dict[str, str] = {}
        self.locks: dict[int, asyncio.Lock] = {}
        self.task: asyncio.Task | None = None

    # ------------------------------------------------------------------ utilità
    @property
    def session(self):
        return getattr(self.bot, "http_session", None)

    def client_id(self) -> str:
        bot_uid = getattr(getattr(self.bot, "user", None), "id", "")
        return str(getattr(self.bot, "application_id", None) or os.environ.get("DISCORD_CLIENT_ID", "") or bot_uid or "")

    def client_secret(self) -> str:
        env_sec = os.environ.get("DISCORD_CLIENT_SECRET", "").strip()
        if env_sec:
            return env_sec
        store = self.bot.store
        return store.get_meta("discord_client_secret", "") if hasattr(store, "get_meta") else ""

    def _secret(self) -> bytes:
        return str(self.bot.store.client_id).encode()

    def user_key(self, discord_id: int) -> str:
        """Chiave opaca consegnata solo al client dell'utente per ripristinare il proprio token."""
        return hmac.new(self._secret(), f"rpc:{discord_id}".encode(), hashlib.sha256).hexdigest()[:40]

    def check_user_key(self, discord_id: int, key: str) -> bool:
        return bool(key) and hmac.compare_digest(self.user_key(discord_id), str(key))

    def cover_sig(self, guild_id: int, track_id: str) -> str:
        return hmac.new(self._secret(), f"cover:{guild_id}:{track_id}".encode(), hashlib.sha256).hexdigest()[:24]

    # ------------------------------------------------------------------ OAuth2
    async def _token_request(self, data: dict) -> dict | None:
        cid, secret, session = self.client_id(), self.client_secret(), self.session
        if not cid or not secret or not session:
            return None
        payload = {"client_id": cid, "client_secret": secret, **data}
        with contextlib.suppress(Exception):
            async with session.post(
                f"{API}/oauth2/token", data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as resp:
                body = await resp.json(content_type=None)
                if resp.status < 300 and isinstance(body, dict) and body.get("access_token"):
                    return body
                if isinstance(body, dict):
                    return {"_error": str(body.get("error_description") or body.get("error") or "")[:120]}
        return None

    async def fetch_user(self, access_token: str) -> dict | None:
        session = self.session
        if not session:
            return None
        with contextlib.suppress(Exception):
            async with session.get(f"{API}/users/@me", headers={"Authorization": f"Bearer {access_token}"}) as resp:
                if resp.status < 300:
                    data = await resp.json(content_type=None)
                    if isinstance(data, dict) and str(data.get("id", "")).isdigit():
                        return data
        return None

    def _save(self, discord_id: int, payload: dict, prev: dict | None = None):
        prev = prev or {}
        expires_in = int(payload.get("expires_in") or 604800)
        data = {
            "access_token": str(payload["access_token"]),
            "refresh_token": str(payload.get("refresh_token") or prev.get("refresh_token") or ""),
            "scope": str(payload.get("scope") or prev.get("scope") or ""),
            "expires_at": int(time.time()) + max(60, expires_in - 120),
        }
        self.bot.store.save_discord_oauth(discord_id, data)
        if "activities.write" in data["scope"].split():
            self.unsupported.discard(discord_id)
        return data

    async def exchange(self, code: str) -> tuple[dict, dict]:
        """Scambia il codice OAuth2 e salva il token per l'utente. Ritorna (token, utente)."""
        payload = await self._token_request({"grant_type": "authorization_code", "code": code})
        if not payload or "access_token" not in payload:
            detail = (payload or {}).get("_error", "")
            raise ValueError(detail)
        user = await self.fetch_user(payload["access_token"])
        if not user:
            raise ValueError("utente non verificato")
        uid = int(user["id"])
        self._save(uid, payload, self.bot.store.get_discord_oauth(uid))
        return payload, user

    async def access_token(self, discord_id: int, *, force_refresh: bool = False) -> str:
        data = self.bot.store.get_discord_oauth(discord_id)
        if not data:
            return ""
        if data.get("access_token") and not force_refresh and int(data.get("expires_at") or 0) > time.time():
            return str(data["access_token"])
        refresh = str(data.get("refresh_token") or "")
        if not refresh:
            return ""
        payload = await self._token_request({"grant_type": "refresh_token", "refresh_token": refresh})
        if not payload or "access_token" not in payload:
            return ""
        return self._save(discord_id, payload, data)["access_token"]

    def has_scope(self, discord_id: int) -> bool:
        data = self.bot.store.get_discord_oauth(discord_id) or {}
        return "activities.write" in str(data.get("scope", "")).split()

    async def revoke(self, discord_id: int):
        await self.clear(discord_id)
        self.bot.store.delete_discord_oauth(discord_id)
        self.unsupported.discard(discord_id)

    # ------------------------------------------------------------------ copertina
    async def cover_image(self, guild_id: int, track_id: str) -> str:
        base = getattr(self.bot, "activity_url", "") or ""
        cid = self.client_id()
        if not base.startswith("https://") or not cid or not track_id.isdigit():
            return ""
        url = f"{base}/api/cover/{guild_id}/{track_id}/{self.cover_sig(guild_id, track_id)}.jpg"
        if url in self.cover_assets:
            return self.cover_assets[url]
        asset = ""
        with contextlib.suppress(Exception):
            route = discord.http.Route("POST", "/applications/{app_id}/external-assets", app_id=cid)
            data = await self.bot.http.request(route, json={"urls": [url]})
            if isinstance(data, list) and data and data[0].get("external_asset_path"):
                asset = "mp:" + str(data[0]["external_asset_path"])
        self.cover_assets[url] = asset
        if len(self.cover_assets) > 300:
            self.cover_assets.pop(next(iter(self.cover_assets)))
        return asset

    # ------------------------------------------------------------------ activity
    async def build_activity(self, player, state: str, track) -> dict:
        settings = self.bot.store.get(player.guild.id)
        paused = state == "paused"
        activity = {
            "application_id": self.client_id(),
            "name": "Plex",
            "type": 2,  # Listening
            "platform": "desktop",
            "status_display_type": 2,
            "details": (("⏸️ " if paused else "") + track.title)[:128] or "Brano su Plex",
            "state": (f"di {track.artist}" + (f" · {track.album}" if track.album else ""))[:128] or "Plex",
        }
        duration = int(track.duration or 0)
        if not paused and duration > 0:
            start = int(time.time() * 1000) - int(player.elapsed) * 1000
            activity["timestamps"] = {"start": start, "end": start + duration}
        assets = {"large_text": (track.album or settings.server_name or "Plexcord")[:128]}
        image = await self.cover_image(player.guild.id, track.id)
        if image:
            assets["large_image"] = image
        activity["assets"] = assets
        return activity

    async def _post_session(self, discord_id: int, activity: dict) -> str:
        """Ritorna "ok", "auth" (token scaduto), "denied" (scope mancante) o "error"."""
        session = self.session
        token = await self.access_token(discord_id)
        if not session or not token:
            return "auth"
        body = {"activities": [activity]}
        if discord_id in self.sessions:
            body["token"] = self.sessions[discord_id]
        try:
            async with session.post(
                f"{API}/users/@me/headless-sessions", json=body,
                headers={"Authorization": f"Bearer {token}"},
            ) as resp:
                data = await resp.json(content_type=None) if resp.content_length != 0 else {}
                if resp.status < 300:
                    if isinstance(data, dict) and data.get("token"):
                        self.sessions[discord_id] = str(data["token"])
                    return "ok"
                if resp.status == 401:
                    return "auth"
                if resp.status == 403:
                    return "denied"
                if resp.status == 404 and "token" in body:
                    self.sessions.pop(discord_id, None)
                return "error"
        except Exception:
            return "error"

    async def push(self, discord_id: int, activity: dict) -> bool:
        result = await self._post_session(discord_id, activity)
        if result == "auth" and await self.access_token(discord_id, force_refresh=True):
            result = await self._post_session(discord_id, activity)
        if result == "error":
            # Alcuni campi opzionali possono non essere accettati: riprova con il minimo indispensabile.
            minimal = {k: v for k, v in activity.items() if k not in ("assets", "status_display_type")}
            result = await self._post_session(discord_id, minimal)
            if result == "error":
                result = await self._post_session(discord_id, {**minimal, "type": 0})
        if result == "denied":
            self.unsupported.add(discord_id)
        return result == "ok"

    async def clear(self, discord_id: int):
        session_token = self.sessions.pop(discord_id, None)
        self.last_key.pop(discord_id, None)
        self.last_push.pop(discord_id, None)
        self.owner.pop(discord_id, None)
        session = self.session
        if not session_token or not session:
            return
        token = await self.access_token(discord_id)
        if not token:
            return
        with contextlib.suppress(Exception):
            async with session.post(
                f"{API}/users/@me/headless-sessions/delete", json={"token": session_token},
                headers={"Authorization": f"Bearer {token}"},
            ) as resp:
                await resp.read()

    # ------------------------------------------------------------------ sincronizzazione
    def listener_ids(self, player) -> list[int]:
        voice = getattr(player.guild, "voice_client", None)
        channel = getattr(voice, "channel", None)
        if not channel:
            return []
        bot_id = getattr(getattr(self.bot, "user", None), "id", None)
        ids = set()
        vs = getattr(channel, "voice_states", None)
        if isinstance(vs, dict):
            ids.update(uid for uid in vs if uid != bot_id)
        for m in getattr(channel, "members", []) or []:
            if not getattr(m, "bot", False):
                ids.add(m.id)
        return list(ids)

    def eligible_ids(self, player) -> list[int]:
        store = self.bot.store
        if not hasattr(store, "discord_oauth_ids"):
            return []
        return [uid for uid in store.discord_oauth_ids(self.listener_ids(player))
                if uid not in self.unsupported and self.has_scope(uid)]

    def active_for(self, discord_ids) -> list[str]:
        return [str(uid) for uid in discord_ids if uid in self.sessions]

    async def sync_player(self, player, state: str | None = None, *, force: bool = False):
        guild_id = player.guild.id
        track = player.current
        if state is None:
            state = "paused" if player.paused_at else "playing"
        listening = set(self.eligible_ids(player)) if track and state in ("playing", "paused") else set()

        # Utenti usciti dal canale o riproduzione terminata: rimuovi lo stato.
        for uid in [u for u, g in self.owner.items() if g == guild_id and u not in listening]:
            await self.clear(uid)

        if not listening:
            return
        activity = await self.build_activity(player, state, track)
        start = activity.get("timestamps", {}).get("start", 0) // 5000
        key = (track.id, state, start)
        now = time.monotonic()
        for uid in listening:
            lock = self.locks.setdefault(uid, asyncio.Lock())
            async with lock:
                stale = now - self.last_push.get(uid, 0) > KEEPALIVE
                if not force and not stale and self.last_key.get(uid) == key and self.owner.get(uid) == guild_id:
                    continue
                if await self.push(uid, activity):
                    self.last_key[uid] = key
                    self.last_push[uid] = now
                    self.owner[uid] = guild_id

    def notify(self, player, state: str):
        """Hook non bloccante richiamato da Player.sync_timeline()."""
        with contextlib.suppress(RuntimeError):
            asyncio.get_running_loop().create_task(self._safe_sync(player, state))

    async def _safe_sync(self, player, state):
        with contextlib.suppress(Exception):
            await self.sync_player(player, state)

    async def run(self):
        while True:
            await asyncio.sleep(TICK)
            for player in list(getattr(self.bot, "players", {}).values()):
                await self._safe_sync(player, None)
            # Sessioni orfane (player chiuso o server rimosso).
            active_guilds = {gid for gid, p in getattr(self.bot, "players", {}).items() if p.current}
            for uid in [u for u, g in self.owner.items() if g not in active_guilds]:
                with contextlib.suppress(Exception):
                    await self.clear(uid)

    def start(self):
        if not self.task:
            self.task = asyncio.create_task(self.run())

    async def close(self):
        if self.task:
            self.task.cancel()
            with contextlib.suppress(BaseException):
                await self.task
            self.task = None
        for uid in list(self.sessions):
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self.clear(uid), 3)
