"""Métricas usadas em toda a pipeline."""
import numpy as np

COMPS = ["C1", "C2", "C3", "C4", "C5"]


def qwk(real, prev):
    """Quadratic weighted kappa para notas 0, 40, ..., 200 (1 = concordância perfeita)."""
    k = 6
    a, b = real // 40, prev // 40
    obs = np.bincount(a * k + b, minlength=k * k).reshape(k, k).astype(float)
    peso = (np.arange(k)[:, None] - np.arange(k)[None, :]) ** 2
    esperado = np.outer(obs.sum(1), obs.sum(0)) / obs.sum()
    den = (peso * esperado).sum()
    return 0.0 if den == 0 else 1 - (peso * obs).sum() / den


def qwk_por_competencia(real, prev):
    """real e prev: matrizes (n redações x 5 competências). Devolve o QWK de cada competência."""
    return np.array([qwk(real[:, i], prev[:, i]) for i in range(5)])


def modelo_nao_regride(qwk_novo, qwk_atual, tolerancia=0.01):
    """Teste de regressão de desempenho: um modelo novo só é aceito se o QWK médio não ficar
    abaixo do atual por mais do que a tolerância."""
    return qwk_novo >= qwk_atual - tolerancia
