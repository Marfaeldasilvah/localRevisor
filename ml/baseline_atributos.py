"""Baselines B0 (sempre a nota mais comum) e B1 (atributos manuais + regressão Ridge).

Uso (na pasta ml):  python baseline_atributos.py
Lê dados/train.csv e dados/valid.csv e mostra as métricas na validação.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from atributos import matriz_atributos
from avaliacao import avaliar
from metricas import COMPS


def previsoes_b0_b1(train, df):
    """Previsões do B0 e do B1 para df. O B1 é ajustado só com o treino (sem vazamento de dados)."""
    modas = [int(train[c].mode()[0]) for c in COMPS]
    prev_b0 = np.tile(modas, (len(df), 1))
    X_train = matriz_atributos([t.split("\n") for t in train["texto"]])
    X_df = matriz_atributos([t.split("\n") for t in df["texto"]])
    b1 = make_pipeline(StandardScaler(), Ridge(alpha=1.0)).fit(X_train, train[COMPS].values)
    prev_b1 = np.clip(np.round(b1.predict(X_df) / 40) * 40, 0, 200).astype(int)
    return prev_b0, prev_b1


if __name__ == "__main__":
    train = pd.read_csv("dados/train.csv")
    valid = pd.read_csv("dados/valid.csv")
    prev_b0, prev_b1 = previsoes_b0_b1(train, valid)
    print("B0 (sempre a nota mais comum do treino):")
    print(avaliar(valid[COMPS].values, prev_b0))
    print("\nB1 (atributos manuais + Ridge):")
    print(avaliar(valid[COMPS].values, prev_b1))
