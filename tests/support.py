"""Apoio comum aos testes."""
from __future__ import annotations

import re

from src import db, paths


def reset() -> None:
    db.init_db()
    db.execute("DELETE FROM corrections")
    db.execute("DELETE FROM settings")
    db.init_db()
    for path in paths.UPLOAD_DIR.glob("*"):
        if path.is_file():
            path.unlink(missing_ok=True)


def configure_models(model: str = "fake") -> None:
    db.save_settings(
        {
            "base_url": "http://localhost:11434/v1",
            "correction_model": model,
            "image_model": model,
            "models": "[]",
            "use_bert": "0",
        }
    )


def csrf(client, path: str = "/config") -> str:
    response = client.get(path)
    html = response.get_data(as_text=True)
    match = re.search(r'name="_csrf_token" value="([^"]+)"', html)
    assert match, f"CSRF token não encontrado em {path}"
    return match.group(1)
