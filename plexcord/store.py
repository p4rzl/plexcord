import json
import os
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Settings:
    token: str = field(default="", repr=False)
    server_token: str = field(default="", repr=False)
    server_id: str = ""
    server_name: str = ""
    server_url: str = ""
    address_override: str = ""
    libraries: list[str] | None = None  # None = tutte, [] = nessuna
    volume: int = 100
    bitrate: int = 128
    idle_seconds: int = 120
    max_queue: int = 100
    dj_role: int | None = None
    revision: int = 0


class Store:
    def __init__(self, directory: str):
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path / "plexcord.sqlite3")
        os.chmod(path / "plexcord.sqlite3", 0o600)
        self.db.execute("PRAGMA secure_delete=ON")
        self.db.execute("CREATE TABLE IF NOT EXISTS settings (guild INTEGER PRIMARY KEY, data TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self.db.execute("INSERT OR IGNORE INTO meta VALUES ('client_id', ?)", (str(uuid.uuid4()),))
        self.db.commit()
        self.client_id = self.db.execute("SELECT value FROM meta WHERE key='client_id'").fetchone()[0]

    def get(self, guild: int) -> Settings:
        row = self.db.execute("SELECT data FROM settings WHERE guild=?", (guild,)).fetchone()
        return Settings(**json.loads(row[0])) if row else Settings()

    def save(self, guild: int, settings: Settings):
        settings.revision += 1
        self.db.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (guild, json.dumps(asdict(settings))))
        self.db.commit()

    def close(self):
        self.db.close()
