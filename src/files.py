"""Validação e leitura de arquivos enviados (PDF, imagem, Markdown e texto)."""
from __future__ import annotations

import mimetypes
import subprocess
import tempfile
import uuid
from pathlib import Path

import pypdf
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from . import paths

TEXT_EXTENSIONS = {".md", ".txt"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
PDF_EXTENSIONS = {".pdf"}
ALLOWED_EXTENSIONS = TEXT_EXTENSIONS | IMAGE_EXTENSIONS | PDF_EXTENSIONS
MAX_PDF_PAGES = 30


class UploadError(ValueError):
    """Erro de upload que pode ser mostrado ao usuário."""


def _magic(path: Path) -> tuple[str, str] | None:
    """Devolve (kind, sufixo canônico) a partir dos primeiros bytes."""
    with path.open("rb") as handle:
        head = handle.read(16)
    if head.startswith(b"%PDF-"):
        return "pdf", ".pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", ".png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image", ".jpg"
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
        return "image", ".gif"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "image", ".webp"
    return None


def kind_from_name(name: str) -> str:
    suffix = Path(name).suffix.lower()
    if suffix in PDF_EXTENSIONS:
        return "pdf"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    return "text"


def mime_for(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def validate_and_store(storage: FileStorage, filename: str) -> tuple[str, str]:
    """Salva o upload com nome seguro e valida extensão + conteúdo.

    Devolve (stored_name, kind). O arquivo inválido é removido antes do erro.
    """
    original_suffix = Path(filename).suffix.lower()
    if original_suffix not in ALLOWED_EXTENSIONS:
        raise UploadError("Formato não suportado. Envie PDF, imagem, .md ou .txt.")
    safe = secure_filename(filename) or "arquivo"
    safe_suffix = Path(safe).suffix.lower()
    stored_name = f"{uuid.uuid4().hex}{safe_suffix or original_suffix}"
    target = paths.UPLOAD_DIR / stored_name
    paths.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    storage.save(target)
    try:
        if target.stat().st_size == 0:
            raise UploadError("O arquivo está vazio.")
        if target.stat().st_size > paths.MAX_UPLOAD_BYTES:
            raise UploadError("O arquivo é maior que o limite permitido.")
        if original_suffix in TEXT_EXTENSIONS:
            try:
                target.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                raise UploadError("O texto precisa estar em UTF-8.") from exc
            return stored_name, "text"
        detected = _magic(target)
        if detected is None:
            raise UploadError("O conteúdo do arquivo não corresponde a PDF ou imagem.")
        kind, canonical_suffix = detected
        if original_suffix in PDF_EXTENSIONS and kind != "pdf":
            raise UploadError("O arquivo não parece ser um PDF válido.")
        if original_suffix in IMAGE_EXTENSIONS and kind != "image":
            raise UploadError("O arquivo não parece ser uma imagem válida.")
        if canonical_suffix != target.suffix.lower():
            new_name = f"{Path(stored_name).stem}{canonical_suffix}"
            target.rename(paths.UPLOAD_DIR / new_name)
            stored_name = new_name
        return stored_name, kind
    except Exception:
        target.unlink(missing_ok=True)
        raise


def save_text(text: str) -> str:
    stored_name = f"{uuid.uuid4().hex}_texto.txt"
    paths.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (paths.UPLOAD_DIR / stored_name).write_text(text, encoding="utf-8")
    return stored_name


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace").strip()


def extract_pdf_text(path: Path, max_pages: int = MAX_PDF_PAGES) -> str:
    reader = pypdf.PdfReader(path)
    pages = reader.pages[:max_pages]
    return "\n".join(page.extract_text() or "" for page in pages).strip()


def convert_to_png(path: Path) -> Path:
    # ffmpeg cobre webp/gif e formatos que o modelo de visão não aceita direto.
    fd, tmp_name = tempfile.mkstemp(suffix=".png", dir=str(paths.UPLOAD_DIR))
    Path(tmp_name).unlink(missing_ok=True)
    target = Path(tmp_name)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(path), str(target)],
            check=True,
            capture_output=True,
            timeout=60,
        )
    except FileNotFoundError as exc:
        target.unlink(missing_ok=True)
        raise UploadError(
            "ffmpeg não encontrado para converter a imagem. Instale o ffmpeg."
        ) from exc
    except subprocess.CalledProcessError as exc:
        target.unlink(missing_ok=True)
        raise UploadError("Falha ao converter a imagem para PNG.") from exc
    except subprocess.TimeoutExpired as exc:
        target.unlink(missing_ok=True)
        raise UploadError("A conversão da imagem demorou demais.") from exc
    return target


def is_small_enough(path: Path) -> bool:
    return path.stat().st_size <= paths.MAX_UPLOAD_BYTES
