"""Comparação dos modelos na validação do Essay-BR, com intervalos de confiança.

Uso (na pasta essay):  python comparar.py
Lê:    dados/train.csv, dados/valid.csv, resultados/bert_valid_previsoes.csv,
       resultados/zero_shot*.jsonl
Gera:  resultados/comparacao_validacao_686.csv e resultados/comparacao_validacao_comum.csv
O conjunto de TESTE não é usado aqui.
"""
import glob
import json
import os

import numpy as np
import pandas as pd

from baseline_atributos import previsoes_b0_b1
from metricas import COMPS, qwk_por_competencia

N_BOOT = 1000
SEMENTE = 42


def bootstrap(real, previsoes, indices):
    """QWK por competência em cada reamostragem (mesmas reamostragens para todos os modelos)."""
    saida = {nome: np.empty((len(indices), 5)) for nome in previsoes}
    for b, idx in enumerate(indices):
        for nome, prev in previsoes.items():
            saida[nome][b] = qwk_por_competencia(real[idx], prev[idx])
    return saida


def resumir(real, previsoes, titulo, caminho_csv):
    n = len(real)
    rng = np.random.default_rng(SEMENTE)
    indices = rng.integers(0, n, size=(N_BOOT, n))
    boot = bootstrap(real, previsoes, indices)

    qwk_linhas, erro_linhas, vies_linhas = [], [], []
    for nome, prev in previsoes.items():
        pontual = qwk_por_competencia(real, prev)
        media_boot = boot[nome].mean(axis=1)
        celulas = {}
        for i, c in enumerate(COMPS):
            lo, hi = np.percentile(boot[nome][:, i], [2.5, 97.5])
            celulas[c] = f"{pontual[i]:.2f} [{lo:.2f}; {hi:.2f}]"
        lo, hi = np.percentile(media_boot, [2.5, 97.5])
        celulas["Média"] = f"{pontual.mean():.2f} [{lo:.2f}; {hi:.2f}]"
        qwk_linhas.append({"modelo": nome, **celulas})
        erro_linhas.append({"modelo": nome, **{c: round(float(np.abs(real[:, i] - prev[:, i]).mean()), 1)
                                              for i, c in enumerate(COMPS)}})
        vies_linhas.append({"modelo": nome, **{c: round(float((prev[:, i] - real[:, i]).mean()), 1)
                                              for i, c in enumerate(COMPS)}})

    tab_qwk = pd.DataFrame(qwk_linhas).set_index("modelo")
    tab_erro = pd.DataFrame(erro_linhas).set_index("modelo")
    tab_vies = pd.DataFrame(vies_linhas).set_index("modelo")

    print(f"\n==== {titulo} ({n} redações) ====")
    print("\nQWK [intervalo de confiança de 95%]")
    print(tab_qwk.to_string())
    print("\nErro médio (pontos)")
    print(tab_erro.to_string())
    print("\nViés médio (pontos; negativo = nota mais baixa que a do professor)")
    print(tab_vies.to_string())

    if "BERTimbau" in previsoes:
        print("\nBERTimbau menos cada modelo: diferença na média de QWK [IC 95%]")
        base = boot["BERTimbau"].mean(axis=1)
        for nome in previsoes:
            if nome == "BERTimbau":
                continue
            dif = base - boot[nome].mean(axis=1)
            ponto = qwk_por_competencia(real, previsoes["BERTimbau"]).mean() - \
                qwk_por_competencia(real, previsoes[nome]).mean()
            lo, hi = np.percentile(dif, [2.5, 97.5])
            marca = "diferença clara" if lo > 0 or hi < 0 else "dentro da margem de erro"
            print(f"  vs {nome}: {ponto:+.2f} [{lo:+.2f}; {hi:+.2f}]  -> {marca}")

    os.makedirs("resultados", exist_ok=True)
    pd.concat({"QWK": tab_qwk, "erro_medio": tab_erro.astype(str), "vies_medio": tab_vies.astype(str)},
              axis=0).to_csv(caminho_csv, encoding="utf-8-sig")
    print("\nSalvo em", caminho_csv)


def carregar_llm(caminho):
    notas = {}
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            d = json.loads(linha)
            if d.get("notas"):
                notas[int(d["id"])] = d["notas"]
    return notas

def main():
    # ---- Dados ----
    train = pd.read_csv("dados/train.csv")
    valid = pd.read_csv("dados/valid.csv").set_index("id")
    y_valid = valid[COMPS].values
    ids = valid.index.to_numpy()

    prev_b0, prev_b1 = previsoes_b0_b1(train, valid)

    # ---- BERTimbau (previsões geradas no Colab) ----
    bert = pd.read_csv("resultados/bert_valid_previsoes.csv").set_index("id").loc[ids]
    prev_bert = bert[COMPS].values.astype(int)

    # ---- Tabela 1: validação completa ----
    resumir(y_valid,
            {"B0 (sempre 120)": prev_b0, "B1 (atributos)": prev_b1, "BERTimbau": prev_bert},
            "Validação completa", "resultados/comparacao_validacao_686.csv")

    # ---- Tabela 2: redações em comum com os LLMs ----
    llms = {}
    for caminho in sorted(glob.glob("resultados/zero_shot*.jsonl")):
        nome = os.path.basename(caminho).replace("zero_shot_", "").replace(".jsonl", "")
        llms[nome] = carregar_llm(caminho)

    if llms:
        comuns = sorted(set.intersection(*[set(d) for d in llms.values()]))
        pos = [int(np.where(ids == i)[0][0]) for i in comuns]
        previsoes = {
            "B0 (sempre 120)": prev_b0[pos],
            "B1 (atributos)": prev_b1[pos],
            **{nome: np.array([d[i] for i in comuns]) for nome, d in llms.items()},
            "BERTimbau": prev_bert[pos],
        }
        resumir(y_valid[pos], previsoes, "Redações em comum com os LLMs",
                "resultados/comparacao_validacao_comum.csv")


if __name__ == "__main__":
    main()
