"""Treino e previsão do BERTimbau (usado por treinar_bert.py e experimentos_bert.py).

Cada redação vira um texto de até 512 pedaços; o modelo prevê as 5 notas (de 0 a 1, depois
multiplicadas por 200) e as previsões são arredondadas para a faixa de 40 pontos mais próxima.
"""
import copy
import gc

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset
from tqdm.auto import tqdm
from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                          get_linear_schedule_with_warmup)

from metricas import COMPS, qwk_por_competencia

MODELO = "neuralmind/bert-base-portuguese-cased"  # BERTimbau
MAX_LEN, BATCH, LR = 512, 8, 2e-5
dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
USAR_AMP = dispositivo == "cuda"  # precisão mista só com GPU

_tokenizador = None


def tokenizador():
    global _tokenizador
    if _tokenizador is None:
        _tokenizador = AutoTokenizer.from_pretrained(MODELO)
    return _tokenizador


class Redacoes(Dataset):
    def __init__(self, df):
        self.enc = tokenizador()(df["texto"].tolist(), truncation=True, max_length=MAX_LEN)
        self.y = (df[COMPS].values / 200.0).astype("float32")  # notas de 0 a 1

    def __len__(self):
        return len(self.y)

    def __getitem__(self, i):
        item = {k: v[i] for k, v in self.enc.items()}
        item["labels"] = self.y[i]
        return item


def agrupar(lote):
    entradas = tokenizador().pad(
        [{k: v for k, v in x.items() if k != "labels"} for x in lote], return_tensors="pt")
    entradas["labels"] = torch.tensor(np.stack([x["labels"] for x in lote]))
    return entradas


@torch.no_grad()
def prever(modelo, df):
    """Notas previstas (matriz n x 5, múltiplos de 40 entre 0 e 200)."""
    modelo.eval()
    saidas = []
    for lote in DataLoader(Redacoes(df), batch_size=32, collate_fn=agrupar):
        lote = {k: v.to(dispositivo) for k, v in lote.items() if k != "labels"}
        with torch.autocast(device_type=dispositivo, dtype=torch.float16, enabled=USAR_AMP):
            saidas.append(modelo(**lote).logits.float().cpu().numpy())
    continuo = np.concatenate(saidas) * 200
    return np.clip(np.round(continuo / 40) * 40, 0, 200).astype(int)


def treinar(df_treino, semente, epocas=4, df_validacao=None):
    """Treina o BERTimbau.

    Sem df_validacao, devolve o modelo da última época. Com df_validacao, mede o QWK médio ao
    fim de cada época e devolve o modelo da melhor época. Devolve (modelo, histórico).
    """
    torch.manual_seed(semente)
    np.random.seed(semente)
    modelo = AutoModelForSequenceClassification.from_pretrained(
        MODELO, num_labels=5, problem_type="regression", use_safetensors=False
    ).to(dispositivo)
    dl = DataLoader(Redacoes(df_treino), batch_size=BATCH, shuffle=True, collate_fn=agrupar)
    total = len(dl) * epocas
    otimizador = torch.optim.AdamW(modelo.parameters(), lr=LR, weight_decay=0.01)
    agenda = get_linear_schedule_with_warmup(otimizador, int(0.1 * total), total)
    escala = torch.amp.GradScaler("cuda", enabled=USAR_AMP)

    melhor, melhores_pesos, historico = -1.0, None, []
    for epoca in range(epocas):
        modelo.train()
        soma = 0.0
        for lote in tqdm(dl, desc=f"Época {epoca + 1}/{epocas}", leave=False):
            lote = {k: v.to(dispositivo) for k, v in lote.items()}
            otimizador.zero_grad()
            with torch.autocast(device_type=dispositivo, dtype=torch.float16, enabled=USAR_AMP):
                perda = modelo(**lote).loss
            escala.scale(perda).backward()
            escala.unscale_(otimizador)
            torch.nn.utils.clip_grad_norm_(modelo.parameters(), 1.0)
            escala.step(otimizador)
            escala.update()
            agenda.step()
            soma += perda.item()
        linha = {"epoca": epoca + 1, "perda_treino": round(soma / len(dl), 4)}
        if df_validacao is not None:
            qwk = qwk_por_competencia(df_validacao[COMPS].values, prever(modelo, df_validacao)).mean()
            linha["qwk_medio_validacao"] = round(float(qwk), 3)
            if qwk > melhor:
                melhor = qwk
                melhores_pesos = copy.deepcopy({k: v.cpu() for k, v in modelo.state_dict().items()})
        historico.append(linha)
        print(linha)
    if melhores_pesos is not None:
        modelo.load_state_dict(melhores_pesos)
    return modelo, historico


def liberar():
    """Libera a memória da GPU entre treinos."""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
