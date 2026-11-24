"""Validação do checkpoint BERTimbau ajustado para as cinco competências."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

from .. import paths

COMPETENCIAS = ["C1", "C2", "C3", "C4", "C5"]


def pasta() -> Path:
    env_dir = os.environ.get("BERT_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return paths.BERT_DIR


def ler_config() -> dict | None:
    try:
        data = json.loads((pasta() / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def rotulos_validos(config: dict) -> bool:
    labels = config.get("id2label") or {}
    if not isinstance(labels, dict):
        return False
    valores = {str(valor).strip().upper() for valor in labels.values()}
    return len(labels) == 5 and set(COMPETENCIAS).issubset(valores)


def rotulos_padrao(config: dict) -> bool:
    """Aceita id2label LABEL_0..LABEL_4, comum quando o treino não renomeou."""
    labels = config.get("id2label") or {}
    if not isinstance(labels, dict) or len(labels) != 5:
        return False
    for chave, valor in labels.items():
        try:
            esperado = f"LABEL_{int(chave)}"
        except (TypeError, ValueError):
            return False
        if str(valor).strip().upper() != esperado:
            return False
    return True


def ajustado() -> bool:
    """True se o checkpoint tem a cabeça de classificação treinada com 5 notas."""
    config = ler_config()
    if config is None:
        return False
    arquiteturas = " ".join(str(item) for item in config.get("architectures", []))
    if "SequenceClassification" not in arquiteturas:
        return False
    if rotulos_validos(config) or rotulos_padrao(config):
        return True
    labels = config.get("id2label") or {}
    return not labels and config.get("num_labels") == 5


def motivo_indisponivel() -> str | None:
    """Explica por que o modo BERT não pode ser usado, ou None se está pronto."""
    diretorio = pasta()
    if not diretorio.is_dir():
        return "a pasta do modelo não foi encontrada (veja a seção Modo BERT do README)."
    config = ler_config()
    if config is None:
        return (
            "o config.json do checkpoint está ausente ou é inválido. "
            "Coloque o modelo ajustado em modelos/bertimbau_enem ou aponte BERT_DIR."
        )
    arquiteturas = " ".join(str(item) for item in config.get("architectures", []))
    if "SequenceClassification" not in arquiteturas:
        return (
            "o modelo encontrado é o BERTimbau base, sem a cabeça de classificação "
            "treinada (as notas seriam aleatórias). Use o checkpoint ajustado."
        )
    if not ajustado():
        return (
            "o checkpoint não declara 5 saídas (num_labels/id2label de C1 a C5). "
            "Use um modelo treinado para as cinco competências."
        )
    faltando = [
        nome
        for nome in ("torch", "transformers", "numpy")
        if importlib.util.find_spec(nome) is None
    ]
    if faltando:
        return (
            "faltam dependências ("
            + ", ".join(faltando)
            + "). Rode: pip install -r requirements-bert.txt"
        )
    return None


def instalado() -> bool:
    return motivo_indisponivel() is None
