import array
import asyncio
import contextlib
import ctypes.util
import io
import random
import shlex
import sys
import threading
import time
from collections import deque

try:
    import audioop
except ImportError:
    audioop = None

import discord

from .plex import Plex, PlexError, Track
from .store import Settings, Store


def _ensure_opus_loaded():
    if discord.opus.is_loaded():
        return
    with contextlib.suppress(Exception):
        discord.opus._load_default()
    if discord.opus.is_loaded():
        return
    for name in (ctypes.util.find_library("opus"), "libopus.so.0", "libopus.so", "opus"):
        if not name:
            continue
        with contextlib.suppress(Exception):
            discord.opus.load_opus(name)
            if discord.opus.is_loaded():
                return


def scale_pcm(pcm: bytes, volume: float) -> bytes:
    if volume <= 0.0:
        return b"\x00" * len(pcm)
    if volume == 1.0 or not pcm:
        return pcm
    if audioop is not None:
        return audioop.mul(pcm, 2, min(volume, 2.0))
    arr = array.array("h")
    arr.frombytes(pcm[: len(pcm) & ~1])
    if sys.byteorder != "little":
        arr.byteswap()
    for i in range(len(arr)):
        val = int(arr[i] * volume)
        arr[i] = 32767 if val > 32767 else (-32768 if val < -32768 else val)
    if sys.byteorder != "little":
        arr.byteswap()
    return arr.tobytes()


class ManagedOpusAudio(discord.FFmpegPCMAudio):
    """Decodifica PCM da FFmpeg, applica il volume in tempo reale ogni 20ms e codifica in Opus senza interrompere lo stream."""

    def __init__(self, source, *, bitrate: int = 128, volume: float = 1.0, **kwargs):
        self._cleanup_lock = threading.Lock()
        self._first_packet = None
        self._current_error = None
        self.volume = max(0.0, min(2.0, float(volume)))
        self.bitrate = max(16, min(512, int(bitrate or 128)))
        self.diagnostics = AudioDiagnostics()
        kwargs["stderr"] = self.diagnostics
        _ensure_opus_loaded()
        self._encoder = discord.opus.Encoder()
        with contextlib.suppress(Exception):
            self._encoder.set_bitrate(self.bitrate)
        super().__init__(source, **kwargs)

    def is_opus(self) -> bool:
        return True

    async def prepare(self):
        # Leggere su un thread: una sorgente HTTP lenta non blocca Discord.
        packet = await asyncio.wait_for(asyncio.to_thread(self.read), timeout=25)
        if not packet:
            raise PlexError(self.diagnostics.reason(self._current_error))
        self._first_packet = packet

    def read(self):
        if self._first_packet is not None:
            packet, self._first_packet = self._first_packet, None
            return packet
        try:
            pcm = super().read()
            if not pcm:
                return b""
            vol = self.volume
            if vol != 1.0:
                pcm = scale_pcm(pcm, vol)
            return self._encoder.encode(pcm, self._encoder.SAMPLES_PER_FRAME)
        except Exception as error:
            self._current_error = error
            return b""

    def cleanup(self):
        with self._cleanup_lock:
            pipes = [getattr(self, name, None) for name in ("_stdout", "_stdin", "_stderr")]
            super().cleanup()
            for pipe in pipes:
                if hasattr(pipe, "close"):
                    pipe.close()


class AudioDiagnostics(io.BytesIO):
    """Buffer limitato: mostriamo categorie di errore, mai stderr/URL/token grezzi."""

    def __init__(self):
        super().__init__()
        self.lock = threading.Lock()

    def write(self, data):
        with self.lock:
            tail = (self.getvalue() + data)[-16384:]
            self.seek(0)
            self.truncate()
            super().write(tail)
        return len(data)

    def reason(self, error=None):
        with self.lock:
            output = (self.getvalue().decode(errors="replace") + str(error or "")).casefold()
        if "401" in output or "403" in output or "unauthorized" in output or "forbidden" in output:
            return "Plex nega l'accesso al file audio. Ripeti /plex login e scegli nuovamente il server."
        if "404" in output or "not found" in output or "no such file" in output:
            return "File audio non trovato o non disponibile sul server Plex."
        if any(word in output for word in ("timed out", "connection refused", "connection reset", "resolve hostname")):
            return "Connessione al file audio fallita: controlla la rete e /plex address."
        return "FFmpeg non riesce a decodificare il file audio: verifica formato, integrità e disponibilità su Plex."


