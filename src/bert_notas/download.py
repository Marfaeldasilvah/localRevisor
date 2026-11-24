"""Download do checkpoint ajustado do BERTimbau no Hugging Face."""
from __future__ import annotations

from .validation import pasta

HF_REPO_ID = "berghilde/bertimbau-enem-notas"


def baixar_modelo() -> None:
    from huggingface_hub import snapshot_download

    pasta_destino = pasta()
    pasta_destino.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=HF_REPO_ID,
        local_dir=str(pasta_destino),
    )
