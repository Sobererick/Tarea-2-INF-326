"""Equivalencias persistentes compartidas por las dos implementaciones HTTP."""
import os
import sqlite3
import string
from contextlib import closing
from pathlib import Path

FIRST_ID = 597_652_313
ALPHABET = string.digits + string.ascii_uppercase + string.ascii_lowercase


def links_db_path() -> str:
    return os.getenv("LINKS_DB", f"data/v{os.getenv('VERSION', '1')}.db")


def base62(number: int) -> str:
    digits = []
    while number:
        number, digit = divmod(number, 62)
        digits.append(ALPHABET[digit])
    return "".join(reversed(digits)) or "0"


class Links:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""
                CREATE TABLE IF NOT EXISTS links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash TEXT NOT NULL UNIQUE,
                    long_url TEXT NOT NULL
                )
            """)

    def create(self, long_url: str) -> str:
        with closing(sqlite3.connect(self.path)) as db, db:
            # Reservar el escritor antes de consultar el último ID asignado.
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT seq FROM sqlite_sequence WHERE name='links'").fetchone()
            next_id = row[0] + 1 if row else FIRST_ID
            code = base62(next_id)
            db.execute("INSERT INTO links VALUES (?, ?, ?)", (next_id, code, long_url))
            return code

    def resolve(self, code: str) -> str | None:
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute("SELECT long_url FROM links WHERE hash=?", (code,)).fetchone()
        return row[0] if row else None
