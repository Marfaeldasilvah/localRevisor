"""Rota e envio SMTP do formulário de feedback, com rate limit local."""
from __future__ import annotations

import logging
import os
import smtplib
import threading
import time
from collections.abc import Callable
from email.message import EmailMessage
from email.utils import formataddr

from flask import Flask, flash, redirect, render_template, request, url_for

LOGGER = logging.getLogger(__name__)

FEEDBACK_WINDOW_SECONDS = 10 * 60
FEEDBACK_MAX_PER_WINDOW = 3
FEEDBACK_RATE_LIMIT: dict[str, list[float]] = {}
FEEDBACK_RATE_LOCK = threading.Lock()


def _feedback_rate_limited() -> bool:
    key = str(request.remote_addr or "unknown")
    now = time.monotonic()
    with FEEDBACK_RATE_LOCK:
        recent = [
            timestamp
            for timestamp in FEEDBACK_RATE_LIMIT.get(key, [])
            if now - timestamp < FEEDBACK_WINDOW_SECONDS
        ]
        if len(recent) >= FEEDBACK_MAX_PER_WINDOW:
            FEEDBACK_RATE_LIMIT[key] = recent
            return True
        recent.append(now)
        FEEDBACK_RATE_LIMIT[key] = recent
    return False


def valid_feedback_email(value: str) -> bool:
    if not value:
        return True
    if len(value) > 254 or "\r" in value or "\n" in value:
        return False
    if value.count("@") != 1:
        return False
    local, domain = value.rsplit("@", 1)
    return bool(local and domain and "." in domain)


def send_feedback_email(name: str, email: str, message: str) -> None:
    host = os.environ.get("SMTP_HOST", "").strip()
    destination = os.environ.get("FEEDBACK_EMAIL", "").strip()
    if not host or not destination:
        raise RuntimeError("Configuração de feedback incompleta.")
    if any(char in host or char in destination for char in ("\r", "\n")):
        raise RuntimeError("Configuração de feedback inválida.")
    if not valid_feedback_email(destination):
        raise RuntimeError("Destinatário de feedback inválido.")

    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
    except ValueError as exc:
        raise RuntimeError("Porta SMTP inválida.") from exc

    username = os.environ.get("SMTP_USERNAME", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "")
    from_address = os.environ.get("SMTP_FROM", "").strip() or username
    if not from_address or "\r" in from_address or "\n" in from_address:
        raise RuntimeError("Remetente SMTP não configurado.")

    email_message = EmailMessage()
    email_message["Subject"] = "Novo feedback - localRevisor"
    email_message["From"] = formataddr(("localRevisor", from_address))
    email_message["To"] = destination
    if email:
        email_message["Reply-To"] = email
    sender_name = name or "Usuário não informado"
    email_message.set_content(
        "Você recebeu uma nova mensagem pelo localRevisor.\n\n"
        f"Nome: {sender_name}\n"
        f"E-mail: {email or 'Não informado'}\n\n"
        f"Mensagem:\n{message}\n",
        charset="utf-8",
    )

    use_ssl = os.environ.get("SMTP_USE_SSL", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if use_ssl or port == 465:
        smtp = smtplib.SMTP_SSL(host, port, timeout=20)
    else:
        smtp = smtplib.SMTP(host, port, timeout=20)

    with smtp:
        if not use_ssl and port != 465:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
        if username:
            smtp.login(username, password)
        smtp.send_message(email_message)


def register(
    app: Flask,
    *,
    send_email: Callable[[str, str, str], None] | None = None,
) -> None:
    @app.route("/feedback", methods=["GET", "POST"])
    def feedback():
        error = None
        name = ""
        email = ""
        message = ""

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip()
            message = request.form.get("message", "").strip()
            honeypot = request.form.get("website", "").strip()

            if honeypot:
                flash("Feedback enviado.", "success")
                return redirect(url_for("feedback"))
            if len(name) > 100:
                error = "O nome deve ter no máximo 100 caracteres."
            elif len(email) > 254 or not valid_feedback_email(email):
                error = "Informe um e-mail válido ou deixe o campo em branco."
            elif not message:
                error = "Escreva uma mensagem antes de enviar."
            elif len(message) > 5000:
                error = "A mensagem deve ter no máximo 5000 caracteres."
            elif _feedback_rate_limited():
                error = (
                    "Muitas mensagens foram enviadas recentemente. "
                    "Aguarde alguns minutos."
                )
            else:
                try:
                    sender = send_email or send_feedback_email
                    sender(name, email, message)
                except Exception:
                    LOGGER.exception("Falha ao enviar feedback por SMTP.")
                    error = (
                        "Não foi possível enviar seu feedback agora. "
                        "Tente novamente mais tarde."
                    )
                else:
                    flash("Feedback enviado. Obrigado pela contribuição!", "success")
                    return redirect(url_for("feedback"))

        return render_template(
            "feedback.html",
            error=error,
            name=name,
            email=email,
            message=message,
            back_url=url_for("index"),
        )
