"""Repositório de correções: CRUD, paginação, estados e serialização."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from .connection import execute, execute_rowcount, now_timestamps, query

SCORE_COLUMNS = ("C1", "C2", "C3", "C4", "C5")
STATUSES = ("pendente", "corrigindo", "corrigido", "erro", "interrompido")
INTERRUPTED_MESSAGE = (
    "Correção interrompida por reinício do app. Use “Tentar novamente”."
)
PER_PAGE = 20


def recover_interrupted() -> int:
    """Marca jobs que ficaram em execução quando o processo morreu."""
    _, iso = now_timestamps()
    return execute_rowcount(
        "UPDATE corrections SET status = 'interrompido', updated_at = ?,"
        " errors = CASE WHEN errors = '' THEN ? ELSE errors END"
        " WHERE status = 'corrigindo'",
        (iso, INTERRUPTED_MESSAGE),
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
    display, iso = now_timestamps()
    return execute(
        "INSERT INTO corrections"
        " (filename, stored_name, theme, created_at, created_at_iso, status,"
        "  updated_at)"
        " VALUES (?, ?, ?, ?, ?, 'corrigindo', ?)",
        (filename, stored_name, theme, display, iso, iso),
    )


def mark_running(correction_id: int) -> bool:
    """Coloca a correção em execução e limpa o resultado anterior."""
    _, iso = now_timestamps()
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
    _, iso = now_timestamps()
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
    _, iso = now_timestamps()
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
