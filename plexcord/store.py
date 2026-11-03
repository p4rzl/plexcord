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
    dj_only: bool = False
    language: str = "en"
    mode: str = "commands"
    revision: int = 0


@dataclass
class UserLink:
    discord_id: int
    plex_token: str = field(default="", repr=False)
    plex_username: str = ""
    discord_name: str = ""


class Store:
    def __init__(self, directory: str):
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path / "plexcord.sqlite3")
        os.chmod(path / "plexcord.sqlite3", 0o600)
        self.db.execute("PRAGMA secure_delete=ON")
        self.db.execute("CREATE TABLE IF NOT EXISTS settings (guild INTEGER PRIMARY KEY, data TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS user_links (discord_id INTEGER PRIMARY KEY, data TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        # Token OAuth2 Discord per singolo utente (Rich Presence). Mai esposti nei log.
        self.db.execute("CREATE TABLE IF NOT EXISTS discord_oauth (discord_id INTEGER PRIMARY KEY, data TEXT NOT NULL)")
        self.db.execute("INSERT OR IGNORE INTO meta VALUES ('client_id', ?)", (str(uuid.uuid4()),))
        self.db.commit()
        self.client_id = self.db.execute("SELECT value FROM meta WHERE key='client_id'").fetchone()[0]

    def get(self, guild: int) -> Settings:
        row = self.db.execute("SELECT data FROM settings WHERE guild=?", (guild,)).fetchone()
        if not row:
            return Settings()
        try:
            data = json.loads(row[0])
            fields = {f.name for f in Settings.__dataclass_fields__.values()}
            return Settings(**{k: v for k, v in data.items() if k in fields})
        except Exception:
            return Settings()

    def save(self, guild: int, settings: Settings):
        settings.revision += 1
        self.db.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (guild, json.dumps(asdict(settings))))
        self.db.commit()

    def get_user(self, discord_id: int) -> UserLink | None:
        row = self.db.execute("SELECT data FROM user_links WHERE discord_id=?", (discord_id,)).fetchone()
        return UserLink(**json.loads(row[0])) if row else None

    def save_user(self, link: UserLink):
        self.db.execute("INSERT OR REPLACE INTO user_links VALUES (?, ?)", (link.discord_id, json.dumps(asdict(link))))
        self.db.commit()

    def delete_user(self, discord_id: int):
        self.db.execute("DELETE FROM user_links WHERE discord_id=?", (discord_id,))
        self.db.commit()

    def list_users(self, discord_ids: list[int] | None = None) -> list[UserLink]:
        rows = self.db.execute("SELECT data FROM user_links").fetchall()
        links = [UserLink(**json.loads(r[0])) for r in rows]
        if discord_ids is not None:
            wanted = set(discord_ids)
            return [u for u in links if u.discord_id in wanted]
        return links

    def get_meta(self, key: str, default: str = "") -> str:
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_meta(self, key: str, value: str):
        self.db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))
        self.db.commit()

    def get_discord_oauth(self, discord_id: int) -> dict | None:
        row = self.db.execute("SELECT data FROM discord_oauth WHERE discord_id=?", (discord_id,)).fetchone()
        if not row:
            return None
        try:
            data = json.loads(row[0])
        except ValueError:
            return None
        return data if isinstance(data, dict) else None

    def save_discord_oauth(self, discord_id: int, data: dict):
        self.db.execute("INSERT OR REPLACE INTO discord_oauth VALUES (?, ?)", (discord_id, json.dumps(data)))
        self.db.commit()

    def delete_discord_oauth(self, discord_id: int):
        self.db.execute("DELETE FROM discord_oauth WHERE discord_id=?", (discord_id,))
        self.db.commit()

    def discord_oauth_ids(self, discord_ids: list[int] | None = None) -> list[int]:
        ids = [r[0] for r in self.db.execute("SELECT discord_id FROM discord_oauth").fetchall()]
        if discord_ids is not None:
            wanted = set(discord_ids)
            return [i for i in ids if i in wanted]
        return ids

    def close(self):
        self.db.close()
