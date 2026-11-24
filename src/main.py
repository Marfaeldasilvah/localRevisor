"""Ponto de entrada Flask do localRevisor."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

if __package__ in (None, ""):
    _root = str(Path(__file__).resolve().parent.parent)
    if _root not in sys.path:
        sys.path.insert(0, _root)
    __package__ = "src"

from . import paths  # noqa: E402

load_dotenv(paths.ENV_PATH)

from . import bert_notas, db, grading, secrets_store, worker  # noqa: E402
from .web import create_app  # noqa: E402
from .web.feedback import (  # noqa: E402
    FEEDBACK_RATE_LIMIT,
    FEEDBACK_RATE_LOCK,
    send_feedback_email as _send_feedback_email,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
LOGGER = logging.getLogger(__name__)


def _normalize_startup_settings() -> None:
    """Desliga o BERT se o banco antigo o deixou ligado sem checkpoint válido."""
    settings = db.get_settings()
    if settings.get("use_bert") == "1" and not bert_notas.instalado():
        settings["use_bert"] = "0"
        db.save_settings(settings)
        LOGGER.warning("Modo BERT desligado no banco: checkpoint/dependências ausentes.")


db.init_db()
_normalize_startup_settings()

app = create_app(
    send_feedback=lambda name, email, message: _send_feedback_email(name, email, message)
)

__all__ = [
    "FEEDBACK_RATE_LIMIT",
    "FEEDBACK_RATE_LOCK",
    "_send_feedback_email",
    "app",
    "create_app",
    "grading",
    "secrets_store",
    "worker",
]


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
