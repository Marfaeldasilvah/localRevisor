"""Carregamento lazy e inferência thread-safe com BERTimbau."""
from __future__ import annotations

import threading

from .validation import COMPETENCIAS, pasta, rotulos_padrao

MAX_TOKENS = 512

_trava = threading.Lock()  # uma estimativa por vez, mesmo com correções paralelas
_modelo = None
_tokenizador = None
_ordem = list(range(5))


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
    if labels and not rotulos_padrao({"id2label": labels}):
        raise RuntimeError(
            "O id2label do checkpoint não corresponde a C1–C5; "
            "não é possível mapear as notas com segurança."
        )
    # Checkpoints antigos sem id2label (ou com LABEL_0..4) são treinados na ordem C1..C5.
    return list(range(5))


def _carregar():
    global _modelo, _tokenizador, _ordem
    if _modelo is None:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        diretorio = pasta()
        _tokenizador = AutoTokenizer.from_pretrained(diretorio)
        modelo, info = AutoModelForSequenceClassification.from_pretrained(
            diretorio, output_loading_info=True
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