def audio_source(url: str, settings: Settings, *, executable: str = "ffmpeg", seek_seconds: int = 0):
    if any(c in settings.server_token for c in ("\r", "\n")):
        raise PlexError("Token Plex non valido. Ripeti /plex login.")
    headers = f"X-Plex-Token: {settings.server_token}\r\n"
    seek = f"-ss {max(0, int(seek_seconds))} " if seek_seconds > 0 else ""
    # Lascia codec al valore predefinito: discord.py interpreta 'libopus' come COPY.
    return ManagedOpusAudio(
        url, executable=executable, bitrate=settings.bitrate, volume=settings.volume / 100,
        before_options=seek + "-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
                       "-probesize 10000000 -analyzeduration 10000000 "
                       "-rw_timeout 15000000 -headers " + shlex.quote(headers),
        options="-map 0:a:0 -vn -sn -dn",
    )


class Player:
    def __init__(self, guild: discord.Guild, plex: Plex, store: Store, bot=None):
        self.guild = guild
        self.plex = plex
        self.store = store
        self.bot = bot
        self.queue: deque[Track] = deque()
        self.current: Track | None = None
        self.current_source: ManagedOpusAudio | None = None
        self.seek_to: int | None = None
        self.started_offset = 0
        self.started = 0.0
        self.paused_at = 0.0
        self.paused_total = 0.0
        self.lock = asyncio.Lock()
        self.wake = asyncio.Event()
        self.finished: asyncio.Future | None = None
        self.task: asyncio.Task | None = None
        self.text_channel = None
        self.last_discord_state: tuple[str, str] = ("", "")

    async def _ensure_voice(self, channel):
        voice = self.guild.voice_client
        if voice and voice.channel.id != channel.id:
            raise PlexError("Il bot è già in un altro canale vocale.")
        if voice and not voice.is_connected():
            await voice.disconnect(force=True)
            voice = None
        if not voice:
            try:
                await channel.connect(timeout=20, reconnect=True, self_deaf=True)
            except Exception:
                if self.guild.voice_client:
                    await self.guild.voice_client.disconnect(force=True)
                raise PlexError("Connessione vocale fallita. Controlla i permessi Connetti e Parla e la rete UDP.") from None

    async def add(self, channel, track, text_channel, *, play_now: bool = False):
        async with self.lock:
            if not play_now and len(self.queue) >= self.store.get(self.guild.id).max_queue:
                raise PlexError("Coda piena.")
            await self._ensure_voice(channel)
            if play_now:
                self.queue.appendleft(track)
            else:
                self.queue.append(track)
            self.text_channel = text_channel
            self.wake.set()
            if not self.task or self.task.done():
                self.task = asyncio.create_task(self.run(), name=f"player-{self.guild.id}")
            elif play_now and self.current is not None:
                self.skip()

    async def add_many(self, channel, tracks: list[Track], text_channel, *, play_now: bool = False, shuffle_tracks: bool = False) -> int:
        if not tracks:
            raise PlexError("Questa playlist non contiene brani riproducibili.")
        async with self.lock:
            max_q = self.store.get(self.guild.id).max_queue
            if not play_now and len(self.queue) >= max_q:
                raise PlexError("Coda piena.")
            await self._ensure_voice(channel)
            items = list(tracks)
            if shuffle_tracks:
                random.shuffle(items)
            if play_now:
                limit = max(1, max_q - len(self.queue))
                selected = items[:limit]
                for t in reversed(selected):
                    self.queue.appendleft(t)
            else:
                limit = max(0, max_q - len(self.queue))
                selected = items[:limit]
                self.queue.extend(selected)
            self.text_channel = text_channel
            self.wake.set()
            if not self.task or self.task.done():
                self.task = asyncio.create_task(self.run(), name=f"player-{self.guild.id}")
            elif play_now and self.current is not None:
                self.skip()
            return len(selected)

    def set_volume(self, volume: int):
        vol = max(0, min(150, int(volume))) / 100.0
        if self.current_source is not None:
            self.current_source.volume = vol
        voice = getattr(self.guild, "voice_client", None)
        src = getattr(voice, "source", None)
        if src is not None and hasattr(src, "volume"):
            src.volume = vol

    def finish(self, error=None):
        if self.finished and not self.finished.done():
            self.finished.set_result(error)

    def skip(self):
        self.seek_to = None
        self.finish()
        if self.guild.voice_client:
            self.guild.voice_client.stop()

    def seek(self, seconds: int):
        if not self.current:
            raise PlexError("Nessun brano in riproduzione.")
        limit = max(0, (self.current.duration // 1000) - 1) if self.current.duration else max(0, int(seconds))
        self.seek_to = min(max(0, int(seconds)), limit)
        self.finish()
        if self.guild.voice_client:
            self.guild.voice_client.stop()

    def remove(self, index: int) -> Track:
        items = list(self.queue)
        if index < 0 or index >= len(items):
            raise PlexError("Posizione nella coda non valida.")
        track = items.pop(index)
        self.queue = deque(items)
        return track

    def promote(self, index: int, *, play_now: bool = False) -> Track:
        track = self.remove(index)
        self.queue.appendleft(track)
        if play_now:
            self.skip()
        return track

    def stop(self):
        self.queue.clear()
        self.skip()

    def shuffle(self):
        items = list(self.queue)
        random.shuffle(items)
        self.queue = deque(items)

    def pause(self):
        voice = self.guild.voice_client
        if not voice or not voice.is_playing():
            raise PlexError("Nessun brano in riproduzione.")
        voice.pause()
        self.paused_at = time.monotonic()
        if self.current:
            asyncio.create_task(self.sync_timeline("paused", self.current))

    def resume(self):
        voice = self.guild.voice_client
        if not voice or not voice.is_paused():
            raise PlexError("La riproduzione non è in pausa.")
        voice.resume()
        self.paused_total += time.monotonic() - self.paused_at
        self.paused_at = 0
        if self.current:
            asyncio.create_task(self.sync_timeline("playing", self.current))

    def active_listeners(self):
        voice = getattr(self.guild, "voice_client", None)
        channel = getattr(voice, "channel", None)
        if not channel or not hasattr(self.store, "list_users"):
            return []
        ids = set()
        vs = getattr(channel, "voice_states", None)
        if isinstance(vs, dict):
            ids.update(vs.keys())
        for m in getattr(channel, "members", []) or []:
            if not getattr(m, "bot", False):
                ids.add(m.id)
        return self.store.list_users(list(ids))

    async def sync_timeline(self, state: str, track: Track | None = None):
        t = track or self.current
        discord_key = (state, t.id if t else "")
        if self.bot and discord_key != self.last_discord_state:
            self.last_discord_state = discord_key
            if hasattr(self.bot, "change_presence"):
                with contextlib.suppress(Exception):
                    if state in ("playing", "paused") and t:
                        prefix = "⏸️ " if state == "paused" else ""
                        act = discord.Activity(
                            type=discord.ActivityType.listening,
                            name=f"{prefix}{t.label}"[:128],
                            details=t.title[:128],
                            state=(f"{t.artist}" + (f" · {t.album}" if t.album else ""))[:128],
                        )
                        await self.bot.change_presence(status=discord.Status.online, activity=act)
                    elif state == "stopped" and not self.queue:
                        await self.bot.change_presence(status=discord.Status.online, activity=None)
            voice = getattr(self.guild, "voice_client", None)
            channel = getattr(voice, "channel", None)
            if channel and hasattr(self.bot, "http") and hasattr(discord, "http"):
                with contextlib.suppress(Exception):
                    v_status = (
                        f"🎵 {t.label}"[:480]
                        if state == "playing" and t
                        else (f"⏸️ {t.label}"[:480] if state == "paused" and t else "")
                    )
                    route = discord.http.Route("PUT", "/channels/{channel_id}/voice-status", channel_id=channel.id)
                    await self.bot.http.request(route, json={"status": v_status})
        if not t or not hasattr(self.plex, "report_timeline"):
            return
        settings = self.store.get(self.guild.id)
        elapsed_ms = self.elapsed * 1000
        listeners = self.active_listeners()
        if listeners:
            for link in listeners:
                name = link.plex_username or link.discord_name or f"Utente {link.discord_id}"
                await self.plex.report_timeline(
                    settings, t, state, elapsed_ms,
                    user_token=link.plex_token,
                    client_id=f"{self.store.client_id}-u{link.discord_id}",
                    device_name=f"Discord ({name})",
                )
        else:
            await self.plex.report_timeline(
                settings, t, state, elapsed_ms,
                device_name=f"Discord ({getattr(self.guild, 'name', 'Plexcord')})",
            )

    @property
    def elapsed(self):
        if not self.started:
            return self.started_offset
        return max(0, self.started_offset + int((self.paused_at or time.monotonic()) - self.started - self.paused_total))

    async def notify(self, content):
        if self.text_channel:
            with contextlib.suppress(discord.HTTPException):
                await self.text_channel.send(content, allowed_mentions=discord.AllowedMentions.none())

    async def run(self):
        loop = asyncio.get_running_loop()
        try:
            while True:
                seek_seconds = 0
                async with self.lock:
                    voice = self.guild.voice_client
                    if not voice or not voice.is_connected():
                        self.queue.clear()
                        return
                    if self.seek_to is not None and self.current is not None:
                        track = self.current
                        seek_seconds = self.seek_to
                        self.seek_to = None
                        self.started_offset = seek_seconds
                        self.started = self.paused_at = self.paused_total = 0
                        done = self.finished = loop.create_future()
                    elif self.queue:
                        track = self.queue.popleft()
                        self.current = track
                        self.started_offset = 0
                        self.started = self.paused_at = self.paused_total = 0
                        done = self.finished = loop.create_future()
                    else:
                        self.current = None
                        self.started_offset = 0
                        self.finished = None
                        self.wake.clear()
                        track = None
                if track is None:
                    try:
                        await asyncio.wait_for(self.wake.wait(), self.store.get(self.guild.id).idle_seconds)
                    except TimeoutError:
                        async with self.lock:
                            if self.queue:
                                continue
                            await voice.disconnect(force=True)
                            return
                    continue
                source = None
                try:
                    settings = self.store.get(self.guild.id)
                    urls = await self.plex.streams(settings, track)
                    failure = "Nessuna versione audio riproducibile."
                    for url in urls:
                        if done.done():
                            break
                        # Verifica l'audio prima di consegnarlo alla voce; se la
                        # prima versione è corrotta/offline, prova le altre.
                        source = audio_source(url, settings) if seek_seconds == 0 else audio_source(url, settings, seek_seconds=seek_seconds)
                        preparing = asyncio.create_task(source.prepare())
                        try:
                            completed, _ = await asyncio.wait((preparing, done), return_when=asyncio.FIRST_COMPLETED)
                            if done in completed:
                                break
                            await preparing
                            break
                        except Exception as error:
                            if isinstance(error, PlexError):
                                failure = str(error)
                            elif isinstance(error, TimeoutError):
                                failure = "Timeout durante la lettura del file audio."
                            else:
                                failure = source.diagnostics.reason(error)
                            source.cleanup()
                            source = None
                        finally:
                            if not preparing.done():
                                preparing.cancel()
                            with contextlib.suppress(asyncio.CancelledError, Exception):
                                await preparing
                    if done.done():
                        continue
                    if source is None:
                        raise PlexError(failure)

                    def after(error, future=done):
                        def resolve():
                            if not future.done():
                                future.set_result(error)
                        with contextlib.suppress(RuntimeError):
                            loop.call_soon_threadsafe(resolve)

                    self.current_source = source
                    if hasattr(source, "volume"):
                        source.volume = self.store.get(self.guild.id).volume / 100.0
                    voice.play(source, after=after)
                    self.started = time.monotonic()
                    asyncio.create_task(self.sync_timeline("playing", track))
                    while not done.done():
                        await asyncio.wait((done,), timeout=15.0)
                        if not done.done():
                            asyncio.create_task(self.sync_timeline("paused" if self.paused_at else "playing", track))
                    error = await done
                    if self.seek_to is None:
                        asyncio.create_task(self.sync_timeline("stopped", track))
                    if error:
                        await self.notify(f"⚠️ {source.diagnostics.reason(error)} Passo al prossimo brano.")
                except PlexError as error:
                    await self.notify(f"⚠️ {error}")
                except Exception:
                    await self.notify("⚠️ Impossibile riprodurre il brano. Controlla FFmpeg e i permessi vocali.")
                finally:
                    self.current_source = None
                    if source:
                        voice.stop()
                        source.cleanup()
                    if self.seek_to is None:
                        self.current = None
                        self.started_offset = 0
                    self.finished = None
                    self.started = 0
        finally:
            self.current = None
            self.started_offset = 0
            self.finished = None

    async def close(self):
        async with self.lock:
            if self.current:
                await self.sync_timeline("stopped", self.current)
            self.stop()
            if self.task and not self.task.done():
                self.task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self.task
            if self.guild.voice_client:
                await self.guild.voice_client.disconnect(force=True)
