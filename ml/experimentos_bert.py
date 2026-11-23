"""Experimentos com o BERTimbau: generalização para temas novos e estabilidade entre sementes.

Uso (na pasta ml, com GPU, por exemplo no Google Colab):
    python experimentos_bert.py temas-novos     # grava resultados/temas_novos_resultado.csv
    python experimentos_bert.py sementes        # grava resultados/sementes_resultado.csv

Os dois usam apenas o treino e a validação. O conjunto de teste não é tocado.
"""
import argparse
import os

import numpy as np
import pandas as pd

from bert_treino import liberar, prever, treinar
from divisao import escolher_temas_novos
from metricas import COMPS, qwk_por_competencia


def temas_novos(train, valid, repeticoes=3, minimo_redacoes=600, saida="resultados/temas_novos_resultado.csv"):
    """Treina sem alguns temas e compara o QWK em temas vistos e em temas nunca vistos."""
    todos = pd.concat([train, valid], ignore_index=True)
    linhas = []
    for rep in range(repeticoes):
        novos = escolher_temas_novos(todos, rep, minimo_redacoes)
        treino_t = train[~train["tema"].isin(novos)]   # treino sem os temas novos
        vistos = valid[~valid["tema"].isin(novos)]     # validação em temas que o modelo viu
        novos_df = todos[todos["tema"].isin(novos)]    # redações de temas que ele nunca viu
        print(f"\nRepetição {rep + 1}: {len(novos)} temas novos ({len(novos_df)} redações) | "
              f"treino {len(treino_t)} | validação em temas vistos {len(vistos)}")

        modelo, _ = treinar(treino_t, semente=rep)
        q_vistos = qwk_por_competencia(vistos[COMPS].values, prever(modelo, vistos))
        q_novos = qwk_por_competencia(novos_df[COMPS].values, prever(modelo, novos_df))
        linhas.append({"repeticao": rep + 1, "grupo": "temas vistos",
                       **dict(zip(COMPS, q_vistos)), "media": q_vistos.mean()})
        linhas.append({"repeticao": rep + 1, "grupo": "temas novos",
                       **dict(zip(COMPS, q_novos)), "media": q_novos.mean()})
        del modelo
        liberar()

    res = pd.DataFrame(linhas).round(3)
    print("\nMédia das repetições:")
    print(res.groupby("grupo")[COMPS + ["media"]].mean().round(3).to_string())
    os.makedirs(os.path.dirname(saida) or ".", exist_ok=True)
    res.to_csv(saida, index=False)
    print("Salvo em", saida)


def sementes(train, valid, lista=(0, 1, 2), saida="resultados/sementes_resultado.csv"):
    """Repete o treino com sementes diferentes e mede a variação do resultado na validação."""
    linhas = []
    for s in lista:
        modelo, _ = treinar(train, semente=s)
        prev = prever(modelo, valid)
        q = qwk_por_competencia(valid[COMPS].values, prev)
        erro = np.abs(valid[COMPS].values - prev).mean(axis=0)
        linhas.append({"semente": s, **{f"QWK_{c}": v for c, v in zip(COMPS, q)},
                       "QWK_media": q.mean(), "erro_medio": erro.mean()})
        print(f"Semente {s}: QWK médio {q.mean():.3f} | erro médio {erro.mean():.1f} pontos")
        del modelo
        liberar()

    res = pd.DataFrame(linhas).round(3)
    colunas = [c for c in res.columns if c != "semente"]
    print("\nMédia e desvio-padrão entre as sementes:")
    print(res[colunas].agg(["mean", "std"]).round(3).to_string())
    os.makedirs(os.path.dirname(saida) or ".", exist_ok=True)
    res.to_csv(saida, index=False)
    print("Salvo em", saida)


def principal():
    ap = argparse.ArgumentParser(description="Experimentos com o BERTimbau.")
    ap.add_argument("experimento", choices=["temas-novos", "sementes"])
    ap.add_argument("--treino", default="dados/train.csv")
    ap.add_argument("--validacao", default="dados/valid.csv")
    args = ap.parse_args()
    train, valid = pd.read_csv(args.treino), pd.read_csv(args.validacao)
    if args.experimento == "temas-novos":
        temas_novos(train, valid)
    else:
        sementes(train, valid)


if __name__ == "__main__":
    principal()
