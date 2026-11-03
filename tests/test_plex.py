import asyncio
import unittest
from unittest.mock import AsyncMock

import aiohttp
from aiohttp import web
from defusedxml import ElementTree

from plexcord.plex import Plex, PlexError, Track, valid_url
from plexcord.store import Settings


class URLTests(unittest.TestCase):
    def test_urls(self):
        self.assertEqual(valid_url("http://192.168.1.5:32400/"), "http://192.168.1.5:32400")
        self.assertEqual(valid_url("https://plex.example.com"), "https://plex.example.com")
        for value in ("file:///etc/passwd", "http://user:pass@plex", "https://plex?token=secret", "http://plex/path", "http://plex:wrong"):
            with self.subTest(value=value), self.assertRaises(PlexError):
                valid_url(value)


class PlexTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = aiohttp.ClientSession()
        self.plex = Plex(self.session, "test-client")
        self.settings = Settings(server_url="http://plex", server_token="secret")
        self.libraries = ElementTree.fromstring('<MediaContainer><Directory key="1" title="Music" type="artist"/><Directory key="2" title="Other" type="artist"/><Directory key="3" type="movie"/></MediaContainer>')

    async def asyncTearDown(self):
        await self.session.close()

    async def test_multi_library_interleaving(self):
        async def request(url, *args, **kwargs):
            if url.endswith("/sections"):
                return self.libraries
            lib = url.split("/")[-2]
            return ElementTree.fromstring('<MediaContainer>' + ''.join(
                f'<Track ratingKey="{lib}{i}" title="Song {i}" grandparentTitle="Artist" duration="1000"/>'
                for i in range(25)) + '</MediaContainer>')
        self.plex.request = AsyncMock(side_effect=request)
        tracks = await self.plex.search(self.settings, "Song")
        self.assertEqual(len(tracks), 50)
        self.assertEqual(tracks[0].library, "Music")
        self.assertEqual(tracks[1].library, "Other")
        self.assertTrue(all(call.kwargs.get("params", {}).get("type") == "10"
                            for call in self.plex.request.call_args_list[1:]))
        self.assertTrue(all(call.args[0].endswith("/all") for call in self.plex.request.call_args_list[1:]))
        self.assertTrue(all(call.kwargs["params"]["title"] == "Song" for call in self.plex.request.call_args_list[1:]))

    async def test_disabled_and_explicit_library(self):
        self.plex.request = AsyncMock(return_value=self.libraries)
        self.settings.libraries = []
        with self.assertRaises(PlexError):
            await self.plex.search(self.settings, "Song")
        self.settings.libraries = ["1"]
        with self.assertRaises(PlexError):
            await self.plex.search(self.settings, "Song", "2")

    async def test_exact_match_on_second_page_is_first(self):
        async def request(url, *args, **kwargs):
            if url.endswith("/sections"):
                return self.libraries
            start = int(kwargs["params"]["X-Plex-Container-Start"])
            titles = [f"Song live {i}" for i in range(59)] + ["Song"]
            return ElementTree.fromstring('<MediaContainer totalSize="60">' + ''.join(
                f'<Track ratingKey="{i + 1}" title="{title}"/>'
                for i, title in enumerate(titles[start:start + 50], start)) + '</MediaContainer>')
        self.plex.request = AsyncMock(side_effect=request)
        tracks = await self.plex.search(self.settings, "Song", "1")
        self.assertEqual(len(tracks), 60)
        self.assertEqual(tracks[0].id, "60")
        self.assertEqual(self.plex.request.call_args_list[-1].kwargs["params"]["X-Plex-Container-Start"], "50")

    async def test_punctuation_fallback_filters_and_deduplicates(self):
        async def request(url, *args, **kwargs):
            if url.endswith("/sections"):
                return self.libraries
            term = kwargs["params"]["title"]
            if term == "sweet child o mine":
                return ElementTree.fromstring('<MediaContainer/>')
            return ElementTree.fromstring('<MediaContainer>'
                '<Track ratingKey="1" title="Sweet Child O’ Mine" duration="unknown"/>'
                '<Track ratingKey="2" title="Sweet Caroline"/>'
                '</MediaContainer>')
        self.plex.request = AsyncMock(side_effect=request)
        tracks = await self.plex.search(self.settings, "sweet child o mine", "1")
        self.assertEqual([track.id for track in tracks], ["1"])
        self.assertEqual(tracks[0].duration, 0)

    async def test_accent_fallback(self):
        async def request(url, *args, **kwargs):
            if url.endswith("/sections"):
                return self.libraries
            if kwargs["params"].get("title") == "tel":
                return ElementTree.fromstring('<MediaContainer><Track ratingKey="1" title="Hôtel"/></MediaContainer>')
            return ElementTree.fromstring('<MediaContainer/>')
        self.plex.request = AsyncMock(side_effect=request)
        tracks = await self.plex.search(self.settings, "hotel", "1")
        self.assertEqual([track.id for track in tracks], ["1"])

    async def test_typo_and_artist_search_fallback(self):
        catalog = [
            ("1", "I Really Want to Stay at Your House", "Various Artists", "Rosa Walton"),
            ("2", "House of the Rising Sun", "The Animals", ""),
            ("3", "Bohemian Rhapsody", "Queen", ""),
            ("4", "By the Way", "Red Hot Chili Peppers", ""),
            ("5", "I Really Want to Stay at Your House (Slowed Remix)", "Various Artists", "Rosa Walton"),
            ("6", "We Will Rock You", "Queen", ""),
        ]

        async def request(url, *args, **kwargs):
            if url.endswith("/sections"):
                return self.libraries
            params = kwargs["params"]
            items = []
            for key, title, grandparent, original in catalog:
                if "title" in params and params["title"].casefold() not in title.casefold():
                    continue
                if "artist.title" in params and params["artist.title"].casefold() not in grandparent.casefold():
                    continue
                if "originalTitle" in params and params["originalTitle"].casefold() not in original.casefold():
                    continue
                attr = f' originalTitle="{original}"' if original else ""
                items.append(f'<Track ratingKey="{key}" title="{title}" grandparentTitle="{grandparent}"{attr}/>')
            return ElementTree.fromstring(f"<MediaContainer>{''.join(items)}</MediaContainer>")

        self.plex.request = AsyncMock(side_effect=request)
        tracks = await self.plex.search(self.settings, "i realy want to stay at your house", "1")
        self.assertEqual([track.id for track in tracks], ["1", "5"])

        tracks = await self.plex.search(self.settings, "i realy want to stay in your huose", "1")
        self.assertEqual([track.id for track in tracks], ["1", "5"])

        tracks = await self.plex.search(self.settings, "rosa walton i really want to stay at your house", "1")
        self.assertEqual([track.id for track in tracks], ["1", "5"])

        tracks = await self.plex.search(self.settings, "queen bohemian rapsody", "1")
        self.assertEqual([track.id for track in tracks], ["3"])

        tracks = await self.plex.search(self.settings, "boheman rapsody", "1")
        self.assertEqual([track.id for track in tracks], ["3"])

        tracks = await self.plex.search(self.settings, "red hot chili peppers by the way", "1")
        self.assertEqual([track.id for track in tracks], ["4"])

        # Ricerca per solo nome dell'autore (sia grandparentTitle che originalTitle e con typo)
        tracks = await self.plex.search(self.settings, "Queen", "1")
        self.assertEqual([track.id for track in tracks], ["3", "6"])

        tracks = await self.plex.search(self.settings, "Rosa Walton", "1")
        self.assertEqual([track.id for track in tracks], ["1", "5"])

        tracks = await self.plex.search(self.settings, "Rosa Waltn", "1")
        self.assertEqual([track.id for track in tracks], ["1", "5"])

    async def test_search_is_bounded_even_if_server_ignores_pagination(self):
        async def request(url, *args, **kwargs):
            if url.endswith("/sections"):
                return self.libraries
            return ElementTree.fromstring('<MediaContainer totalSize="5000">' + ''.join(
                f'<Track ratingKey="{i}" title="Song {i}"/>' for i in range(50)) + '</MediaContainer>')
        self.plex.request = AsyncMock(side_effect=request)
        tracks = await self.plex.search(self.settings, "Song", "1")
        self.assertEqual(len(tracks), 50)
        self.assertEqual(self.plex.request.call_count, 3)

    async def test_stream_does_not_expose_token(self):
        self.plex.request = AsyncMock(return_value=ElementTree.fromstring('<MediaContainer><Track><Media><Part key="/library/parts/42/file.flac"/></Media></Track></MediaContainer>'))
        url = await self.plex.stream(self.settings, Track("42", "Song", "Artist", "Album", "Music", 1000))
        self.assertEqual(url, "http://plex/library/parts/42/file.flac")
        self.assertNotIn("secret", url)

    async def test_wrong_server_identity_rejected(self):
        self.plex.request = AsyncMock(return_value=ElementTree.fromstring('<MediaContainer machineIdentifier="other"/>'))
        resource = {"clientIdentifier": "expected", "accessToken": "secret", "connections": [{"uri": "http://plex"}]}
        with self.assertRaises(PlexError):
            await self.plex.connect(resource)

    async def test_missing_part(self):
        self.plex.request = AsyncMock(return_value=ElementTree.fromstring('<MediaContainer><Track/></MediaContainer>'))
        with self.assertRaises(PlexError):
            await self.plex.stream(self.settings, Track("1", "Song", "", "", "", 0))

    async def test_stream_skips_missing_and_invalid_versions(self):
        self.plex.request = AsyncMock(return_value=ElementTree.fromstring('<MediaContainer><Track><Media>'
            '<Part key="/library/parts/1/missing.flac" exists="0"/>'
            '<Part key="https://other.example/file.flac"/>'
            '<Part key="/library/parts/2/a.flac" accessible="false"/>'
            '<Part key="/library/parts/3/good.flac" selected="1"/>'
            '<Part key="/library/parts/4/alternative.mp3"/>'
            '</Media></Track></MediaContainer>'))
        urls = await self.plex.streams(self.settings, Track("1", "Song", "", "", "", 0))
        self.assertEqual(urls, ["http://plex/library/parts/3/good.flac", "http://plex/library/parts/4/alternative.mp3"])
        self.assertEqual(self.plex.request.call_args.kwargs["params"], {"checkFiles": "1"})

    async def test_stream_accepts_query_and_encodes_unicode_without_token(self):
        self.plex.request = AsyncMock(return_value=ElementTree.fromstring('<MediaContainer><Track><Media>'
            '<Part key="/library/parts/1/Café song.flac?download=1&amp;X-Plex-Token=secret"/>'
            '</Media></Track></MediaContainer>'))
        url = await self.plex.stream(self.settings, Track("1", "Song", "", "", "", 0))
        self.assertEqual(url, "http://plex/library/parts/1/Caf%C3%A9%20song.flac?download=1")
        self.assertNotIn("secret", url)

    async def test_no_accessible_files(self):
        self.plex.request = AsyncMock(return_value=ElementTree.fromstring('<MediaContainer><Track><Media>'
            '<Part key="/library/parts/1/file.flac" exists="0"/></Media></Track></MediaContainer>'))
        with self.assertRaisesRegex(PlexError, "accessibile"):
            await self.plex.streams(self.settings, Track("1", "Song", "", "", "", 0))

    async def test_playlists_and_playlist_tracks(self):
        async def request(url, token="", *args, **kwargs):
            if url.endswith("/playlists"):
                return ElementTree.fromstring(
                    '<MediaContainer>'
                    '<Playlist ratingKey="101" title="My Mix" playlistType="audio" leafCount="2" duration="300000" composite="/playlists/101/composite/1"/>'
                    '<Playlist ratingKey="102" title="Video List" playlistType="video" leafCount="5" duration="900000"/>'
                    '</MediaContainer>'
                )
            if url.endswith("/playlists/101/items"):
                return ElementTree.fromstring(
                    '<MediaContainer>'
                    '<Track ratingKey="55" title="Track One" grandparentTitle="Artist A" parentTitle="Album A" librarySectionTitle="Music" duration="150000" thumb="/library/metadata/55/thumb/1"/>'
                    '<Track ratingKey="56" title="Track Two" originalTitle="Artist B" parentTitle="Album B" duration="150000"/>'
                    '</MediaContainer>'
                )
            return ElementTree.fromstring('<MediaContainer/>')

        self.plex.request = AsyncMock(side_effect=request)
        playlists = await self.plex.playlists(self.settings, user_token="user-tok")
        self.assertEqual(len(playlists), 1)
        self.assertEqual(playlists[0].id, "101")
        self.assertEqual(playlists[0].title, "My Mix")
        self.assertEqual(playlists[0].track_count, 2)
        self.assertEqual(self.plex.thumbs.get("pl_101"), "/playlists/101/composite/1")

        tracks = await self.plex.playlist_tracks(self.settings, "101", user_token="user-tok")
        self.assertEqual([t.id for t in tracks], ["55", "56"])
        self.assertEqual(tracks[0].artist, "Artist A")
        self.assertEqual(tracks[1].artist, "Artist B")
        self.assertEqual(self.plex.thumbs.get("55"), "/library/metadata/55/thumb/1")

    async def test_http_chunking_headers_and_sanitized_errors(self):
        received = []

        async def handler(request):
            received.append(request.headers.get("X-Plex-Token"))
            response = web.StreamResponse(headers={"Content-Type": "application/xml"})
            await response.prepare(request)
            await response.write(b'<MediaContainer')
            await asyncio.sleep(0.01)
            await response.write(b' size="1"/>')
            await response.write_eof()
            return response

        async def denied(request):
            return web.Response(status=401, text="secret should never escape")

        app = web.Application()
        app.router.add_get("/chunks", handler)
        app.router.add_get("/denied", denied)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        url = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
        try:
            root = await self.plex.request(url + "/chunks", "secret")
            self.assertEqual(root.get("size"), "1")
            self.assertEqual(received, ["secret"])
            with self.assertRaises(PlexError) as error:
                await self.plex.request(url + "/denied", "secret")
            self.assertNotIn("secret", str(error.exception))
        finally:
            await runner.cleanup()

    async def test_resolve_user_token_and_report_timeline(self):
        settings = Settings(server_url="http://127.0.0.1", server_token="admin-srv-tok", server_id="srv-123", token="admin-cloud-tok")
        self.plex.resources = AsyncMock(return_value=[
            {"clientIdentifier": "srv-123", "accessToken": "user-scoped-srv-tok"}
        ])
        resolved = await self.plex.resolve_user_token(settings, user_token="friend-cloud-tok", username="kikmine")
        self.assertEqual(resolved, "user-scoped-srv-tok")

        # Test shared servers fallback
        self.plex.resources = AsyncMock(return_value=[])
        async def shared_req(url, token="", *args, **kwargs):
            if "shared_servers" in url:
                return ElementTree.fromstring(
                    '<MediaContainer>'
                    '<SharedServer username="blackdevilwe" accessToken="blackdevilwe-srv-tok"/>'
                    '</MediaContainer>'
                )
            return ElementTree.fromstring('<MediaContainer/>')
        self.plex.request = AsyncMock(side_effect=shared_req)
        resolved_shared = await self.plex.resolve_user_token(settings, user_token="blackdevilwe-cloud-tok", username="Blackdevilwe")
        self.assertEqual(resolved_shared, "blackdevilwe-srv-tok")

        # Test report_timeline uses user-specific token and does NOT fall back to admin token
        timeline_headers = []
        async def timeline_handler(request):
            timeline_headers.append(dict(request.headers))
            return web.Response(status=200, text="<Response/>")

        app = web.Application()
        app.router.add_get("/:/timeline", timeline_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        settings.server_url = f"http://127.0.0.1:{port}"

        try:
            track = Track("42", "Song", "Artist", "Album", "Music", 180000)
            await self.plex.report_timeline(
                settings, track, "playing", 15000,
                user_token="blackdevilwe-cloud-tok", username="Blackdevilwe",
                client_id="client-1", device_name="Discord (Blackdevilwe)",
            )
            self.assertEqual(len(timeline_headers), 1)
            self.assertEqual(timeline_headers[0]["X-Plex-Token"], "blackdevilwe-srv-tok")
            self.assertEqual(timeline_headers[0]["X-Plex-Device-Name"], "Discord (Blackdevilwe)")
        finally:
            await runner.cleanup()
