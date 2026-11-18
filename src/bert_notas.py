"""Estimativa opcional das notas por competência com um BERTimbau ajustado.

O modo BERT é ligado e desligado na tela de Configurações. Este módulo informa se
ele pode ser usado (checkpoint ajustado + dependências) e faz a estimativa das
notas. A pasta padrão é ``modelos/bertimbau_enem`` na raiz do projeto; ``BERT_DIR``
pode apontar para outro checkout. ``torch`` e ``transformers`` só são importados
quando o modelo é realmente carregado.
"""
from __future__ import annotations

import importlib.util
import json
import os
import threading
from pathlib import Path

from . import paths

COMPETENCIAS = ["C1", "C2", "C3", "C4", "C5"]
MAX_TOKENS = 512

_trava = threading.Lock()  # uma estimativa por vez, mesmo com correções paralelas
_modelo = None
_tokenizador = None
_ordem = list(range(5))


def _pasta() -> Path:
    env_dir = os.environ.get("BERT_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return paths.BERT_DIR


def _config() -> dict | None:
    try:
        data = json.loads((_pasta() / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _rotulos_validos(config: dict) -> bool:
    labels = config.get("id2label") or {}
    if not isinstance(labels, dict):
        return False
    valores = {str(valor).strip().upper() for valor in labels.values()}
    return len(labels) == 5 and set(COMPETENCIAS).issubset(valores)


def _rotulos_padrao(config: dict) -> bool:
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


def _ajustado() -> bool:
    """True se o checkpoint tem a cabeça de classificação treinada com 5 notas."""
    config = _config()
    if config is None:
        return False
    arquiteturas = " ".join(str(item) for item in config.get("architectures", []))
    if "SequenceClassification" not in arquiteturas:
        return False
    if _rotulos_validos(config) or _rotulos_padrao(config):
        return True
    labels = config.get("id2label") or {}
    return not labels and config.get("num_labels") == 5


def motivo_indisponivel() -> str | None:
    """Explica por que o modo BERT não pode ser usado, ou None se está pronto."""
    pasta = _pasta()
    if not pasta.is_dir():
        return "a pasta do modelo não foi encontrada (veja a seção Modo BERT do README)."
    config = _config()
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
    if not _ajustado():
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


def _mapear_rotulos(modelo) -> list[int]:
    labels = getattr(modelo.config, "id2label", None) or {}
    por_nome: dict[str, int] = {}
    for chave, valor in labels.items():
        nome = str(valor).strip().upper()
        if nome in COMPETENCIAS:
            try:
                por_nome[nome] = int(chave)
            except (TypeError, ValueError):
                continue
    if len(por_nome) == 5:
        return [por_nome[nome] for nome in COMPETENCIAS]
    if labels and not _rotulos_padrao({"id2label": labels}):
        raise RuntimeError(
            "O id2label do checkpoint não corresponde a C1–C5; "
            "não é possível mapear as notas com segurança."
        )
    # Checkpoints antigos sem id2label (ou com LABEL_0..4) são treinados na
    # ordem C1..C5.
    return list(range(5))


def _carregar():
    global _modelo, _tokenizador, _ordem
    if _modelo is None:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        _tokenizador = AutoTokenizer.from_pretrained(_pasta())
        modelo, info = AutoModelForSequenceClassification.from_pretrained(
            _pasta(), output_loading_info=True
        )
        faltando = [
            chave for chave in info["missing_keys"] if "classifier" in chave
        ]
        if faltando:
            _modelo = None
            raise RuntimeError(
                "O checkpoint não tem a cabeça de classificação treinada "
                f"({', '.join(faltando)}). Use o modelo ajustado, não o BERTimbau base."
            )
        num_labels = getattr(modelo.config, "num_labels", None)
        classificador = getattr(modelo, "classifier", None)
        out_features = getattr(classificador, "out_features", None)
        if num_labels != 5 or out_features != 5:
            _modelo = None
            raise RuntimeError(
                "O checkpoint precisa de 5 saídas (C1 a C5); "
                f"encontrei num_labels={num_labels!r}, out_features={out_features!r}."
            )
        _ordem = _mapear_rotulos(modelo)
        modelo.eval()
        _modelo = modelo
    return _tokenizador, _modelo


def estimar(texto: str) -> tuple[dict[str, int], bool]:
    """Devolve ({'C1': 120, ...}, True se o texto passou de 512 pedaços)."""
    if not texto or not texto.strip():
        raise ValueError("A redação está vazia.")
    import numpy as np
    import torch

    with _trava:
        tokenizador, modelo = _carregar()
        cortada = len(tokenizador.encode(texto)) > MAX_TOKENS
        entrada = tokenizador(
            texto, truncation=True, max_length=MAX_TOKENS, return_tensors="pt"
        )
        with torch.no_grad():
            bruto = modelo(**entrada).logits[0].detach().cpu().numpy()
        if bruto.shape[0] != 5:
            raise RuntimeError(
                f"O modelo devolveu {bruto.shape[0]} notas; esperava 5 (C1 a C5)."
            )
        bruto = bruto[_ordem] * 200
    notas = np.clip(np.round(bruto / 40) * 40, 0, 200).astype(int)
    return dict(zip(COMPETENCIAS, notas.tolist())), cortada

#baixar modelo do bert

def baixar_modelo() -> None:
    from pathlib import Path
    from huggingface_hub import snapshot_download

    pasta_destino = Path(__file__).resolve().parent.parent / "modelos" / "bertimbau_enem"
    pasta_destino.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id="https://huggingface.co/berghilde/bertimbau-enem-notas/tree/main",
        local_dir=str(pasta_destino),
    )