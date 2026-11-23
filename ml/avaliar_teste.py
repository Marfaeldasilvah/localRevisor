"""Avaliação final no conjunto de TESTE. Use uma única vez, com o modelo já escolhido.

Uso (na pasta do estudo):
    python avaliar_teste.py
    python avaliar_teste.py dados/test.csv resultados/bert_test_previsoes.csv resultados/comparacao_teste.csv

Lê dados/train.csv (para o B0 e o B1), o test.csv e as previsões do BERTimbau para o teste.
Gera resultados/comparacao_teste.csv.
"""
import sys

import pandas as pd

from baseline_atributos import previsoes_b0_b1
from comparar import resumir
from metricas import COMPS

caminho_teste = sys.argv[1] if len(sys.argv) > 1 else "dados/test.csv"
caminho_bert = sys.argv[2] if len(sys.argv) > 2 else "resultados/bert_test_previsoes.csv"
caminho_saida = sys.argv[3] if len(sys.argv) > 3 else "resultados/comparacao_teste.csv"

train = pd.read_csv("dados/train.csv")
teste = pd.read_csv(caminho_teste).set_index("id")
bert = pd.read_csv(caminho_bert).set_index("id")

if len(bert) != len(teste) or set(bert.index) != set(teste.index):
    raise SystemExit("As previsões do BERT não correspondem às redações do teste (ids diferentes).")
bert = bert.loc[teste.index]

prev_b0, prev_b1 = previsoes_b0_b1(train, teste)
resumir(
    teste[COMPS].values,
    {
        "B0 (sempre 120)": prev_b0,
        "B1 (atributos)": prev_b1,
        "BERTimbau": bert[COMPS].values.astype(int),
    },
    "Conjunto de teste",
    caminho_saida,
)
