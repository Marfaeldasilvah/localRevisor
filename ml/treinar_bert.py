"""Treina o modelo final (BERTimbau) e o salva para uso no aplicativo.

Uso (na pasta ml, de preferência com GPU, por exemplo no Google Colab):
    python treinar_bert.py --saida ../modelos/bertimbau_enem --teste dados/test.csv

- Treina com dados/train.csv e escolhe a melhor época pelo QWK médio em dados/valid.csv.
- Salva o modelo e o tokenizador na pasta indicada em --saida.
- Grava as previsões da validação em resultados/bert_valid_previsoes.csv.
- Com --teste, grava as previsões do teste em resultados/bert_test_previsoes.csv SEM avaliá-las
  (a avaliação do teste é feita uma única vez, por avaliar_teste.py).
"""
import argparse
import os

import pandas as pd

from avaliacao import avaliar
from bert_treino import prever, tokenizador, treinar
from metricas import COMPS


def gravar_previsoes(df, prev, caminho):
    saida = pd.DataFrame(prev, columns=COMPS)
    saida.insert(0, "id", df["id"].values)
    saida.to_csv(caminho, index=False)
    print("Previsões gravadas em", caminho)


def principal():
    ap = argparse.ArgumentParser(description="Treina o BERTimbau para estimar as notas do Enem.")
    ap.add_argument("--treino", default="dados/train.csv")
    ap.add_argument("--validacao", default="dados/valid.csv")
    ap.add_argument("--teste", default=None, help="CSV do teste (só para gravar as previsões)")
    ap.add_argument("--saida", default="../modelos/bertimbau_enem", help="pasta do modelo treinado")
    ap.add_argument("--previsoes", default="resultados", help="pasta das previsões")
    ap.add_argument("--semente", type=int, default=42)
    ap.add_argument("--epocas", type=int, default=4)
    args = ap.parse_args()

    train = pd.read_csv(args.treino)
    valid = pd.read_csv(args.validacao)

    modelo, historico = treinar(train, args.semente, args.epocas, df_validacao=valid)

    prev_valid = prever(modelo, valid)
    print("\nBERTimbau na validação:")
    print(avaliar(valid[COMPS].values, prev_valid))

    os.makedirs(args.saida, exist_ok=True)
    modelo.save_pretrained(args.saida)
    tokenizador().save_pretrained(args.saida)
    print("Modelo salvo em", os.path.abspath(args.saida))

    os.makedirs(args.previsoes, exist_ok=True)
    gravar_previsoes(valid, prev_valid, os.path.join(args.previsoes, "bert_valid_previsoes.csv"))
    if args.teste:
        teste = pd.read_csv(args.teste)
        gravar_previsoes(teste, prever(modelo, teste), os.path.join(args.previsoes, "bert_test_previsoes.csv"))
        print("O teste NÃO foi avaliado aqui. Use avaliar_teste.py, uma única vez.")


if __name__ == "__main__":
    principal()
