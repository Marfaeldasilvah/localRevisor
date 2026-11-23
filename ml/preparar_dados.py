"""Prepara os CSVs de treino, validação e teste a partir do corpus Essay-BR.

O corpus não é distribuído com este projeto. Clone o repositório do Essay-BR
(https://github.com/lplnufpi/essay-br) em uma pasta, por exemplo ml/corpus, e rode:

    python preparar_dados.py --corpus corpus --saida dados

Gera dados/train.csv, dados/valid.csv e dados/test.csv com as colunas:
id, tema (código numérico do tema), texto, C1, C2, C3, C4, C5.
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd


def como_texto(x):
    if isinstance(x, (list, tuple, np.ndarray)):
        return "\n".join(str(i) for i in x)
    return str(x)


def preparar(df):
    saida = pd.DataFrame({
        "id": df.index,
        "tema": df["prompt"].apply(como_texto),
        "texto": df["essay"].apply(como_texto),
    })
    comp = pd.DataFrame(df["competence"].tolist(), columns=["C1", "C2", "C3", "C4", "C5"])
    comp.index = saida.index
    return pd.concat([saida, comp], axis=1)


def principal():
    ap = argparse.ArgumentParser(description="Prepara os CSVs a partir do corpus Essay-BR.")
    ap.add_argument("--corpus", default="corpus", help="pasta com o clone do repositório do Essay-BR")
    ap.add_argument("--saida", default="dados", help="pasta onde os CSVs serão gravados")
    args = ap.parse_args()

    saida = os.path.abspath(args.saida)
    corpus = os.path.abspath(args.corpus)
    if not os.path.isfile(os.path.join(corpus, "build_dataset.py")):
        raise SystemExit(f"Não encontrei build_dataset.py em {corpus}. Clone o repositório do Essay-BR nessa pasta.")

    sys.path.insert(0, corpus)
    os.chdir(corpus)  # o Corpus procura os arquivos de dados a partir da pasta do corpus
    from build_dataset import Corpus

    train, valid, test = Corpus().read_splits()
    os.makedirs(saida, exist_ok=True)
    for nome, df in [("train", train), ("valid", valid), ("test", test)]:
        tabela = preparar(df)
        tabela.to_csv(os.path.join(saida, f"{nome}.csv"), index=False, encoding="utf-8")
        print(nome, tabela.shape)


if __name__ == "__main__":
    principal()
