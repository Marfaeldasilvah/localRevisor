"""Criação do schema SQLite e migrações idempotentes."""
from __future__ import annotations

import sqlite3
from contextlib import closing

from .. import paths
from .connection import connect
from .corrections import recover_interrupted
from .settings import DEFAULT_SETTINGS

# Colunas adicionadas depois da primeira versão. A migração é idempotente.
_EXTRA_COLUMNS = (
    ("status", "TEXT NOT NULL DEFAULT 'pendente'"),
    ("note", "TEXT NOT NULL DEFAULT ''"),
    ("explanation", "TEXT NOT NULL DEFAULT ''"),
    ("errors", "TEXT NOT NULL DEFAULT ''"),
    ("scores", "TEXT NOT NULL DEFAULT '{}'"),
    ("source_text", "TEXT NOT NULL DEFAULT ''"),
    ("score_mode", "TEXT NOT NULL DEFAULT ''"),
    ("model", "TEXT NOT NULL DEFAULT ''"),
    ("provider", "TEXT NOT NULL DEFAULT ''"),
    ("prompt_version", "TEXT NOT NULL DEFAULT ''"),
    ("duration_ms", "INTEGER NOT NULL DEFAULT 0"),
    ("tokens_in", "INTEGER NOT NULL DEFAULT 0"),
    ("tokens_out", "INTEGER NOT NULL DEFAULT 0"),
    ("truncated", "INTEGER NOT NULL DEFAULT 0"),
    ("note_value", "INTEGER"),
    ("created_at_iso", "TEXT NOT NULL DEFAULT ''"),
    ("updated_at", "TEXT NOT NULL DEFAULT ''"),
)


def init_db() -> None:
    """Cria o banco, aplica migrações e recupera jobs deixados como 'corrigindo'."""
    paths.ensure_dirs()
    with closing(connect()) as conn, conn:
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:
            # Bancos antigos/read-only ainda devem abrir; o app avisa no log.
            pass
        conn.execute(
            "CREATE TABLE IF NOT EXISTS settings ("
            "key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS corrections ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "filename TEXT NOT NULL,"
            "stored_name TEXT NOT NULL,"
            "theme TEXT NOT NULL,"
            "created_at TEXT NOT NULL,"
            "status TEXT NOT NULL DEFAULT 'pendente',"
            "note TEXT NOT NULL DEFAULT '',"
            "explanation TEXT NOT NULL DEFAULT '',"
            "errors TEXT NOT NULL DEFAULT '')"
        )
        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(corrections)")
        }
        for name, definition in _EXTRA_COLUMNS:
            if name not in columns:
                conn.execute(
                    f"ALTER TABLE corrections ADD COLUMN {name} {definition}"
                )
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
        # A versão antiga guardava a chave (e depois só um hash) no banco.
        conn.execute(
            "DELETE FROM settings WHERE key IN ('api_key', 'api_key_hash')"
        )
        conn.execute(
            "UPDATE corrections SET note_value = CAST(note AS INTEGER)"
            " WHERE note_value IS NULL AND TRIM(note) <> ''"
            " AND CAST(note AS INTEGER) > 0"
        )
        conn.execute(
            "UPDATE corrections SET created_at_iso = created_at"
            " WHERE created_at_iso = ''"
        )
    recover_interrupted()
