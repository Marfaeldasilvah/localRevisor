"""Conexão SQLite e utilitários de consulta."""
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from typing import Any, Iterable

from .. import paths


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(paths.DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def query(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    with closing(connect()) as conn:
        return conn.execute(sql, tuple(params)).fetchall()


def execute(sql: str, params: Iterable[Any] = ()) -> int:
    with closing(connect()) as conn, conn:
        return conn.execute(sql, tuple(params)).lastrowid


def execute_rowcount(sql: str, params: Iterable[Any] = ()) -> int:
    with closing(connect()) as conn, conn:
        return conn.execute(sql, tuple(params)).rowcount


def now_timestamps() -> tuple[str, str]:
    now = datetime.now().astimezone()
    return now.strftime("%d/%m/%Y %H:%M"), now.isoformat(timespec="seconds")
