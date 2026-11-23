"""Tabela de avaliação por competência (QWK, erro médio, acerto aproximado e viés)."""
import numpy as np
import pandas as pd

from metricas import COMPS, qwk


def avaliar(y_real, y_prev):
    """y_real e y_prev: matrizes (n redações x 5) com notas de 0 a 200."""
    linhas = []
    for i, nome in enumerate(COMPS):
        real, prev = y_real[:, i], y_prev[:, i]
        linhas.append({
            "competencia": nome,
            "QWK": qwk(real, prev),
            "erro_medio": np.abs(real - prev).mean(),
            "acerto_aprox": (np.abs(real - prev) <= 40).mean(),
            "vies_medio": (prev - real).mean(),
        })
    return pd.DataFrame(linhas).round(3)
