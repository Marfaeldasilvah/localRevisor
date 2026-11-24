"""Benchmark de redações reais (Essay-BR) para BERT e BERT+IA."""
from __future__ import annotations

from .dataset import EssaySample, load_samples, sample_stratified
from .metrics import BenchRecord, format_summary, quadratic_weighted_kappa, summarize
from .runner import VALID_MODES, run_benchmark

__all__ = [
    "BenchRecord",
    "EssaySample",
    "VALID_MODES",
    "format_summary",
    "load_samples",
    "quadratic_weighted_kappa",
    "run_benchmark",
    "sample_stratified",
    "summarize",
]
