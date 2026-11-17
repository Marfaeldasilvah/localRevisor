"""Chave da API e segredo de sessão, sempre em arquivos locais com permissão restrita."""
from __future__ import annotations

import json
import os
import secrets
import tempfile
from pathlib import Path

from . import paths

KEY_NAME = "OPENAI_API_KEY"


def _read_lines() -> list[str]:
    try:
        return paths.ENV_PATH.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []


def _is_key_line(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].lstrip()
    return stripped.split("=", 1)[0].strip() == KEY_NAME


def _without_key(lines: list[str]) -> list[str]:
    return [line for line in lines if not _is_key_line(line)]


def _write_lines(lines: list[str]) -> None:
    """Escreve o .env de forma atômica, preservando as demais linhas."""
    paths.ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines).rstrip("\n")
    if text:
        text += "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=".env.", dir=str(paths.ENV_PATH.parent), text=True
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(tmp_path, 0o600)
        except OSError:
            pass
        os.replace(tmp_path, paths.ENV_PATH)
    finally:
        tmp_path.unlink(missing_ok=True)


def validate_key(key: str) -> str:
    key = (key or "").strip()
    if not key:
        raise ValueError("Informe a chave da API.")
    if len(key) > 4096:
        raise ValueError("A chave da API é longa demais.")
    if any(char.isspace() or ord(char) < 32 for char in key):
        raise ValueError("A chave da API não pode conter espaços ou quebras de linha.")
    return key


def save_api_key(key: str) -> tuple[bool, str]:
    """Grava a chave no .env e atualiza o processo.

    Devolve (persistiu_no_disco, aviso). Em Docker o .env pode ser efêmero; a
    chave continua valendo nesta execução, mas o aviso explica como persistir.
    """
    key = validate_key(key)
    os.environ[KEY_NAME] = key
    try:
        lines = _without_key(_read_lines())
        lines.append(f"{KEY_NAME}={json.dumps(key, ensure_ascii=False)}")
        _write_lines(lines)
    except OSError as exc:
        return False, (
            f"A chave vale nesta execução, mas não foi possível gravar o .env: {exc}"
        )
    if Path("/.dockerenv").exists():
        return True, (
            "Chave salva no .env do container. Para sobreviver a recriações, "
            "defina OPENAI_API_KEY no docker-compose/.env do host."
        )
    return True, "Chave salva em .env (permissão 600)."


def remove_api_key() -> tuple[bool, str]:
    os.environ.pop(KEY_NAME, None)
    try:
        _write_lines(_without_key(_read_lines()))
    except OSError as exc:
        return False, f"A chave foi removida desta execução, mas o .env não pôde ser atualizado: {exc}"
    return True, "Chave removida do .env e desta execução."


def key_configured() -> bool:
    return bool(os.environ.get(KEY_NAME, "").strip())


def load_or_create_secret() -> str:
    env_secret = os.environ.get("SECRET_KEY", "").strip()
    if env_secret:
        return env_secret
    try:
        existing = paths.SECRET_PATH.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    except FileNotFoundError:
        pass
    secret = secrets.token_hex(32)
    try:
        paths.SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=".secret.", dir=str(paths.SECRET_PATH.parent), text=True
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(secret)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.chmod(tmp_path, 0o600)
            except OSError:
                pass
            os.replace(tmp_path, paths.SECRET_PATH)
        finally:
            tmp_path.unlink(missing_ok=True)
    except OSError:
        # Sem persistência, as sessões duram só esta execução; o app continua.
        pass
    return secret
