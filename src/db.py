"""Persistência local em SQLite: correções, configurações e migrações."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from typing import Any, Iterable

from . import paths

SCORE_COLUMNS = ("C1", "C2", "C3", "C4", "C5")
STATUSES = ("pendente", "corrigindo", "corrigido", "erro", "interrompido")
INTERRUPTED_MESSAGE = (
    "Correção interrompida por reinício do app. Use “Tentar novamente”."
)
DEFAULT_SETTINGS = {
    "base_url": "https://api.deepseek.com",
    "correction_model": "",
    "image_model": "",
    "models": "[]",
    "use_bert": "0",
}
PER_PAGE = 20

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


def _now() -> tuple[str, str]:
    now = datetime.now().astimezone()
    return now.strftime("%d/%m/%Y %H:%M"), now.isoformat(timespec="seconds")


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


def recover_interrupted() -> int:
    """Marca jobs que ficaram em execução quando o processo morreu."""
    display, iso = _now()
    return execute_rowcount(
        "UPDATE corrections SET status = 'interrompido', updated_at = ?,"
        " errors = CASE WHEN errors = '' THEN ? ELSE errors END"
        " WHERE status = 'corrigindo'",
        (iso, INTERRUPTED_MESSAGE),
    )


def get_settings() -> dict[str, str]:
    settings = dict(DEFAULT_SETTINGS)
    for row in query("SELECT key, value FROM settings"):
        settings[row["key"]] = row["value"]
    return settings


def save_settings(values: dict[str, str]) -> None:
    with closing(connect()) as conn, conn:
        conn.executemany(
            "INSERT INTO settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            [(key, str(value)) for key, value in values.items()],
        )


def recent_corrections(
    page: int = 1, per_page: int = PER_PAGE, status: str | None = None
) -> tuple[list[sqlite3.Row], int]:
    page = max(1, page)
    per_page = max(1, min(per_page, 100))
    where = ""
    params: list[Any] = []
    if status in STATUSES:
        where = " WHERE status = ?"
        params.append(status)
    total_row = query(f"SELECT COUNT(*) AS total FROM corrections{where}", params)
    total = int(total_row[0]["total"]) if total_row else 0
    rows = query(
        f"SELECT * FROM corrections{where} ORDER BY id DESC LIMIT ? OFFSET ?",
        [*params, per_page, (page - 1) * per_page],
    )
    return rows, total


def pending_count() -> int:
    rows = query(
        "SELECT COUNT(*) AS total FROM corrections WHERE status = 'corrigindo'"
    )
    return int(rows[0]["total"]) if rows else 0


def get_correction(correction_id: int) -> sqlite3.Row | None:
    rows = query("SELECT * FROM corrections WHERE id = ?", (correction_id,))
    return rows[0] if rows else None


def create_correction(filename: str, stored_name: str, theme: str) -> int:
    display, iso = _now()
    return execute(
        "INSERT INTO corrections"
        " (filename, stored_name, theme, created_at, created_at_iso, status,"
        "  updated_at)"
        " VALUES (?, ?, ?, ?, ?, 'corrigindo', ?)",
        (filename, stored_name, theme, display, iso, iso),
    )


def mark_running(correction_id: int) -> bool:
    """Coloca a correção em execução e limpa o resultado anterior."""
    display, iso = _now()
    changed = execute_rowcount(
        "UPDATE corrections SET status = 'corrigindo', note = '', note_value = NULL,"
        " scores = '{}', explanation = '', errors = '', source_text = '',"
        " score_mode = '', model = '', provider = '', prompt_version = '',"
        " duration_ms = 0, tokens_in = 0, tokens_out = 0, truncated = 0,"
        " updated_at = ? WHERE id = ? AND status <> 'corrigindo'",
        (iso, correction_id),
    )
    return changed > 0


def finish_correction(
    correction_id: int,
    *,
    note: int,
    scores: dict[str, int],
    explanation: str,
    errors: str,
    source_text: str,
    score_mode: str,
    model: str,
    provider: str,
    prompt_version: str,
    duration_ms: int,
    tokens_in: int,
    tokens_out: int,
    truncated: bool,
) -> None:
    _, iso = _now()
    execute(
        "UPDATE corrections SET status = 'corrigido', note = ?, note_value = ?,"
        " scores = ?, explanation = ?, errors = ?, source_text = ?,"
        " score_mode = ?, model = ?, provider = ?, prompt_version = ?,"
        " duration_ms = ?, tokens_in = ?, tokens_out = ?, truncated = ?,"
        " updated_at = ? WHERE id = ?",
        (
            str(note),
            int(note),
            json.dumps(scores, ensure_ascii=False),
            explanation,
            errors,
            source_text,
            score_mode,
            model,
            provider,
            prompt_version,
            int(duration_ms),
            int(tokens_in),
            int(tokens_out),
            1 if truncated else 0,
            iso,
            correction_id,
        ),
    )


def fail_correction(correction_id: int, message: str, code: str = "") -> None:
    _, iso = _now()
    execute(
        "UPDATE corrections SET status = 'erro', errors = ?, updated_at = ?"
        " WHERE id = ?",
        (message, iso, correction_id),
    )


def delete_correction(correction_id: int) -> str | None:
    rows = query(
        "SELECT stored_name FROM corrections WHERE id = ?", (correction_id,)
    )
    if not rows:
        return None
    execute("DELETE FROM corrections WHERE id = ?", (correction_id,))
    return str(rows[0]["stored_name"])


def scores_of(row: sqlite3.Row | dict[str, Any]) -> dict[str, int]:
    raw = row["scores"] if not isinstance(row, dict) else row.get("scores", "{}")
    try:
        data = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    result: dict[str, int] = {}
    for name in SCORE_COLUMNS:
        try:
            value = int(data.get(name))
        except (TypeError, ValueError):
            continue
        result[name] = max(0, min(200, value))
    return result


def note_of(row: sqlite3.Row | dict[str, Any]) -> int | None:
    value = row["note_value"] if not isinstance(row, dict) else row.get("note_value")
    if value is not None:
        try:
            return int(value)
        except (TypeError, ValueError):
            pass
    raw = row["note"] if not isinstance(row, dict) else row.get("note", "")
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


def to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["scores_dict"] = scores_of(row)
    data["note_display"] = note_of(row)
    return data
