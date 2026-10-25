# Plexcord

Bot Discord leggero per ascoltare i brani del proprio server Plex nei canali vocali. **Login, scelta del server, librerie e impostazioni si gestiscono da Discord**. All'avvio serve soltanto il token del bot Discord.

## Funzionalità

- Comandi slash e messaggi di configurazione privati (ephemeral).
- Login Plex tramite link ufficiale e pulsante di conferma: nessuna password inserita in Discord. Compatibile con il login/2FA gestito dal sito Plex.
- Scelta di un server Plex tra quelli accessibili all'account, anche condivisi.
- Ricerca contemporanea in tutte le librerie musicali abilitate, oppure in una sola. Confronto normalizzato di accenti/apostrofi, priorità ai titoli esatti e menu paginato. Ogni risultato indica la libreria di origine.
- Coda, pausa, ripresa, salto, mescolamento, stato e disconnessione automatica a coda vuota.
- Volume, bitrate Opus, timeout, limite coda e ruolo DJ configurabili con `/settings`.
- Configurazione persistente SQLite, separata per ogni server Discord.
- Docker Compose, processo non-root, filesystem read-only e volume persistente.
- Supporto vocale Discord/DAVE tramite `discord.py[voice]` 2.7.1 o superiore.

Nessun Lavalink, Redis, server web o database esterno. Un processo FFmpeg per riproduzione attiva; niente download dei brani su disco né indicizzazione completa delle librerie. Il consumo effettivo dipende da formato dei file, hardware e numero di riproduzioni simultanee: misuralo con `docker stats`.

## 1. Crea il bot Discord

