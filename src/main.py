"""Aplicação Flask do localRevisor: rotas, CSRF, upload e configuração."""
from __future__ import annotations

import hmac
import json
import logging
import math
import os
import secrets

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from . import paths

load_dotenv(paths.ENV_PATH)

from . import bert_notas, db, files, grading, secrets_store, worker  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
LOGGER = logging.getLogger(__name__)

app = Flask(__name__)
app.config.update(
    MAX_CONTENT_LENGTH=paths.MAX_UPLOAD_BYTES,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    TRUSTED_HOSTS=["localhost", "127.0.0.1", "::1", "[::1]"],
)
app.secret_key = secrets_store.load_or_create_secret()

STATUS_LABELS = {
    "pendente": "Pendente",
    "corrigindo": "Corrigindo",
    "corrigido": "Corrigida",
    "erro": "Falhou",
    "interrompido": "Interrompida",
}


def csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def _csrf_protect():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        expected = session.get("_csrf_token", "")
        sent = request.form.get("_csrf_token") or request.headers.get(
            "X-CSRF-Token", ""
        )
        if not expected or not hmac.compare_digest(str(expected), str(sent)):
            abort(400, description="Sessão inválida ou formulário expirado.")


@app.after_request
def _security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; style-src 'self'; "
        "script-src 'self'; base-uri 'none'; form-action 'self'; "
        "frame-ancestors 'none'",
    )
    return response


def _settings_configured(settings: dict[str, str] | None = None) -> bool:
    settings = settings or db.get_settings()
    if not (settings.get("correction_model") or "").strip():
        return False
    if secrets_store.key_configured():
        return True
    return grading.is_local_endpoint(settings.get("base_url", ""))


def _model_options(settings: dict[str, str]) -> tuple[list[str], list[str]]:
    try:
        models = json.loads(settings.get("models") or "[]")
    except ValueError:
        models = []
    if not isinstance(models, list):
        models = []
    models = [str(model) for model in models if str(model).strip()]
    correction = list(models)
    image = list(models)
    if "deepseek" in settings.get("base_url", "").lower() and (
        grading.VISION_MODEL not in image
    ):
        image.insert(0, grading.VISION_MODEL)
    current_correction = settings.get("correction_model", "").strip()
    current_image = settings.get("image_model", "").strip()
    if current_correction and current_correction not in correction:
        correction.insert(0, current_correction)
    if current_image and current_image not in image:
        image.insert(0, current_image)
    return correction, image


def _enqueue(correction_id: int, theme: str, stored_name: str) -> bool:
    try:
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


@app.route("/")
def index():
    page = _page_arg()
    status = request.args.get("status")
    if status not in db.STATUSES:
        status = None
    rows, total = db.recent_corrections(page, db.PER_PAGE, status)
    pages = max(1, math.ceil(total / db.PER_PAGE))
    if page > pages and total:
        page = pages
        rows, total = db.recent_corrections(page, db.PER_PAGE, status)
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
        status=status,
        statuses=db.STATUSES,
        status_labels=STATUS_LABELS,
        pending=db.pending_count(),
        configured=_settings_configured(settings),
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
    if not _enqueue(correction_id, row["theme"], row["stored_name"]):
        flash("A correção falhou ao iniciar. Veja os detalhes na revisão.", "error")
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
    if not _settings_configured(settings):
        flash("Configure a IA antes de enviar uma redação.", "warning")
        return redirect(url_for("config", setup=1))

    error = None
    theme = request.form.get("theme", "").strip()
    source = request.form.get("source", "file")
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
                if _enqueue(correction_id, theme, stored_name):
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
                    if _enqueue(correction_id, theme, stored_name):
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
        back_url=url_for("index"),
        max_upload_mb=max(1, paths.MAX_UPLOAD_BYTES // (1024 * 1024)),
    )
#recebendo rota do bert_notas para baixar modelo

@app.route("/config/baixar-bert", methods=["POST"])
def baixar_bert():
    try:
        bert_notas.baixar_modelo()
        flash("Modelo BERT baixado com sucesso! Agora você já pode ativá-lo.", "success")
    except Exception as exc:
        flash(f"Erro ao baixar modelo do Hugging Face: {exc}", "error")
    return redirect(url_for("config"))

