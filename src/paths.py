"""Caminhos e limites do app, configuráveis por variáveis de ambiente.

Os testes chamam ``configure()`` para apontar tudo para um diretório temporário.
O app normal usa os padrões da raiz do projeto.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Carrega o .env antes de calcular os caminhos, para que LOCALREVISOR_* e
# BERT_DIR definidos nele também valham. main.py recarrega depois por segurança.
try:
    from dotenv import load_dotenv

    _env_file = os.environ.get("LOCALREVISOR_ENV_PATH")
    load_dotenv(_env_file or (BASE_DIR / ".env"), override=False)
except Exception:  # dotenv ausente ou .env inválido não deve derrubar o app
    pass


def _path_env(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser().resolve() if value else default


def _int_env(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default


DATA_DIR = _path_env("LOCALREVISOR_DATA_DIR", BASE_DIR / "data")
UPLOAD_DIR = _path_env("LOCALREVISOR_UPLOAD_DIR", DATA_DIR / "uploads")
DB_PATH = _path_env("LOCALREVISOR_DB_PATH", DATA_DIR / "app.db")
ENV_PATH = _path_env("LOCALREVISOR_ENV_PATH", BASE_DIR / ".env")
BERT_DIR = _path_env("BERT_DIR", BASE_DIR / "modelos" / "bertimbau_enem")
SECRET_PATH = DATA_DIR / ".secret"

# 20 MB é suficiente para uma redação escaneada; evita upload ilimitado.
MAX_UPLOAD_BYTES = _int_env("LOCALREVISOR_MAX_UPLOAD_BYTES", 20 * 1024 * 1024)


def configure(
    data_dir: str | Path | None = None,
    *,
    env_path: str | Path | None = None,
    upload_dir: str | Path | None = None,
    db_path: str | Path | None = None,
    bert_dir: str | Path | None = None,
) -> None:
    """Reaponta os caminhos globais. Usado pelos testes e por deploys alternativos."""
    global DATA_DIR, UPLOAD_DIR, DB_PATH, ENV_PATH, BERT_DIR, SECRET_PATH

    if data_dir is not None:
        DATA_DIR = Path(data_dir).expanduser().resolve()
        UPLOAD_DIR = DATA_DIR / "uploads"
        DB_PATH = DATA_DIR / "app.db"
        SECRET_PATH = DATA_DIR / ".secret"
    if upload_dir is not None:
        UPLOAD_DIR = Path(upload_dir).expanduser().resolve()
    if db_path is not None:
        DB_PATH = Path(db_path).expanduser().resolve()
    if env_path is not None:
        ENV_PATH = Path(env_path).expanduser().resolve()
    if bert_dir is not None:
        BERT_DIR = Path(bert_dir).expanduser().resolve()


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Diretório 700: outras contas do sistema não leem redações/banco/segredo.
    for directory in (DATA_DIR, UPLOAD_DIR):
        try:
            os.chmod(directory, 0o700)
        except OSError:
            pass