1. Apri il [Discord Developer Portal](https://discord.com/developers/applications), crea un'applicazione e vai su **Bot**.
2. Genera/copia il token. **Non pubblicarlo e non inserirlo in un comando Discord.**
3. In **OAuth2 → URL Generator**, seleziona gli scope `bot` e `applications.commands`.
4. Permessi del bot: **View Channels**, **Send Messages**, **Connect**, **Speak**. Non serve Administrator.
5. Apri il link generato e invita il bot nel tuo server. Controlla anche gli override dei permessi nei canali.

Non servono intent privilegiati: **Message Content**, **Server Members** e **Presence** possono restare disabilitati. Chi usa i comandi deve poter usare i comandi delle applicazioni nel canale.

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

Modifica `.env` e imposta `DISCORD_TOKEN`. Facoltativamente inserisci `DISCORD_GUILD_ID` per pubblicare subito i comandi in un solo server di sviluppo. Trovi l'ID attivando la modalità sviluppatore Discord e facendo clic destro sul server → Copia ID.

```sh
docker compose up -d --build
docker compose logs -f
```

Non devi esporre porte del container: le connessioni sono in uscita. Consenti HTTPS verso Discord e Plex.tv, accesso al server Plex e traffico UDP in uscita per la voce Discord.

Senza `DISCORD_GUILD_ID` i comandi vengono pubblicati globalmente e possono impiegare tempo a comparire. Per cambiare modalità di pubblicazione in un bot già utilizzato, considera che i vecchi comandi globali/per-server possono rimanere registrati: non vengono cancellati automaticamente.

## 3. Configura tutto da Discord

Per `/plex` e `/settings` serve **Gestisci server**.

1. `/plex login`: premi **Autorizza su Plex**, accedi nel browser e autorizza Plexcord. Torna su Discord e premi **Completa login** prima della scadenza.
2. `/plex servers`: mostra i server e gli ID.
3. `/plex server id:ID_SERVER`: verifica la connessione e seleziona il server. Tutte le librerie musicali vengono abilitate.
4. `/plex libraries`: mostra nome, ID e stato delle librerie.
5. Entra in un normale canale vocale e usa `/play query:titolo o autore`.

Se ci sono più risultati, scegli dal menu privato. Usa **Avanti/Indietro** per scorrere pagine da 25 brani. Il menu dura 3 minuti; puoi restringere la ricerca passando `library:ID_LIBRERIA`. La ricerca è per **titolo del brano o nome dell'autore**, con un massimo di 200 risultati distribuiti tra le librerie e i titoli esatti in cima. Se la frase non trova un titolo esatto, il bot prova poche parole del titolo o dell'autore e confronta i candidati ignorando accenti, apostrofi, separatori e piccoli errori di battitura. Le ricerche rimangono limitate per evitare scansioni complete delle librerie: se manca un risultato, specifica un titolo più preciso e la libreria. Non carica automaticamente album o playlist.

Prima di avviare la voce, il bot verifica che FFmpeg produca audio e seleziona esplicitamente la traccia audio (non la copertina incorporata). Se Plex contiene più versioni dello stesso brano, ignora quelle dichiarate non accessibili e prova le altre in caso di errore iniziale. Non riparte dall'inizio su un'altra versione se la riproduzione si interrompe a metà. I file realmente mancanti, corrotti o in un formato non decodificabile vanno comunque corretti sul server Plex.

### Più librerie musicali

```text
/plex libraries
/play query:Imagine
/play query:Imagine library:2
/plex library id:2 enabled:False
/plex library id:2 enabled:True
/plex all
```

Senza `library`, `/play` cerca in tutte le librerie abilitate. `/plex all` include automaticamente anche future librerie musicali. Quando personalizzi l'elenco con `/plex library`, nuove librerie non vengono incluse finché non le abiliti o ripristini `/plex all`.

Cambiare login, server, indirizzo o abilitazione di una libreria interrompe la riproduzione e svuota la coda, per non conservare brani di una configurazione precedente. La selezione di un server nuovo ripristina tutte le librerie.

### Indirizzo Plex manuale

Se il rilevamento automatico non trova una connessione raggiungibile dal container:

```text
/plex address url:http://192.168.1.20:32400
/plex server id:ID_SERVER
```

Puoi impostare l'indirizzo anche prima di scegliere il server. Senza `url`, `/plex address` ripristina il rilevamento automatico.

- `localhost` nel container indica **il container stesso**, non il PC o il NAS.
- Su Docker Desktop, Plex sul PC host può essere raggiungibile tramite `http://host.docker.internal:32400`.
- Se Plex è un altro container, usa una rete Docker condivisa e il nome del servizio Plex.
- Sono accettati URL base HTTP/HTTPS senza credenziali, query o sottopercorsi. I reverse proxy devono esporre Plex alla radice.
- I certificati HTTPS sono verificati; per un certificato privato configura una CA attendibile, non disabilitare TLS.
- L'URL deve corrispondere al server Plex scelto: il bot verifica il `machineIdentifier` prima di salvare la connessione.
- HTTP è adatto solo a reti fidate: il token Plex viaggia nell'header della richiesta.

## Comandi

| Comando | Funzione |
| --- | --- |
| `/plex login` | Autorizzazione Plex |
| `/plex logout` | Ferma il player e rimuove le credenziali locali |
| `/plex servers` | Elenco dei server accessibili |
| `/plex server id` | Selezione del server Plex |
| `/plex address [url]` | Indirizzo manuale o automatico |
| `/plex libraries` | Elenco delle librerie musicali |
| `/plex library id enabled` | Abilita/disabilita una libreria |
| `/plex all` | Abilita tutte le librerie, presenti e future |
| `/settings` | Mostra la configurazione attuale |
| `/settings volume bitrate idle_seconds max_queue dj_role clear_dj` | Modifica solo le opzioni fornite |
| `/play query [library]` | Cerca un brano e lo mette in coda |
| `/queue [page]` | Coda, 10 brani per pagina |
| `/now` | Brano e progresso indicativo |
| `/pause`, `/resume`, `/skip` | Controlli del brano |
| `/shuffle` | Mescola solo i brani in attesa |
| `/stop` | Ferma e svuota la coda; esce dopo il timeout |
| `/leave` | Ferma, svuota ed esce subito |
| `/help` | Guida rapida |

Valori predefiniti: volume **100%**, Opus **128 kbps**, timeout a coda vuota **120 s**, massimo **100** brani in attesa. Volume e bitrate si applicano **dal prossimo brano**. Il timeout non interrompe un brano in pausa; usa `/stop` o `/leave`.

Chi controlla la musica deve essere nello stesso canale vocale del bot: **tutti gli utenti presenti nel canale vocale** possono riprodurre, scegliere i brani dal menu e controllare la riproduzione sia tramite i comandi slash sia tramite i **pulsanti interattivi del player** (`⏯️ Pausa/Riprendi`, `⏭️ Salta`, `🔀 Mescola`, `⏹️ Stop`, `👋 Esci`). `/queue` e `/now` sono consultabili anche fuori dal canale vocale.

## Persistenza e sicurezza

- Il volume Docker `plexcord-data` conserva impostazioni e token Plex in SQLite. **I token sono salvati in chiaro**, con permessi di file ristretti nel container: proteggi host, volume e backup. Non condividere il database.
- Non vengono conservate password Plex. Token e link dei file non vengono mostrati nei messaggi Discord; FFmpeg riceve il token tramite header HTTP. Un amministratore dell'host può comunque leggere memoria e argomenti dei processi.
- L'account Plex collegato è condiviso dal bot per **quel server Discord**, non per singolo ascoltatore. Abilita soltanto librerie che vuoi rendere disponibili agli utenti autorizzati.
- `/plex logout` elimina le credenziali locali; per revocare l'accesso sull'account rimuovi Plexcord dai dispositivi autorizzati su Plex. Non invalida automaticamente token usati altrove.
- Non pubblicare `.env`. Il token Discord resta fuori dal database.
- Coda e riproduzione sono in memoria e **non riprendono dopo un riavvio**; il login e le impostazioni rimangono.
- Un solo canale vocale e un solo server Plex selezionato per server Discord. Più server Discord possono avere configurazioni e player indipendenti.

Usa il bot soltanto per contenuti che hai diritto di riprodurre/condividere.

## Gestione

```sh
docker compose restart
docker compose down
docker compose up -d --build
docker stats
```

`docker compose down` conserva il volume. **Non usare `down -v`** se vuoi mantenere credenziali e configurazione. Per aggiornare le dipendenze e ricostruire da zero: `docker compose build --no-cache`, poi `docker compose up -d`.

### Problemi comuni

- **Comandi non visibili:** controlla scope `applications.commands`, server corretto, permessi applicazione e propagazione dei comandi globali.
- **Plex non raggiungibile:** imposta `/plex address` con un URL accessibile da Docker e controlla firewall, porta Plex e certificati. Se cambia l'IP del server, riselezionalo con `/plex server`.
- **Accesso Plex negato:** ripeti `/plex login` e `/plex server`; verifica che l'account abbia accesso alle librerie.
- **Connessione vocale fallita:** controlla Connect/Speak/View Channel e firewall UDP. I canali Stage non sono supportati.
- **Il brano non viene trovato:** prova il titolo presente nei metadati Plex (non necessariamente il nome del file), specifica la libreria e scorri le pagine dei risultati.
- **Il brano non parte:** verifica che il file sia online e accessibile tramite Plex e che FFmpeg supporti il formato. Il bot prova le versioni alternative disponibili prima di passare al prossimo brano; gli errori distinguono accesso negato, file non trovato, rete e decodifica senza esporre credenziali.

## Sviluppo e test senza Docker

Python 3.12+, FFmpeg nel PATH e dipendenze vocali. Il file `.env` viene letto da Compose, **non** dall'esecuzione Python diretta: esporta le variabili d'ambiente.

```sh
python -m venv .venv
# Attiva l'ambiente virtuale secondo il tuo sistema operativo.
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m plexcord
```

Esempio PowerShell prima dell'avvio diretto:

```powershell
$env:DISCORD_TOKEN = 'il_token_del_bot'
$env:DISCORD_GUILD_ID = 'id_del_server_di_test'
python -m plexcord
```

I test automatici usano HTTP locale e oggetti vocali simulati: non richiedono token reali. Se FFmpeg è nel PATH, eseguono anche una conversione audio HTTP → Opus reale; altrimenti quel test viene saltato. Non sostituiscono la verifica end-to-end su un server Plex e un canale vocale Discord reali.
