"""Rotas de configuração do provedor de IA, modelos e modo BERT."""
from __future__ import annotations

import json
import os

from flask import Flask, flash, redirect, render_template, request, url_for

from .. import bert_notas, db, grading, secrets_store

CUSTOM_MODEL_VALUE = "__custom__"


def settings_configured(settings: dict[str, str] | None = None) -> bool:
    settings = settings or db.get_settings()
    if not (settings.get("correction_model") or "").strip():
        return False
    if secrets_store.key_configured():
        return True
    return grading.is_local_endpoint(settings.get("base_url", ""))


def model_options(settings: dict[str, str]) -> tuple[list[str], list[str]]:
    try:
        models = json.loads(settings.get("models") or "[]")
    except ValueError:
        models = []
    if not isinstance(models, list):
        models = []
    models = [str(model).strip() for model in models if str(model).strip()]
    correction = list(models)
    image = list(models)
    current_correction = settings.get("correction_model", "").strip()
    current_image = settings.get("image_model", "").strip()
    if current_correction and current_correction not in correction:
        correction.insert(0, current_correction)
    if current_image and current_image not in image:
        image.insert(0, current_image)
    return correction, image


def _read_model_field(field: str) -> str:
    value = request.form.get(field, "").strip()
    if value == CUSTOM_MODEL_VALUE:
        return request.form.get(f"{field}_custom", "").strip()
    return value


def register(app: Flask) -> None:
    @app.route("/config/baixar-bert", methods=["POST"])
    def baixar_bert():
        try:
            bert_notas.baixar_modelo()
            flash(
                "Modelo BERT baixado com sucesso! Agora você já pode ativá-lo.",
                "success",
            )
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
            correction_model = _read_model_field("correction_model")
            image_model = _read_model_field("image_model")
            entered_key = request.form.get("api_key", "").strip()
            if entered_key:
                try:
                    persisted, key_message = secrets_store.save_api_key(entered_key)
                except ValueError as exc:
                    flash(str(exc), "error")
                    return redirect(url_for("config"))
                flash(key_message, "success" if persisted else "warning")

            if action == "connect" and not base_url:
                flash("Informe uma URL base http(s) válida.", "error")
                return redirect(url_for("config"))
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
                "1"
                if request.form.get("use_bert") and bert_notas.instalado()
                else "0"
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
                    settings["correction_model"] = (
                        models[0] if len(models) == 1 else ""
                    )
                if image_model not in models:
                    settings["image_model"] = ""
                db.save_settings(settings)
                if models:
                    flash(
                        f"Conectado. {len(models)} modelo(s) encontrado(s).",
                        "success",
                    )
                else:
                    flash(
                        "Conectado, mas o endpoint /models não retornou nenhum modelo.",
                        "warning",
                    )
            else:
                flash("Configurações salvas.", "success")
            return redirect(url_for("config"))

        correction_options, image_options = model_options(settings)
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
