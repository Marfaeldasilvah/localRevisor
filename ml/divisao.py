"""Divisão por temas: escolhe temas inteiros para ficarem fora do treino."""
import numpy as np


def escolher_temas_novos(todos, repeticao, minimo_redacoes=600):
    """Sorteia temas (sempre os mesmos para a mesma repetição) até somarem ao menos
    `minimo_redacoes` redações. `todos` é um DataFrame com a coluna `tema`."""
    rng = np.random.default_rng(100 + repeticao)
    temas = sorted(todos["tema"].unique())
    novos, total = set(), 0
    for tema in rng.permutation(temas):
        if total >= minimo_redacoes:
            break
        novos.add(tema)
        total += int((todos["tema"] == tema).sum())
    return novos
