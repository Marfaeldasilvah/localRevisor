"""Confere se o checkpoint local reproduz as previsões feitas no Colab.

Uso:
    python verificar_bert_local.py CAMINHO/valid.csv CAMINHO/bert_valid_previsoes.csv [N]

O `valid.csv` não vai para o repositório (contém redações). O CSV de previsões
versionado tem apenas `id` e as cinco notas. O script usa a biblioteca padrão;
só depende de `requirements-bert.txt` para carregar o modelo.
"""
from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path
from statistics import mean

from src import bert_notas

COMPS = ["C1", "C2", "C3", "C4", "C5"]


def ler_csv(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "id" not in reader.fieldnames:
            raise SystemExit(f"{path}: o CSV precisa da coluna id.")
        return {str(row["id"]): row for row in reader}


def notas(texto: str) -> list[int]:
    resultado = bert_notas.estimar(texto)[0]
    return [resultado[comp] for comp in COMPS]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("valid_csv", type=Path, help="CSV com id, texto e notas do professor")
    parser.add_argument(
        "previsoes_csv", type=Path, help="CSV com id, C1..C5 gerado no Colab"
    )
    parser.add_argument(
        "n", nargs="?", type=int, default=50, help="amostra (padrão: 50)"
    )
    args = parser.parse_args()

    valid = ler_csv(args.valid_csv)
    previsoes = ler_csv(args.previsoes_csv)
    ids = sorted(set(valid) & set(previsoes))
    if not ids:
        raise SystemExit("Nenhum id em comum entre os dois CSVs.")
    random.Random(42).shuffle(ids)
    amostra = ids[: max(1, args.n)]

    local: list[list[int]] = []
    colab: list[list[int]] = []
    professor: list[list[int]] = []
    for item in amostra:
        row = valid[item]
        if "texto" not in row:
            raise SystemExit(f"{args.valid_csv}: a coluna texto é obrigatória.")
        local.append(notas(row["texto"]))
        colab.append([int(previsoes[item][comp]) for comp in COMPS])
        professor.append([int(row[comp]) for comp in COMPS])

    iguais = sum(a == b for a, b in zip(local, colab)) / len(amostra) * 100
    diferenca = mean(
        abs(a - b) for linha_a, linha_b in zip(local, colab) for a, b in zip(linha_a, linha_b)
    )
    erro_local = mean(
        abs(a - b)
        for linha_a, linha_b in zip(local, professor)
        for a, b in zip(linha_a, linha_b)
    )
    erro_colab = mean(
        abs(a - b)
        for linha_a, linha_b in zip(colab, professor)
        for a, b in zip(linha_a, linha_b)
    )

    print(f"Amostra: {len(amostra)} redação(ões)")
    print(f"Notas idênticas ao Colab: {iguais:.1f}%")
    print(f"Diferença média local × Colab (pontos): {diferenca:.2f}")
    print(f"Erro médio vs professor — local: {erro_local:.1f}")
    print(f"Erro médio vs professor — Colab: {erro_colab:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
