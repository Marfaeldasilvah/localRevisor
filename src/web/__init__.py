"""App factory Flask do localRevisor."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from flask import Flask

from .. import paths, secrets_store
from . import feedback, routes_config, routes_corrections, security

SRC_DIR = Path(__file__).resolve().parent.parent


def create_app(
    *,
    send_feedback: Callable[[str, str, str], None] | None = None,
) -> Flask:
    app = Flask(
        "src.main",
        template_folder=str(SRC_DIR / "templates"),
        static_folder=str(SRC_DIR / "static"),
    )
    app.config.update(
        MAX_CONTENT_LENGTH=paths.MAX_UPLOAD_BYTES,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        TRUSTED_HOSTS=["localhost", "127.0.0.1", "::1", "[::1]"],
    )
    app.secret_key = secrets_store.load_or_create_secret()

    security.register(app)
    routes_corrections.register(app)
    routes_config.register(app)
    feedback.register(app, send_email=send_feedback)
    return app
