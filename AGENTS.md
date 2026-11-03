# AGENTS.md — Linee guida per Agenti AI su Plexcord

Questo documento descrive l'architettura, i vincoli progettuali e le convenzioni tecniche di **Plexcord** per qualsiasi agente AI o sviluppatore che modifichi il repository.

---

## 1. Filosofia e Vincoli Principali

1. **Ultraleggero e Zero Servizi Esterni**:
   - Nessun Lavalink, Redis, Node.js, bundler frontend o database esterno.
   - Le uniche dipendenze Python consentite sono quelle in [`requirements.txt`](requirements.txt): `discord.py[voice]`, `aiohttp` e `defusedxml`.
   - La persistenza usa esclusivamente **SQLite** integrato nella libreria standard (`sqlite3`), salvato nel volume `/app/data/plexcord.db`.
2. **100% Compatibile con Docker**:
   - Il container gira come utente non-root (`plexcord`, UID `10001`), con filesystem read-only (`read_only: true`), `tmpfs` per `/tmp` e `PYTHONUNBUFFERED=1`.
   - Non scrivere mai file temporanei o di stato fuori da `PLEXCORD_DATA` (`/app/data`) o `/tmp`.
   - Gli asset grafici statici si trovano in `icon/` (`icon/logo.jpg`, `icon/banner.jpg`) e vengono copiati nell'immagine Docker (`COPY icon ./icon`).
3. **Internazionalizzazione (i18n)**:
   - La lingua predefinita di sistema è l'**Inglese (`en`)** per release pubblica (descrizioni comandi slash, risposte bot, interfaccia Activity).
   - È supportata la traduzione completa in **Italiano (`it`)**, selezionabile tramite `/settings language:it` o dalla scheda Config dell'Activity.
   - Le stringhe localizzate del bot sono gestite tramite il dizionario `MESSAGES` in [`plexcord/bot.py`](plexcord/bot.py) e i helper `tr()` / `bot.t()`.
   - L'Activity implementa `I18N` dinamico client-side (`data-i18n`, `data-i18n-ph`, `data-i18n-title`) con sincronizzazione persistita sul server.
4. **Sicurezza delle Credenziali**:
   - I token Plex (`token`, `server_token`, `plex_token` utente), il `DISCORD_TOKEN`, il `DISCORD_CLIENT_SECRET` e gli URL interni del server Plex **non devono mai essere esposti** nei messaggi Discord, nei log di errore o al client browser/Activity.
   - Tutte le eccezioni destinate all'utente devono usare `PlexError` con messaggi sanitizzati.
   - FFmpeg riceve `X-Plex-Token` tramite l'header HTTP (`-headers`), mai nella query string dell'URL.

---

## 2. Architettura dei Moduli

- [`plexcord/__main__.py`](plexcord/__main__.py):
  Entrypoint asincrono. Gestisce `SIGINT`/`SIGTERM` per chiudere ordinatamente sessioni vocali, server HTTP Activity, sessioni Rich Presence e connessioni SQLite.
- [`plexcord/store.py`](plexcord/store.py):
  Persistenza SQLite con migrazione automatica dello schema:
  - Tabella `guilds`: impostazioni per singolo server Discord (`Settings`: modalità `mode`, lingua `language` `"en"`/`"it"`, `dj_only`, `dj_role`, ecc.).
  - Tabella `users`: collegamenti tra account Discord e account personali Plex (`UserLink`) per lo scrobbling e le playlist personali.
  - Tabella `discord_oauth`: token OAuth2 per il Rich Presence headless lato server.
  - Tabella `meta`: chiavi globali del bot (`client_id`, `discord_client_secret`).
- [`plexcord/plex.py`](plexcord/plex.py):
  Client asincrono verso `plex.tv` e il Plex Media Server:
  - Autenticazione OAuth/PIN a 4 caratteri (`pin_code`, `check_pin`) per il server e per i singoli utenti (`plex.tv/link`).
  - Ricerca multi-libreria (`search`) con normalizzazione Unicode, tolleranza agli errori di battitura (`SequenceMatcher`), ricerca per titolo e autore (`artist.title` / `originalTitle`) e caching immediato delle copertine (`self.thumbs`).
  - Playlist personali dell'utente (`playlists`, `playlist_tracks`, `resolve_user_token`).
  - Proxy sicuro delle copertine (`artwork`) per brani e playlist (`pl_<id>`) con deduplicazione in RAM.
  - Scrobbling e aggiornamento stato di riproduzione su Plex Dashboard (`report_timeline` su `/:/timeline`) per ogni singolo ascoltatore collegato.
