import asyncio
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit

import aiohttp
from defusedxml import ElementTree

from .store import Settings


class PlexError(Exception):
    """Errore già sicuro da mostrare su Discord (nessun URL o token)."""


SEARCH_LIMIT = 200
SEARCH_PAGE_SIZE = 50
CHAR_MAP = str.maketrans({"æ": "ae", "œ": "oe", "ø": "o", "ł": "l", "đ": "d", "ð": "d", "þ": "th"})


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold().translate(CHAR_MAP))
    value = "".join(c for c in value if not unicodedata.combining(c) and c not in "'’‘ʼ`´ʹʽ")
    return " ".join(re.findall(r"[^\W_]+", value))


def word_matches(word: str, target: str, target_words: list[str]) -> bool:
    if word in target_words:
        return True
    if len(word) >= 3:
        if word in target:
            return True
        return any(len(tw) >= 3 and SequenceMatcher(None, word, tw).ratio() >= 0.8 for tw in target_words)
    return False


def number(value: str | None, default: int = 0) -> int:
    try:
        return max(0, int(value or ""))
    except ValueError:
        return default


def valid_url(value: str) -> str:
    parts = urlsplit(value)
    if (parts.scheme not in ("http", "https") or not parts.hostname
            or parts.username or parts.password or parts.query or parts.fragment
            or parts.path not in ("", "/")):
        raise PlexError("Usa un URL di base http(s), senza credenziali, percorso o query.")
    try:
        _ = parts.port
    except ValueError:
        raise PlexError("Porta dell'URL non valida.") from None
    return value.rstrip("/")


@dataclass(frozen=True)
class Library:
    id: str
    title: str


@dataclass(frozen=True)
class Track:
    id: str
    title: str
    artist: str
    album: str
    library: str
    duration: int

    @property
    def label(self):
        return f"{self.artist} — {self.title}"


