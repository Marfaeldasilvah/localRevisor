from __future__ import annotations

import io
import os
import unittest
from unittest import mock

from src import db, main, paths
from tests import support


class WebTests(unittest.TestCase):
    def setUp(self):
        support.reset()
        main.app.config["TESTING"] = True
        self.client = main.app.test_client()
        os.environ.pop("OPENAI_API_KEY", None)
        with main.FEEDBACK_RATE_LOCK:
            main.FEEDBACK_RATE_LIMIT.clear()

    def test_feedback_page_and_send(self):
        response = self.client.get("/feedback")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Envie seu feedback", body)

        token = support.csrf(self.client, "/feedback")
        with mock.patch.object(main, "_send_feedback_email") as send:
            response = self.client.post(
                "/feedback",
                data={
                    "_csrf_token": token,
                    "name": "Maria",
                    "email": "maria@example.com",
                    "message": "Gostei do novo fluxo.",
                },
            )
        self.assertEqual(response.status_code, 302)
        send.assert_called_once_with("Maria", "maria@example.com", "Gostei do novo fluxo.")

    def test_feedback_message_is_required_and_csrf_is_required(self):
        response = self.client.post(
            "/feedback",
            data={"name": "", "email": "", "message": ""},
        )
        self.assertEqual(response.status_code, 400)

        token = support.csrf(self.client, "/feedback")
        response = self.client.post(
            "/feedback",
            data={"_csrf_token": token, "name": "", "email": "", "message": "   "},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Escreva uma mensagem", response.get_data(as_text=True))

    def test_feedback_smtp_error_is_friendly(self):
        token = support.csrf(self.client, "/feedback")
        with mock.patch.object(main, "_send_feedback_email", side_effect=RuntimeError("smtp")):
            response = self.client.post(
                "/feedback",
                data={
                    "_csrf_token": token,
                    "name": "",
                    "email": "",
                    "message": "Relato de um problema.",
                },
            )
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Não foi possível enviar seu feedback", body)

    def test_upload_blocked_without_config(self):
        response = self.client.get("/upload")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/config?setup=1", response.headers["Location"])

    def test_index_shows_setup_banner(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("ainda não está configurada", response.get_data(as_text=True))
        body = response.get_data(as_text=True)
        self.assertIn('id="menu-toggle"', body)
        self.assertIn('href="/feedback"', body)

    def test_config_save(self):
        token = support.csrf(self.client)
        response = self.client.post(
            "/config",
            data={
                "_csrf_token": token,
                "action": "save",
                "base_url": "http://localhost:11434/v1",
                "correction_model": "fake",
                "image_model": "fake",
            },
        )
        self.assertEqual(response.status_code, 302)
        settings = db.get_settings()
        self.assertEqual(settings["correction_model"], "fake")
        self.assertEqual(settings["base_url"], "http://localhost:11434/v1")

    def test_config_connect_populates_select_and_saves_selected_model(self):
        token = support.csrf(self.client)
        models = ["deepseek-chat", "deepseek-reasoner", "qwen2.5"]
        with mock.patch.object(main.grading, "fetch_models", return_value=models):
            response = self.client.post(
                "/config",
                data={
                    "_csrf_token": token,
                    "action": "connect",
                    "base_url": "http://localhost:11434/v1",
                    "correction_model": "",
                    "image_model": "",
                },
                follow_redirects=True,
            )
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Conectado. 3 modelo(s) encontrado(s).", body)
        self.assertIn('id="correction_model_select"', body)
        self.assertIn('id="image_model_select"', body)
        for model in models:
            self.assertIn(f'<option value="{model}"', body)
        # Não preenche arbitrariamente modelos quando há várias opções
        settings_after_connect = db.get_settings()
        self.assertEqual(settings_after_connect["correction_model"], "")
        self.assertEqual(settings_after_connect["image_model"], "")

        token = support.csrf(self.client)
        response = self.client.post(
            "/config",
            data={
                "_csrf_token": token,
                "action": "save",
                "base_url": "http://localhost:11434/v1",
                "correction_model": "deepseek-reasoner",
                "image_model": "qwen2.5",
            },
        )
        self.assertEqual(response.status_code, 302)
        settings = db.get_settings()
        self.assertEqual(settings["correction_model"], "deepseek-reasoner")
        self.assertEqual(settings["image_model"], "qwen2.5")

    def test_config_save_custom_model_option(self):
        token = support.csrf(self.client)
        response = self.client.post(
            "/config",
            data={
                "_csrf_token": token,
                "action": "save",
                "base_url": "http://localhost:11434/v1",
                "correction_model": "__custom__",
                "correction_model_custom": "meu-modelo-local",
                "image_model": "__custom__",
                "image_model_custom": "meu-modelo-visao",
            },
        )
        self.assertEqual(response.status_code, 302)
        settings = db.get_settings()
        self.assertEqual(settings["correction_model"], "meu-modelo-local")
        self.assertEqual(settings["image_model"], "meu-modelo-visao")

    def test_config_renders_popular_provider_presets(self):
        response = self.client.get("/config")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('id="provider_preset"', body)
        for url in (
            "https://api.z.ai/api/paas/v4",
            "https://api.anthropic.com/v1",
            "https://generativelanguage.googleapis.com/v1beta/openai",
            "https://opencode.ai/zen/go/v1",
            "https://opencode.ai/inference/go/v1",
            "http://localhost:11434/v1",
        ):
            self.assertIn(f'value="{url}"', body)

    def test_config_saves_bert_max_tokens(self):
        token = support.csrf(self.client)
        response = self.client.post(
            "/config",
            data={
                "_csrf_token": token,
                "action": "save",
                "base_url": "http://localhost:11434/v1",
                "correction_model": "fake",
                "image_model": "",
                "bert_max_tokens": "4096",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(db.get_settings()["bert_max_tokens"], "4096")
        self.assertIn('id="bert_max_tokens"', response.get_data(as_text=True))

    def test_config_key_save_and_remove(self):
        token = support.csrf(self.client)
        response = self.client.post(
            "/config",
            data={
                "_csrf_token": token,
                "action": "save",
                "base_url": "http://localhost:11434/v1",
                "correction_model": "fake",
                "image_model": "fake",
                "api_key": "chave#teste",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(main.secrets_store.key_configured())
        token = support.csrf(self.client)
        response = self.client.post(
            "/config",
            data={"_csrf_token": token, "action": "remove_key"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(main.secrets_store.key_configured())

    def test_csrf_is_required(self):
        support.configure_models()
        response = self.client.post("/config", data={"action": "save"})
        self.assertEqual(response.status_code, 400)

    def test_upload_text_with_csrf(self):
        support.configure_models()
        token = support.csrf(self.client, "/upload")
        with mock.patch.object(main.worker, "start", return_value=True) as start:
            response = self.client.post(
                "/upload",
                data={
                    "_csrf_token": token,
                    "source": "text",
                    "theme": "Tema",
                    "text": "Uma redação de teste.",
                },
            )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(start.called)
        row = db.query("SELECT * FROM corrections")[0]
        self.assertEqual(row["status"], "corrigindo")
        self.assertTrue((paths.UPLOAD_DIR / row["stored_name"]).exists())

    def test_upload_file_with_csrf(self):
        support.configure_models()
        token = support.csrf(self.client, "/upload")
        with mock.patch.object(main.worker, "start", return_value=True):
            response = self.client.post(
                "/upload",
                data={
                    "_csrf_token": token,
                    "source": "file",
                    "theme": "Tema",
                    "file": (io.BytesIO(b"%PDF-1.4\n"), "redacao.pdf"),
                },
                content_type="multipart/form-data",
            )
        self.assertEqual(response.status_code, 302)
        row = db.query("SELECT * FROM corrections")[0]
        self.assertTrue(row["stored_name"].endswith(".pdf"))

    def test_review_shows_note_scores_and_source(self):
        correction_id = db.create_correction("redacao.txt", "redacao.txt", "Tema")
        db.finish_correction(
            correction_id,
            note=600,
            scores={"C1": 120, "C2": 120, "C3": 120, "C4": 120, "C5": 120},
            explanation="Explicação da correção.",
            errors="",
            source_text="Texto original da redação.",
            score_mode="llm",
            model="modelo",
            provider="localhost",
            prompt_version="review-v2",
            duration_ms=1500,
            tokens_in=10,
            tokens_out=20,
            truncated=False,
        )
        response = self.client.get(f"/review/{correction_id}")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("600", body)
        self.assertIn("Competências", body)
        self.assertIn("Texto original da redação.", body)
        self.assertIn("Explicação da correção.", body)
        self.assertIn("estimativa", body)
        self.assertIn("Refazer correção", body)

        index_body = self.client.get("/").get_data(as_text=True)
        self.assertIn('aria-label="Refazer correção"', index_body)

        token = support.csrf(self.client, f"/review/{correction_id}")
        with mock.patch.object(main.worker, "start", return_value=True) as start:
            retry_response = self.client.post(
                f"/correction/{correction_id}/retry",
                data={"_csrf_token": token},
            )
        self.assertEqual(retry_response.status_code, 302)
        start.assert_called_once_with(correction_id, "Tema", "redacao.txt")
        self.assertEqual(db.get_correction(correction_id)["status"], "corrigindo")

    def test_legacy_pending_review_has_retry(self):
        correction_id = db.create_correction("a.txt", "a.txt", "Tema")
        db.execute("UPDATE corrections SET status = 'pendente' WHERE id = ?", (correction_id,))
        response = self.client.get(f"/review/{correction_id}")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("não processada", body)
        self.assertIn("Tentar novamente", body)

    def test_review_running_redirects(self):
        correction_id = db.create_correction("redacao.txt", "redacao.txt", "Tema")
        response = self.client.get(f"/review/{correction_id}")
        self.assertEqual(response.status_code, 302)

    def test_recover_interrupted_on_restart(self):
        correction_id = db.create_correction("redacao.txt", "redacao.txt", "Tema")
        db.init_db()
        row = db.get_correction(correction_id)
        self.assertEqual(row["status"], "interrompido")
        response = self.client.get(f"/review/{correction_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("interrompida", response.get_data(as_text=True).lower())

    def test_pagination(self):
        for index in range(25):
            db.create_correction(f"{index}.txt", f"{index}.txt", "Tema")
        response = self.client.get("/?page=2")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Página 2 de 2", body)

    def test_delete_requires_csrf_and_deletes(self):
        correction_id = db.create_correction("redacao.txt", "redacao.txt", "Tema")
        db.finish_correction(
            correction_id,
            note=0,
            scores={"C1": 0, "C2": 0, "C3": 0, "C4": 0, "C5": 0},
            explanation="x",
            errors="",
            source_text="x",
            score_mode="llm",
            model="m",
            provider="p",
            prompt_version="v",
            duration_ms=0,
            tokens_in=0,
            tokens_out=0,
            truncated=False,
        )
        response = self.client.post(f"/correction/{correction_id}/delete")
        self.assertEqual(response.status_code, 400)
        token = support.csrf(self.client, "/")
        response = self.client.post(
            f"/correction/{correction_id}/delete",
            data={"_csrf_token": token},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(db.get_correction(correction_id))

    def test_upload_too_large_returns_413(self):
        support.configure_models()
        token = support.csrf(self.client, "/upload")
        old = main.app.config["MAX_CONTENT_LENGTH"]
        main.app.config["MAX_CONTENT_LENGTH"] = 32
        try:
            response = self.client.post(
                "/upload",
                data={
                    "_csrf_token": token,
                    "source": "file",
                    "theme": "Tema",
                    "file": (io.BytesIO(b"x" * 256), "grande.txt"),
                },
                content_type="multipart/form-data",
            )
        finally:
            main.app.config["MAX_CONTENT_LENGTH"] = old
        self.assertEqual(response.status_code, 413)

    def test_security_headers(self):
        response = self.client.get("/")
        self.assertIn("Content-Security-Policy", response.headers)
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_status_endpoint(self):
        db.create_correction("a.txt", "a.txt", "Tema")
        response = self.client.get("/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"pending": 1})

    def test_404(self):
        response = self.client.get("/review/9999")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
