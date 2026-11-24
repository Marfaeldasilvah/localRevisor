"""Rotas principais de histórico, envio, revisão, retry e exclusão."""
from __future__ import annotations

import logging
import math

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for

from .. import bert_notas, db, files, paths, worker
from .routes_config import settings_configured

LOGGER = logging.getLogger(__name__)

STATUS_LABELS = {
    "pendente": "Pendente",
    "corrigindo": "Corrigindo",
    "corrigido": "Corrigida",
    "erro": "Falhou",
    "interrompido": "Interrompida",
}


def _enqueue(
    correction_id: int,
    theme: str,
    stored_name: str,
    *,
    bert_only: bool = False,
) -> bool:
    try:
        if bert_only:
            started = worker.start(
                correction_id, theme, stored_name, bert_only=True
            )
        else:
            started = worker.start(correction_id, theme, stored_name)
    except Exception as exc:
        LOGGER.exception("Falha ao iniciar a correção %s", correction_id)
        db.fail_correction(correction_id, f"Falha ao iniciar a correção: {exc}")
        return False
    if not started:
        db.fail_correction(correction_id, "Esta correção já está em andamento.")
        return False
    return True


def _page_arg() -> int:
    page = request.args.get("page", 1, type=int) or 1
    return max(1, page)


def register(app: Flask) -> None:
    @app.route("/")
    def index():
        page = _page_arg()
        status_filter = request.args.get("status")
        if status_filter not in db.STATUSES:
            status_filter = None
        rows, total = db.recent_corrections(page, db.PER_PAGE, status_filter)
        pages = max(1, math.ceil(total / db.PER_PAGE))
        if page > pages and total:
            page = pages
            rows, total = db.recent_corrections(page, db.PER_PAGE, status_filter)
        settings = db.get_settings()
        corrections = [db.to_dict(row) for row in rows]
        for correction in corrections:
            correction["status_label"] = STATUS_LABELS.get(
                correction["status"], correction["status"]
            )
        return render_template(
            "index.html",
            corrections=corrections,
            page=page,
            pages=pages,
            total=total,
            status=status_filter,
            statuses=db.STATUSES,
            status_labels=STATUS_LABELS,
            pending=db.pending_count(),
            configured=settings_configured(settings),
            bert_available=bert_notas.instalado(),
        )

    @app.get("/status")
    def status():
        return jsonify({"pending": db.pending_count()})

    @app.route("/review/<int:correction_id>")
    def review(correction_id: int):
        row = db.get_correction(correction_id)
        if row is None:
            abort(404)
        if row["status"] == "corrigindo":
            flash("Esta correção ainda está em andamento.", "warning")
            return redirect(url_for("index"))
        data = db.to_dict(row)
        return render_template(
            "review.html",
            correction=data,
            scores=data["scores_dict"],
            note=data["note_display"],
            status_label=STATUS_LABELS.get(row["status"], row["status"]),
            back_url=url_for("index"),
        )

    @app.post("/correction/<int:correction_id>/retry")
    def retry(correction_id: int):
        row = db.get_correction(correction_id)
        if row is None:
            abort(404)
        if row["status"] == "corrigindo" or worker.is_active(correction_id):
            flash("A correção ainda está em andamento.", "warning")
            return redirect(url_for("index"))
        if not db.mark_running(correction_id):
            flash("Não foi possível reagendar esta correção.", "error")
            return redirect(url_for("index"))
        settings = db.get_settings()
        use_bert_only = (
            (not settings_configured(settings) or request.form.get("bert_only") == "1")
            and bert_notas.instalado()
        )
        if not _enqueue(
            correction_id, row["theme"], row["stored_name"], bert_only=use_bert_only
        ):
            flash(
                "A correção falhou ao iniciar. Veja os detalhes na revisão.", "error"
            )
        else:
            flash("Correção reagendada.", "success")
        return redirect(url_for("index"))

    @app.post("/correction/<int:correction_id>/delete")
    def delete_correction(correction_id: int):
        row = db.get_correction(correction_id)
        if row is None:
            abort(404)
        if row["status"] == "corrigindo" or worker.is_active(correction_id):
            flash("Aguarde a correção terminar antes de excluir.", "warning")
            return redirect(url_for("index"))
        stored_name = db.delete_correction(correction_id)
        if stored_name:
            (paths.UPLOAD_DIR / stored_name).unlink(missing_ok=True)
        flash("Correção excluída.", "success")
        return redirect(url_for("index"))

    @app.route("/upload", methods=["GET", "POST"])
    def upload():
        settings = db.get_settings()
        ai_configured = settings_configured(settings)
        bert_available = bert_notas.instalado()
        if not ai_configured and not bert_available:
            flash("Configure a IA ou baixe o BERT antes de enviar uma redação.", "warning")
            return redirect(url_for("config", setup=1))

        error = None
        theme = request.form.get("theme", "").strip()
        source = request.form.get("source", "file")
        bert_only = (
            bert_available
            and (not ai_configured or request.form.get("bert_only") == "1")
        )
        if request.method == "POST":
            if not theme:
                error = "Informe o tema."
            elif source == "text":
                text = request.form.get("text", "").strip()
                if not text:
                    error = "Cole o texto da redação."
                else:
                    stored_name = files.save_text(text)
                    correction_id = db.create_correction(
                        "Texto colado.txt", stored_name, theme
                    )
                    if _enqueue(
                        correction_id, theme, stored_name, bert_only=bert_only
                    ):
                        flash("Redação enviada. Correção em andamento.", "success")
                        return redirect(url_for("index"))
                    error = "Não foi possível iniciar a correção."
            elif source == "file":
                file = request.files.get("file")
                if file is None or not file.filename:
                    error = "Selecione um arquivo."
                else:
                    try:
                        stored_name, _kind = files.validate_and_store(
                            file, file.filename
                        )
                    except files.UploadError as exc:
                        error = str(exc)
                    else:
                        correction_id = db.create_correction(
                            file.filename, stored_name, theme
                        )
                        if _enqueue(
                            correction_id, theme, stored_name, bert_only=bert_only
                        ):
                            flash("Redação enviada. Correção em andamento.", "success")
                            return redirect(url_for("index"))
                        error = "Não foi possível iniciar a correção."
            else:
                error = "Escolha entre enviar um arquivo ou colar o texto."

        return render_template(
            "upload.html",
            error=error,
            theme=theme,
            source=source,
            ai_configured=ai_configured,
            bert_available=bert_available,
            bert_only=bert_only,
            back_url=url_for("index"),
            max_upload_mb=max(1, paths.MAX_UPLOAD_BYTES // (1024 * 1024)),
        )
