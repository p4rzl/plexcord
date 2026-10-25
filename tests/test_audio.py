import asyncio
import io
import os
import shutil
import unittest
import wave

from aiohttp import web

from plexcord.player import AudioDiagnostics, audio_source
from plexcord.plex import PlexError
from plexcord.store import Settings

FFMPEG = os.environ.get("PLEXCORD_TEST_FFMPEG") or shutil.which("ffmpeg")


class DiagnosticsTests(unittest.TestCase):
    def test_error_categories_and_buffer_limit(self):
        for output, expected in (("HTTP 404 file secret", "non trovato"),
                                 ("HTTP 403 token=secret", "nega l'accesso"),
                                 ("Connection timed out secret", "Connessione"),
                                 ("Invalid data found at secret", "decodificare")):
            diagnostics = AudioDiagnostics()
            diagnostics.write(b"x" * 20000)
            diagnostics.write(output.encode())
            self.assertLessEqual(len(diagnostics.getvalue()), 16384)
            self.assertIn(expected, diagnostics.reason())
            self.assertNotIn("secret", diagnostics.reason())


@unittest.skipUnless(FFMPEG, "FFmpeg non disponibile: test audio opzionale")
class AudioTests(unittest.IsolatedAsyncioTestCase):
    async def test_http_wav_encoded_as_opus_with_private_header(self):
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as audio:
            audio.setnchannels(2)
            audio.setsampwidth(2)
            audio.setframerate(48000)
            audio.writeframes(b"\0" * 48000)  # 250ms stereo PCM, non Opus.
        headers = []

        async def handler(request):
            headers.append(request.headers.get("X-Plex-Token"))
            self.assertNotIn("secret", str(request.url))
            return web.Response(body=buffer.getvalue(), content_type="audio/wav")

        app = web.Application()
        app.router.add_get("/library/parts/1/file.wav", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        source = audio_source(f"http://127.0.0.1:{port}/library/parts/1/file.wav",
                              Settings(server_token="secret", volume=80), executable=FFMPEG)
        try:
            await source.prepare()
            def read_packets():
                packets = []
                while packet := source.read():
                    packets.append(packet)
                return packets

            packets = await asyncio.wait_for(asyncio.to_thread(read_packets), 10)
            self.assertTrue(source.is_opus())
            self.assertGreaterEqual(len(packets), 12)
            self.assertEqual(headers, ["secret"])
            self.assertIsNone(source._current_error)
        finally:
            source.cleanup()
            await runner.cleanup()

    async def test_missing_file_fails_before_voice_playback(self):
        async def handler(request):
            return web.Response(status=404)

        app = web.Application()
        app.router.add_get("/missing.wav", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        source = audio_source(f"http://127.0.0.1:{port}/missing.wav", Settings(server_token="secret"), executable=FFMPEG)
        try:
            with self.assertRaises(PlexError) as error:
                await source.prepare()
            self.assertIn("non trovato", str(error.exception))
            self.assertNotIn("secret", str(error.exception))
            self.assertNotIn("127.0.0.1", str(error.exception))
        finally:
            source.cleanup()
            await runner.cleanup()
