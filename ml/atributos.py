"""Atributos manuais usados no baseline B1 (compartilhado entre os scripts)."""
import re

import pandas as pd

CONECTIVOS = ["portanto", "além disso", "entretanto", "contudo", "porém", "todavia",
              "no entanto", "dessa forma", "desse modo", "pois", "porque", "logo",
              "ademais", "sobretudo", "por isso", "embora", "visto que", "haja vista"]
PROPOSTA = ["deve", "devem", "cabe", "por meio de", "a fim de",
            "com o intuito de", "com o objetivo de", "para que"]


def atributos(paragrafos):
    texto = "\n".join(paragrafos)
    baixo = texto.lower()
    palavras = re.findall(r"\w+", baixo)
    frases = [f for f in re.split(r"[.!?]+", texto) if f.strip()]
    n = max(len(palavras), 1)
    return {
        "n_palavras": len(palavras),
        "n_paragrafos": len(paragrafos),
        "n_frases": len(frases),
        "palavras_por_frase": len(palavras) / max(len(frases), 1),
        "diversidade": len(set(palavras)) / n,
        "conectivos": sum(baixo.count(c) for c in CONECTIVOS) / n * 100,
        "virgulas": texto.count(",") / n * 100,
        "proposta_final": sum(paragrafos[-1].lower().count(p) for p in PROPOSTA),
    }


def matriz_atributos(redacoes):
    """redacoes: sequência em que cada item é a lista de parágrafos de uma redação."""
    return pd.DataFrame([atributos(p) for p in redacoes])
