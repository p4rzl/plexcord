import asyncio
import contextlib
import io
import random
import shlex
import threading
import time
from collections import deque

import discord

from .plex import Plex, PlexError, Track
from .store import Settings, Store


class ManagedOpusAudio(discord.FFmpegOpusAudio):
    """Chiude esplicitamente la pipe anche quando thread e player fanno cleanup."""

    def __init__(self, *args, **kwargs):
        self._cleanup_lock = threading.Lock()
        self._first_packet = None
        self.diagnostics = AudioDiagnostics()
        kwargs["stderr"] = self.diagnostics
        super().__init__(*args, **kwargs)

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
        return super().read()

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


def audio_source(url: str, settings: Settings, *, executable: str = "ffmpeg"):
    if any(c in settings.server_token for c in ("\r", "\n")):
        raise PlexError("Token Plex non valido. Ripeti /plex login.")
    headers = f"X-Plex-Token: {settings.server_token}\r\n"
    # Lascia codec al valore predefinito: discord.py interpreta 'libopus' come COPY.
    return ManagedOpusAudio(
        url, executable=executable, bitrate=settings.bitrate,
        before_options="-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
                       "-probesize 10000000 -analyzeduration 10000000 "
                       "-rw_timeout 15000000 -headers " + shlex.quote(headers),
        options=f"-map 0:a:0 -vn -sn -dn -af volume={settings.volume / 100:.2f} -frame_duration 20",
    )


class Player:
    def __init__(self, guild: discord.Guild, plex: Plex, store: Store):
        self.guild = guild
        self.plex = plex
        self.store = store
        self.queue: deque[Track] = deque()
        self.current: Track | None = None
        self.started = 0.0
        self.paused_at = 0.0
        self.paused_total = 0.0
        self.lock = asyncio.Lock()
        self.wake = asyncio.Event()
        self.finished: asyncio.Future | None = None
        self.task: asyncio.Task | None = None
        self.text_channel = None

    async def add(self, channel, track, text_channel):
        async with self.lock:
            if len(self.queue) >= self.store.get(self.guild.id).max_queue:
                raise PlexError("Coda piena.")
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
            self.queue.append(track)
            self.text_channel = text_channel
            self.wake.set()
            if not self.task or self.task.done():
                self.task = asyncio.create_task(self.run(), name=f"player-{self.guild.id}")

    def finish(self, error=None):
        if self.finished and not self.finished.done():
            self.finished.set_result(error)

    def skip(self):
        self.finish()
        if self.guild.voice_client:
            self.guild.voice_client.stop()

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

    def resume(self):
        voice = self.guild.voice_client
        if not voice or not voice.is_paused():
            raise PlexError("La riproduzione non è in pausa.")
        voice.resume()
        self.paused_total += time.monotonic() - self.paused_at
        self.paused_at = 0

    @property
    def elapsed(self):
        if not self.started:
            return 0
        return max(0, int((self.paused_at or time.monotonic()) - self.started - self.paused_total))

    async def notify(self, content):
        if self.text_channel:
            with contextlib.suppress(discord.HTTPException):
                await self.text_channel.send(content, allowed_mentions=discord.AllowedMentions.none())

    async def run(self):
        loop = asyncio.get_running_loop()
        try:
            while True:
                async with self.lock:
                    voice = self.guild.voice_client
                    if not voice or not voice.is_connected():
                        self.queue.clear()
                        return
                    if self.queue:
                        track = self.queue.popleft()
                        self.current = track
                        self.started = self.paused_at = self.paused_total = 0
                        done = self.finished = loop.create_future()
                    else:
                        self.current = None
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
                        source = audio_source(url, settings)
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

                    voice.play(source, after=after)
                    self.started = time.monotonic()
                    error = await done
                    if error:
                        await self.notify(f"⚠️ {source.diagnostics.reason(error)} Passo al prossimo brano.")
                except PlexError as error:
                    await self.notify(f"⚠️ {error}")
                except Exception:
                    await self.notify("⚠️ Impossibile riprodurre il brano. Controlla FFmpeg e i permessi vocali.")
                finally:
                    if source:
                        voice.stop()
                        source.cleanup()
                    self.current = None
                    self.finished = None
                    self.started = 0
        finally:
            self.current = None
            self.finished = None

    async def close(self):
        async with self.lock:
            self.stop()
            if self.task and not self.task.done():
                self.task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self.task
            if self.guild.voice_client:
                await self.guild.voice_client.disconnect(force=True)
