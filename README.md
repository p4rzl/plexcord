# Plexcord

Bot Discord ultraleggero per ascoltare i brani e le playlist del proprio server Plex nei canali vocali, con supporto completo per **Discord Activity (Embedded App SDK)**, **Discord Rich Presence (RPC)** personale e **sincronizzazione con la Dashboard Plex**.

**Login, scelta del server, librerie, playlist e impostazioni si gestiscono direttamente da Discord** (sia tramite **Comandi Slash** sia dall'**Activity grafica**). All'avvio serve soltanto il token del bot Discord.

---

## Funzionalità Principali

- **Doppia modalità operativa (`/mode`)**:
  - **🎛️ Modalità Activity**: controlla e configura l'intero bot dall'interfaccia grafica dentro il canale vocale di Discord (o via Web Player).
  - **💬 Modalità Comandi Slash**: usa i comandi slash classici (`/play`, `/playlist`, `/queue`, `/plex`, `/settings`, ecc.) con autocompletamento e pulsanti interattivi.
- **Controllo condiviso nel canale vocale**: chiunque si trovi nello stesso canale vocale del bot può cercare brani, gestire la riproduzione e usare i pulsanti interattivi (`⏯️ Pausa/Riprendi`, `⏭️ Salta`, `🔀 Mescola`, `⏹️ Stop`, `👋 Esci`) o la Discord Activity.
- **Discord Activity (Embedded App SDK) & Web Player integrato**:
  - Interfaccia responsiva (si adatta automaticamente anche quando si apre la chat laterale del canale vocale di Discord).
  - **Ricerca live con miniature delle copertine** per titolo del brano o nome dell'autore, con tasti **▶️ Ora** (riproduci subito) e **➕ Coda**.
  - **🎶 Playlist personali Plex**: collegando il proprio account Plex, ogni utente può sfogliare le proprie playlist audio, aprirle per vedere i singoli brani oppure riprodurle interamente (anche in modalità **🔀 Shuffle**).
  - **Volume in tempo reale (0–150%)**: regolazione istantanea del volume (ogni 20ms su stream PCM → Opus) **senza mai bloccare o riavviare la canzone**.
  - **Seek interattivo** cliccando sulla barra di avanzamento e gestione completa della coda (riproduci subito, sposta in cima, rimuovi).
- **🟣 Discord Rich Presence (RPC) & 🎧 Scrobbling Plex**:
  - **RPC sul profilo personale Discord**: autorizzando l'app nell'Activity (`🟣 Attiva RPC Utente`), il brano in ascolto, l'artista, l'album e il timer live compaiono direttamente sul **tuo profilo personale Discord** (*"Sta ascoltando..."*).
  - **Collegamento Account Plex con PIN a 4 cifre (`plex.tv/link`)**: collegando il tuo account Plex (dalla scheda `🎧 RPC & Account` o con `/link`), la tua attività di ascolto viene mostrata in tempo reale anche sulla **Dashboard di Plex** e aggiorna le statistiche di ascolto del tuo profilo Plex.
- **Ricerca intelligente e tollerante agli errori**:
  - Ricerca contemporanea in tutte le librerie musicali abilitate per **titolo del brano**, **nome dell'autore** o entrambi, tollerante ad accenti, punteggiatura e piccoli errori di battitura.
- **Ultraleggero e sicuro**:
  - Nessun Lavalink, Redis, Node.js o database esterno. Persistenza in SQLite, processo Docker non-root e filesystem read-only.

---

## 1. Crea il bot Discord

1. Apri il [Discord Developer Portal](https://discord.com/developers/applications), crea un'applicazione e vai su **Bot**.
2. Genera/copia il token. **Non pubblicarlo e non inserirlo in un comando Discord.**
3. In **OAuth2 → URL Generator**, seleziona gli scope `bot` e `applications.commands`.
4. Permessi del bot: **View Channels**, **Send Messages**, **Connect**, **Speak**. Non serve Administrator.
5. Apri il link generato e invita il bot nel tuo server.

Non servono intent privilegiati: **Message Content**, **Server Members** e **Presence** possono restare disabilitati.

---

## 2. Avvia con Docker

Serve Docker con il plugin Compose (su Windows: Docker Desktop in modalità container Linux).

Copia `.env.example` in `.env`:

```powershell
# Windows PowerShell
Copy-Item .env.example .env
```

```sh
# Linux/macOS
cp .env.example .env
```

Modifica `.env` e imposta `DISCORD_TOKEN`:

| Variabile `.env` | Descrizione |
| --- | --- |
| `DISCORD_TOKEN` | **(Obbligatorio)** Token del bot Discord |
| `DISCORD_GUILD_ID` | *(Opzionale)* ID del server Discord per sincronizzare istantaneamente i comandi slash in un singolo server |
| `PLEXCORD_ACTIVITY_PORT` | *(Opzionale)* Porta del server HTTP/WebSocket dell'Activity (predefinito: `8080`, `0` per disabilitare) |
| `PLEXCORD_ACTIVITY_URL` | *(Opzionale)* URL pubblico HTTPS dell'Activity/Web Player |
| `DISCORD_CLIENT_SECRET` | *(Opzionale)* Client Secret OAuth2 dell'app Discord per abilitare il Discord Rich Presence (RPC) personale (configurabile anche direttamente dentro l'Activity) |

Avvia il container:

```sh
docker compose up -d --build
docker compose logs -f
```

---

## 3. Configura tutto da Discord (Comandi o Activity)

Puoi configurare il server Plex sia tramite i comandi `/plex` (serve il permesso **Gestisci server**) sia direttamente dalla scheda **`⚙️ Config`** dentro la Discord Activity:

1. **Collegamento Server Plex**:
   - **Dall'Activity**: apri la scheda **⚙️ Config**, clicca **🔑 Collega con PIN a 4 Cifre**, copia il codice e incollalo su **https://plex.tv/link** (verifica automatica ogni 3 secondi).
   - **Dai Comandi**: esegui `/plex login`, autorizza nel browser e premi **Completa login**.
2. **Scelta del Server**:
   - **Dall'Activity**: clicca **🔄 Carica Server**, scegli il server dal menu a tendina e premi **✅ Connetti**.
   - **Dai Comandi**: usa `/plex servers` e `/plex server id:ID_SERVER` (con autocompletamento).
3. **Librerie musicali**: tutte le librerie musicali vengono abilitate automaticamente; puoi abilitarle o disabilitarle singolarmente da **⚙️ Config** o con `/plex library`.

### Indirizzo Plex manuale

Se il rilevamento automatico non trova una connessione raggiungibile dal container:

```text
/plex address url:http://192.168.1.20:32400
/plex server id:ID_SERVER
```

- `localhost` nel container indica **il container stesso**, non il PC o il NAS.
- Su Docker Desktop, Plex sul PC host può essere raggiungibile tramite `http://host.docker.internal:32400`.
- L'URL deve corrispondere al server Plex scelto: il bot verifica il `machineIdentifier` prima di salvare la connessione.

---

## 4. Discord Activity (Embedded App SDK), RPC Utente e Playlist

### Configurazione dell'Activity nel Discord Developer Portal
1. Esponi in HTTPS la porta `8080` del container (ad es. tramite reverse proxy o Cloudflare Tunnel).
2. Nel [Discord Developer Portal](https://discord.com/developers/applications) della tua applicazione, apri **Activities → Settings** e abilita **Enable Activities**.
3. In **Activities → URL Mappings**, imposta il prefisso `/` verso il tuo dominio HTTPS.
4. *(Per il Discord Rich Presence personale)* In **OAuth2**:
   - Aggiungi un **Redirect URL** (es. `https://127.0.0.1`).
   - Copia il **Client Secret** e incollalo nella scheda **`🎧 RPC & Account`** dell'Activity (oppure in `DISCORD_CLIENT_SECRET` nel file `.env`).
5. Nel canale vocale avvia l'Activity cliccando sull'icona del razzo 🚀 (**Avvia attività**) o usando `/activity`.

### Collegamento Account Personale Plex e Playlist (`🎶 Playlist`)
Ogni ascoltatore può collegare il proprio account Plex personale:
1. Nella scheda **`🎧 RPC & Account`** dell'Activity (oppure eseguendo `/link`), genera il **codice PIN a 4 caratteri** e inseriscilo su **https://plex.tv/link**.
2. Una volta collegato:
   - La tua riproduzione su Discord apparirà in tempo reale sulla **Dashboard di Plex** con il tuo nome utente.
   - Nella scheda **`🎶 Playlist`** dell'Activity (o con il comando `/playlist`) vedrai tutte le **tue playlist audio personali**, potrai aprirle per sfogliare i brani con copertina oppure riprodurle subito (`▶️ Ora`, `🔀 Shuffle`, `➕ Coda`).

---

## 5. Elenco Comandi Slash

| Comando | Funzione |
| --- | --- |
| `/mode [modalita]` | Passa tra la **Modalità Activity** (`activity`) e la **Modalità Comandi Slash** (`commands`) |
| `/activity` | Avvia la Discord Activity nel canale vocale o apre il Web Player interattivo |
| `/play query [library]` | Cerca un brano per titolo o autore (con autocompletamento) e lo mette in coda |
| `/playlist [id] [shuffle]` | Mostra e riproduce le playlist personali del tuo account Plex collegato |
| `/link` | Collega il tuo account Plex personale a Discord tramite codice a 4 cifre (`plex.tv/link`) |
| `/unlink` | Scollega il tuo account Plex personale dal tuo profilo Discord |
| `/queue [page]` | Mostra il brano attuale, la coda (10 brani per pagina) e i pulsanti del player |
| `/now` | Mostra il brano in corso, il progresso e i pulsanti di controllo |
| `/pause`, `/resume`, `/skip` | Controlli rapidi del brano in riproduzione |
| `/shuffle` | Mescola i brani in attesa nella coda |
| `/stop` | Ferma la riproduzione e svuota la coda |
| `/leave` | Ferma la riproduzione, svuota la coda ed esce subito dal canale vocale |
| `/plex login`, `/plex logout` | Autorizzazione o rimozione dell'account Plex del server |
| `/plex servers`, `/plex server id` | Elenco e selezione del server Plex (con autocompletamento) |
| `/plex address [url]` | Imposta un indirizzo manuale LAN/Docker o ripristina il rilevamento automatico |
| `/plex libraries`, `/plex library`, `/plex all` | Gestione delle librerie musicali abilitate |
| `/settings [volume] [bitrate] [idle_seconds] [max_queue]` | Mostra o modifica volume (applicato istantaneamente), qualità Opus, timeout e limite coda |
| `/help` | Guida rapida a tutti i comandi |

Valori predefiniti: volume **100%** (modificabile da `0%` a `150%` in tempo reale senza interrompere il brano), Opus **128 kbps**, timeout a coda vuota **120 s**, massimo **100** brani in attesa.

---

## Persistenza e Sicurezza

- Il volume Docker `plexcord-data` conserva impostazioni, collegamenti utenti e token in SQLite (`/app/data/plexcord.db`). Proteggi host, volume e backup.
- Non vengono mai conservate password Plex. Token e URL interni dei file audio non vengono mai mostrati nei messaggi Discord né esposti al browser; le copertine vengono servite tramite proxy dal bot e FFmpeg riceve il token tramite header HTTP.
- Usa il bot soltanto per contenuti che hai diritto di riprodurre/condividere.

---

## Gestione e Sviluppo

```sh
# Ricostruisci e avvia con Docker
docker compose up -d --build

# Riavvia o ferma
docker compose restart
docker compose down

# Monitora risorse
docker stats
```

### Esecuzione test automatici (senza Docker)

```sh
python -m venv .venv
# Attiva l'ambiente virtuale
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Per indicazioni sull'architettura interna e lo sviluppo assistito da AI, consulta [`AGENTS.md`](AGENTS.md).
