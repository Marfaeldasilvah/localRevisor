"""Tipos de dados e exceções do domínio de correção."""
from __future__ import annotations

from dataclasses import dataclass

from .. import bert_notas

COMPETENCIAS = bert_notas.COMPETENCIAS


class GradingError(RuntimeError):
    """Erro de configuração ou do provedor que pode ser mostrado ao usuário."""


class ModelOutputError(GradingError):
    """O provedor respondeu, mas fora do contrato esperado."""


@dataclass
class ReviewResult:
    note: int
    scores: dict[str, int]
    explanation: str
    errors: str
    source_text: str
    score_mode: str
    model: str
    provider: str
    prompt_version: str
    duration_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    truncated: bool = False
