"""Persistência local em SQLite: correções, configurações e migrações."""
from __future__ import annotations

from .connection import connect, execute, execute_rowcount, query
from .corrections import (
    INTERRUPTED_MESSAGE,
    PER_PAGE,
    SCORE_COLUMNS,
    STATUSES,
    create_correction,
    delete_correction,
    fail_correction,
    finish_correction,
    get_correction,
    mark_running,
    note_of,
    pending_count,
    recent_corrections,
    recover_interrupted,
    scores_of,
    to_dict,
)
from .schema import init_db
from .settings import DEFAULT_SETTINGS, get_settings, save_settings

__all__ = [
    "DEFAULT_SETTINGS",
    "INTERRUPTED_MESSAGE",
    "PER_PAGE",
    "SCORE_COLUMNS",
    "STATUSES",
    "connect",
    "create_correction",
    "delete_correction",
    "execute",
    "execute_rowcount",
    "fail_correction",
    "finish_correction",
    "get_correction",
    "get_settings",
    "init_db",
    "mark_running",
    "note_of",
    "pending_count",
    "query",
    "recent_corrections",
    "recover_interrupted",
    "save_settings",
    "scores_of",
    "to_dict",
]
