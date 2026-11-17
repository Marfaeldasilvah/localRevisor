from __future__ import annotations

import unittest

from src import db
from tests import support


class DbTests(unittest.TestCase):
    def setUp(self):
        support.reset()

    def test_create_finish_and_read(self):
        correction_id = db.create_correction("redacao.pdf", "arquivo.pdf", "Tema")
        row = db.get_correction(correction_id)
        self.assertEqual(row["status"], "corrigindo")
        db.finish_correction(
            correction_id,
            note=600,
            scores={"C1": 120, "C2": 120, "C3": 120, "C4": 120, "C5": 120},
            explanation="Boa.",
            errors="",
            source_text="Texto da redação.",
            score_mode="llm",
            model="modelo",
            provider="localhost",
            prompt_version="review-v2",
            duration_ms=1000,
            tokens_in=10,
            tokens_out=20,
            truncated=False,
        )
        row = db.get_correction(correction_id)
        self.assertEqual(row["status"], "corrigido")
        self.assertEqual(row["note_value"], 600)
        self.assertEqual(db.note_of(row), 600)
        self.assertEqual(db.scores_of(row)["C1"], 120)
        self.assertEqual(row["source_text"], "Texto da redação.")
        self.assertEqual(row["model"], "modelo")

    def test_recover_interrupted_jobs(self):
        correction_id = db.create_correction("a.pdf", "a.pdf", "Tema")
        self.assertEqual(db.pending_count(), 1)
        changed = db.recover_interrupted()
        self.assertEqual(changed, 1)
        row = db.get_correction(correction_id)
        self.assertEqual(row["status"], "interrompido")
        self.assertIn("reinício", row["errors"])
        self.assertEqual(db.pending_count(), 0)

    def test_mark_running_clears_previous_result(self):
        correction_id = db.create_correction("a.pdf", "a.pdf", "Tema")
        db.finish_correction(
            correction_id,
            note=200,
            scores={"C1": 40, "C2": 40, "C3": 40, "C4": 40, "C5": 40},
            explanation="ok",
            errors="",
            source_text="texto",
            score_mode="llm",
            model="m",
            provider="p",
            prompt_version="v",
            duration_ms=1,
            tokens_in=1,
            tokens_out=1,
            truncated=False,
        )
        self.assertTrue(db.mark_running(correction_id))
        row = db.get_correction(correction_id)
        self.assertEqual(row["status"], "corrigindo")
        self.assertEqual(row["scores"], "{}")
        self.assertEqual(row["source_text"], "")
        self.assertFalse(db.mark_running(correction_id))

    def test_pagination_and_status_filter(self):
        for index in range(25):
            db.create_correction(f"{index}.txt", f"{index}.txt", "Tema")
        rows, total = db.recent_corrections(1, 20)
        self.assertEqual(total, 25)
        self.assertEqual(len(rows), 20)
        rows, total = db.recent_corrections(2, 20)
        self.assertEqual(total, 25)
        self.assertEqual(len(rows), 5)
        target_id = rows[0]["id"]
        db.finish_correction(
            target_id,
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
        rows, total = db.recent_corrections(1, 20, status="corrigido")
        self.assertEqual(total, 1)
        self.assertEqual(rows[0]["id"], target_id)

    def test_delete_returns_stored_name(self):
        correction_id = db.create_correction("a.pdf", "a.pdf", "Tema")
        self.assertEqual(db.delete_correction(correction_id), "a.pdf")
        self.assertIsNone(db.get_correction(correction_id))

    def test_settings_upsert(self):
        db.save_settings({"base_url": "http://x/v1", "custom": "1"})
        settings = db.get_settings()
        self.assertEqual(settings["base_url"], "http://x/v1")
        self.assertEqual(settings["custom"], "1")
        self.assertEqual(settings["use_bert"], "0")

    def test_init_is_idempotent(self):
        db.init_db()
        db.init_db()
        names = [row["name"] for row in db.query("PRAGMA table_info(corrections)")]
        self.assertIn("scores", names)
        self.assertIn("source_text", names)
        self.assertIn("note_value", names)

    def test_scores_of_invalid_json(self):
        correction_id = db.create_correction("a.pdf", "a.pdf", "Tema")
        db.execute(
            "UPDATE corrections SET scores = ? WHERE id = ?",
            ("{invalido", correction_id),
        )
        row = db.get_correction(correction_id)
        self.assertEqual(db.scores_of(row), {})


if __name__ == "__main__":
    unittest.main()