- [`plexcord/player.py`](plexcord/player.py):
  Pipeline audio e gestione della coda per singolo server Discord:
  - `ManagedOpusAudio(discord.FFmpegPCMAudio)`: FFmpeg decodifica lo stream HTTP in PCM (`s16le` 48kHz stereo); ogni frame da 20ms viene scalato in tempo reale in Python (`scale_pcm`) secondo `self.volume` e codificato in Opus tramite `discord.opus.Encoder` (`libopus0`).
  - **Invariante critica sul volume**: `Player.set_volume()` aggiorna `source.volume` al volo (effetto entro 20ms) **senza mai fermare o riavviare FFmpeg** né eseguire `seek()`.
  - Verifica preliminare (`source.prepare()`) sul primo pacchetto audio prima di avviare `voice.play()` con fallback automatico su versioni alternative del file.
  - Sincronizzazione `sync_timeline()` verso Plex (`/:/timeline` per tutti gli ascoltatori collegati nel canale vocale), stato presenza del bot e stato del canale vocale Discord.
- [`plexcord/presence.py`](plexcord/presence.py):
  Rich Presence lato server (headless session `POST /users/@me/headless-sessions` con scope `activities.write`):
  - Mostra lo stato *"Listening to Plex"* sul profilo Discord personale di ogni ascoltatore autorizzato nel canale vocale.
- [`plexcord/bot.py`](plexcord/bot.py):
  Client Discord (`Plexcord`) e comandi slash (`Tree`):
  - **Invariante `Tree.sync()`**: prima di eseguire `bulk_upsert_global_commands`, recupera i comandi globali esistenti e preserva sempre i comandi `type == 4` (`PRIMARY_ENTRY_POINT`) richiesti dalle Discord Activities (evita l'errore Discord `50240`). La sincronizzazione gira in background (`asyncio.create_task`) in `setup_hook()` per non ritardare la connessione al Gateway.
  - **Controllo della riproduzione e permessi DJ**: di default chiunque si trovi nello stesso canale vocale del bot (`require_voice`) può controllare la musica. Se l'opzione `dj_only` è attiva (`Settings.dj_only`), solo gli amministratori (permesso `manage_guild` o `administrator` o proprietario del server) e i membri con il ruolo DJ configurato (`Settings.dj_role`) possono gestire la riproduzione, sia via comandi slash e bottoni interattivi che dall'Activity.
  - **Senza Privileged Intents**: `intents.members` e `intents.message_content` sono `False`. Per rilevare gli utenti nel canale vocale usa sempre `channel.voice_states` oltre a `channel.members`.
- [`plexcord/activity.py`](plexcord/activity.py):
  Server HTTP/WebSocket ultraleggero (`aiohttp.web` sulla porta `8080`) e SPA HTML/CSS/JS self-contained (`ACTIVITY_HTML`) per **Discord Embedded App SDK**:
  - Endpoint asset `/api/logo` e `/api/banner` che servono le immagini di branding da `icon/` con cache HTTP.
  - Supporta handshake `postMessage` con l'iframe di Discord (`AUTHORIZE` + `/api/discord_token` + `AUTHENTICATE` + `SET_ACTIVITY` per il Discord Rich Presence personale dell'utente).
  - Include viste per: **Cerca** (con miniature copertina), **Playlist** personali Plex, **Coda** interattiva, **RPC & Account** (collegamento PIN 4 cifre e Discord Client Secret) e **Config** completa del bot (inclusa selezione lingua EN/IT e permessi DJ).
  - Responsive per layout mobile, desktop e sidebar Discord.

---

## 3. Test e Verifica

Prima di concludere qualsiasi modifica, verifica sempre:

1. **Sintassi Python e JavaScript**:
   ```bash
   python3 -m unittest discover -s tests -v
   ```
2. **Controllo sintassi JS dell'Activity**:
   Verifica che lo `<script>` dentro `ACTIVITY_HTML` in `plexcord/activity.py` superi `node --check`.
3. **Allineamento dei test**:
   - Se aggiungi o rimuovi un comando slash top-level in [`plexcord/bot.py`](plexcord/bot.py), aggiorna il set dei comandi attesi in [`tests/test_bot.py`](tests/test_bot.py).
   - Non rimuovere i controlli di sicurezza sui token nei test (`tests/test_plex.py`, `tests/test_player.py`, `tests/test_audio.py`).