class Plex:
    def __init__(self, session: aiohttp.ClientSession, client_id: str):
        self.session = session
        self.client_id = client_id
        self.limit = asyncio.Semaphore(4)

    def headers(self, token: str = "", json: bool = False):
        headers = {
            "X-Plex-Product": "Plexcord", "X-Plex-Version": "1.0",
            "X-Plex-Client-Identifier": self.client_id,
            "X-Plex-Platform": "Python", "X-Plex-Device-Name": "Plexcord",
            "Accept": "application/json" if json else "application/xml",
        }
        if token:
            headers["X-Plex-Token"] = token
        return headers

    async def request(self, url, token="", *, method="GET", params=None, json=False):
        try:
            async with self.limit:
                async with self.session.request(
                    method, url, headers=self.headers(token, json), params=params,
                    allow_redirects=False, timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    if response.status in (401, 403):
                        raise PlexError("Accesso Plex negato: ripeti /plex login e scegli nuovamente il server.")
                    if response.status >= 300:
                        raise PlexError(f"Plex ha risposto con HTTP {response.status}.")
                    # Evita di caricare accidentalmente intere librerie in memoria.
                    body = bytearray()
                    async for chunk in response.content.iter_chunked(65536):
                        body.extend(chunk)
                        if len(body) > 4 * 1024 * 1024:
                            raise PlexError("Risposta Plex troppo grande: restringi la ricerca.")
                    if json:
                        import json as json_module
                        return json_module.loads(body)
                    return ElementTree.fromstring(body)
        except PlexError:
            raise
        except (TimeoutError, aiohttp.ClientError):
            raise PlexError("Plex non raggiungibile. Controlla rete, certificato e /plex address.") from None
        except Exception:
            raise PlexError("Risposta Plex non valida.") from None

    async def pin(self):
        pin = await self.request("https://plex.tv/api/v2/pins", method="POST", params={"strong": "true"}, json=True)
        query = urlencode({"clientID": self.client_id, "code": pin["code"], "context[device][product]": "Plexcord"})
        return pin["id"], f"https://app.plex.tv/auth#?{query}", min(int(pin.get("expiresIn", 300)), 600)

    async def check_pin(self, pin_id):
        data = await self.request(f"https://plex.tv/api/v2/pins/{pin_id}", json=True)
        return data.get("authToken")

    async def resources(self, token):
        data = await self.request("https://plex.tv/api/v2/resources", token, params={"includeHttps": "1", "includeRelay": "1"}, json=True)
        return [r for r in data if "server" in r.get("provides", "").split(",")]

    async def connect(self, resource, override=""):
        token = resource.get("accessToken")
        if not token:
            raise PlexError("Questo server non espone un token di accesso.")
        connections = sorted(resource.get("connections", []), key=lambda c: (bool(c.get("relay")), not bool(c.get("local")), c.get("protocol") != "https"))
        candidates = [valid_url(override)] if override else [c["uri"].rstrip("/") for c in connections]
        for url in dict.fromkeys(candidates):
            try:
                identity = await self.request(url + "/identity", token)
                if identity.get("machineIdentifier") != resource["clientIdentifier"]:
                    continue
                await self.request(url + "/library/sections", token)
                return url, token
            except PlexError:
                continue
        raise PlexError("Server non raggiungibile o identità errata. Imposta /plex address con un indirizzo accessibile dal container.")

    @staticmethod
    def ready(settings):
        if not settings.server_url or not settings.server_token:
            raise PlexError("Configura prima /plex login e /plex server.")

    async def libraries(self, settings: Settings):
        self.ready(settings)
        root = await self.request(settings.server_url + "/library/sections", settings.server_token)
        return [Library(d.get("key"), d.get("title", "Musica")) for d in root.findall("Directory") if d.get("type") == "artist"]

    async def search(self, settings: Settings, query: str, library: str | None = None):
        libraries = await self.libraries(settings)
        enabled = [lib for lib in libraries if settings.libraries is None or lib.id in settings.libraries]
        if library:
            enabled = [lib for lib in enabled if lib.id == library]
        if not enabled:
            raise PlexError("Nessuna libreria musicale abilitata per questa ricerca. Usa /plex libraries.")

        needle = normalized(query)
        words = needle.split()
        if not words:
            raise PlexError("Inserisci almeno una lettera o un numero nel titolo.")

        required = len(words) if len(words) <= 3 else len(words) - max(1, len(words) // 4)

        def matches(track: Track) -> bool:
            title = normalized(track.title)
            artist = normalized(track.artist)
            if not title and not artist:
                return False
            if (title and (needle in title or SequenceMatcher(None, needle, title).ratio() >= 0.75)) or (
                artist and (needle in artist or SequenceMatcher(None, needle, artist).ratio() >= 0.75)
            ):
                return True
            title_words = title.split()
            matched_title = sum(1 for word in words if word_matches(word, title, title_words))
            if matched_title >= required:
                return True
            artist_words = artist.split()
            matched_artist = sum(1 for word in words if word_matches(word, artist, artist_words))
            if matched_artist >= required:
                return True
            if matched_title == 0 and matched_artist == 0:
                return False
            full = normalized(f"{track.title} {track.artist} {track.album}")
            full_words = full.split()
            matched_full = sum(1 for word in words if word_matches(word, full, full_words))
            return matched_full >= required

        def score(track: Track):
            title = normalized(track.title)
            if title == needle:
                return (0, 0, 0)
            if needle in title:
                return (1, 0, 0)
            if all(word in title for word in words):
                return (2, 0, 0)
            title_words = title.split()
            matched_title = sum(1 for word in words if word_matches(word, title, title_words))
            if matched_title == len(words):
                return (3, int(len(title_words) != len(words)), 0)
            artist = normalized(track.artist)
            if artist == needle:
                return (4, 0, 0)
            if artist and (needle in artist or all(word in artist for word in words)):
                return (5, 0, 0)
            artist_words = artist.split()
            matched_artist = sum(1 for word in words if word_matches(word, artist, artist_words))
            if matched_artist == len(words):
                return (6, int(len(artist_words) != len(words)), 0)
            full = normalized(f"{track.title} {track.artist} {track.album}")
            full_words = full.split()
            matched_full = sum(1 for word in words if word_matches(word, full, full_words))
            return (7, -matched_full, -(matched_title + matched_artist))

        async def candidates(lib, term, field="title"):
            found = {}
            # Paginazione limitata: niente scansione o indice completo della libreria.
            for start in range(0, SEARCH_LIMIT, SEARCH_PAGE_SIZE):
                root = await self.request(
                    f"{settings.server_url}/library/sections/{lib.id}/all", settings.server_token,
                    params={"type": "10", field: term, "X-Plex-Container-Start": str(start),
                            "X-Plex-Container-Size": str(SEARCH_PAGE_SIZE)},
                )
                elements = root.findall("Track")
                added = 0
                for t in elements:
                    key = t.get("ratingKey", "")
                    if not key.isdigit() or key in found:
                        continue
                    added += 1
                    found[key] = Track(key, t.get("title") or "Senza titolo",
                                       t.get("originalTitle") or t.get("grandparentTitle") or "Artista sconosciuto",
                                       t.get("parentTitle") or "", lib.title, number(t.get("duration")))
                total = number(root.get("totalSize"), start + len(elements))
                if not added or len(elements) < SEARCH_PAGE_SIZE or start + len(elements) >= total:
                    break
            return list(found.values())

        async def artist_candidates(lib, term):
            tracks = await candidates(lib, term, "artist.title")
            if not tracks:
                tracks = await candidates(lib, term, "originalTitle")
            return tracks

        async def section(lib):
            direct = await candidates(lib, query)
            found = {track.id: track for track in direct}
            if not any(normalized(track.title) == needle for track in direct):
                # Una frase Plex è una sottostringa: apostrofi, trattini, accenti
                # o piccoli errori di battitura possono impedirne la corrispondenza.
                # Recupera candidati con poche parole/sottostringhe e verifica localmente.
                ordered_words = [w for w in sorted(set(words), key=lambda word: (-len(word), word)) if len(w) >= 2]
                terms = list(ordered_words[:3])
                if len(words) >= 4:
                    mid = len(words) // 2
                    terms.extend((" ".join(words[:mid]), " ".join(words[mid:])))
                terms.extend(ordered_words[3:4])
                terms.extend(w for w in (words[0], words[-1]) if len(w) >= 2)

                matched_terms = 0
                for term in dict.fromkeys(terms):
                    if term.casefold() == query.casefold():
                        continue
                    added = False
                    for track in await candidates(lib, term):
                        if matches(track):
                            found.setdefault(track.id, track)
                            added = True
                    if added:
                        matched_terms += 1
                    if matched_terms >= 2 and any(score(t)[0] <= 3 for t in found.values()):
                        break

                has_full_title = any(
                    score(t)[0] in (0, 2, 3) and len(normalized(t.title).split()) == len(words)
                    for t in found.values()
                )
                if len(direct) < 25 and not has_full_title:
                    for track in await artist_candidates(lib, query):
                        if matches(track):
                            found.setdefault(track.id, track)
                    if not any(score(t)[0] <= 6 for t in found.values()):
                        for term in dict.fromkeys(ordered_words[:2]):
                            if term.casefold() == query.casefold():
                                continue
                            for track in await artist_candidates(lib, term):
                                if matches(track):
                                    found.setdefault(track.id, track)

                if not found:
                    fragments = [
                        frag
                        for word in (ordered_words or words)[:2]
                        if len(word) > 3
                        for frag in (word[:3], word[-3:])
                    ]
                    for term in dict.fromkeys(fragments):
                        if term.casefold() == query.casefold():
                            continue
                        for track in await candidates(lib, term):
                            if matches(track):
                                found.setdefault(track.id, track)
                        if not found:
                            for track in await artist_candidates(lib, term):
                                if matches(track):
                                    found.setdefault(track.id, track)
            return sorted(found.values(), key=score)[:SEARCH_LIMIT]

        results = await asyncio.gather(*(section(lib) for lib in enabled))
        # Interleaving e deduplica: non nascondere le altre librerie o le pagine successive.
        tracks = {track.id: track for index in range(SEARCH_LIMIT) for group in results
                  if len(group) > index for track in (group[index],)}
        return sorted(tracks.values(), key=score)[:SEARCH_LIMIT]

    async def stream(self, settings: Settings, track: Track):
        """Prima sorgente, mantenuta per i client che non gestiscono alternative."""
        return (await self.streams(settings, track))[0]

    async def streams(self, settings: Settings, track: Track):
        self.ready(settings)
        root = await self.request(f"{settings.server_url}/library/metadata/{track.id}", settings.server_token,
                                  params={"checkFiles": "1"})
        parts = root.findall("Track/Media/Part")
        if not parts:
            raise PlexError("Il brano non contiene un file audio riproducibile.")
        urls = []
        for part in sorted(parts, key=lambda p: p.get("selected") != "1"):
            if any(part.get(flag, "").casefold() in ("0", "false") for flag in ("exists", "accessible")):
                continue
            key = part.get("key", "")
            try:
                parsed = urlsplit(key)
            except ValueError:
                continue
            path = unquote(parsed.path)
            if (parsed.scheme or parsed.netloc or parsed.fragment or not path.startswith("/library/parts/")
                    or ".." in path.split("/") or any(c in unquote(key) for c in ("\r", "\n", "\\"))):
                continue
            # Le query di Plex (es. download=1) sono valide, ma eventuali token
            # restano esclusivamente nell'header HTTP.
            query = urlencode([(k, v) for k, v in parse_qsl(parsed.query)
                               if k.casefold() != "x-plex-token"])
            url = settings.server_url + quote(parsed.path, safe="/%:@") + ("?" + query if query else "")
            if url not in urls:
                urls.append(url)
        if not urls:
            raise PlexError("Nessun file audio accessibile per questo brano. Verifica il file e i permessi sul server Plex.")
        return urls[:8]