@app.route("/config", methods=["GET", "POST"])
def config():
    settings = db.get_settings()
    if request.method == "POST":
        action = request.form.get("action", "save")
        if action == "remove_key":
            persisted, message = secrets_store.remove_api_key()
            flash(message, "success" if persisted else "warning")
            return redirect(url_for("config"))

        base_url = request.form.get("base_url", "").strip()
        correction_model = request.form.get("correction_model", "").strip()
        image_model = request.form.get("image_model", "").strip()
        entered_key = request.form.get("api_key", "").strip()
        if entered_key:
            try:
                persisted, key_message = secrets_store.save_api_key(entered_key)
            except ValueError as exc:
                flash(str(exc), "error")
                return redirect(url_for("config"))
            flash(key_message, "success" if persisted else "warning")

        if base_url:
            try:
                base_url = grading.validate_base_url(base_url)
            except grading.GradingError as exc:
                flash(str(exc), "error")
                return redirect(url_for("config"))
        if base_url != settings.get("base_url", ""):
            settings["models"] = "[]"
        settings["base_url"] = base_url
        settings["correction_model"] = correction_model
        settings["image_model"] = image_model
        settings["use_bert"] = (
            "1" if request.form.get("use_bert") and bert_notas.instalado() else "0"
        )
        db.save_settings(settings)

        if action == "connect":
            try:
                api_key = entered_key or os.environ.get("OPENAI_API_KEY", "")
                models = grading.fetch_models(base_url, api_key)
            except grading.GradingError as exc:
                flash(str(exc), "error")
                return redirect(url_for("config"))
            settings["models"] = json.dumps(models)
            if correction_model not in models:
                settings["correction_model"] = models[0] if models else ""
            if image_model not in models:
                if "deepseek" in base_url.lower():
                    settings["image_model"] = grading.VISION_MODEL
                else:
                    settings["image_model"] = models[0] if models else ""
            db.save_settings(settings)
            flash(
                f"Conectado. {len(models)} modelo(s) encontrado(s).", "success"
            )
        else:
            flash("Configurações salvas.", "success")
        return redirect(url_for("config"))

    correction_options, image_options = _model_options(settings)
    setup = request.args.get("setup") == "1"
    return render_template(
        "config.html",
        base_url=settings.get("base_url", ""),
        key_configured=secrets_store.key_configured(),
        correction_options=correction_options,
        image_options=image_options,
        correction_model=settings.get("correction_model", ""),
        image_model=settings.get("image_model", ""),
        use_bert=settings.get("use_bert") == "1" and bert_notas.instalado(),
        bert_available=bert_notas.instalado(),
        bert_reason=bert_notas.motivo_indisponivel(),
        setup=setup,
        back_url=url_for("index"),
    )


@app.errorhandler(400)
def bad_request(error):
    return (
        render_template(
            "error.html",
            code=400,
            message=getattr(error, "description", "Requisição inválida."),
        ),
        400,
    )


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="Página não encontrada."), 404


@app.errorhandler(413)
def too_large(_error):
    limit = paths.MAX_UPLOAD_BYTES / (1024 * 1024)
    return (
        render_template(
            "error.html",
            code=413,
            message=f"O arquivo é maior que o limite de {limit:.0f} MB.",
        ),
        413,
    )


@app.errorhandler(500)
def server_error(error):
    LOGGER.exception("Erro interno: %s", error)
    return (
        render_template(
            "error.html",
            code=500,
            message="Algo deu errado no servidor. Tente novamente.",
        ),
        500,
    )


db.init_db()


def _normalize_startup_settings() -> None:
    """Desliga o BERT se o banco antigo o deixou ligado sem checkpoint válido."""
    settings = db.get_settings()
    if settings.get("use_bert") == "1" and not bert_notas.instalado():
        settings["use_bert"] = "0"
        db.save_settings(settings)
        LOGGER.warning("Modo BERT desligado no banco: checkpoint/dependências ausentes.")


_normalize_startup_settings()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
