from __future__ import annotations

import unittest
from unittest import mock

from src import db, grading, paths, worker
from tests import support


class WorkerTests(unittest.TestCase):
    def setUp(self):
        support.reset()
        support.configure_models()

    def _create_text_correction(self) -> tuple[int, str]:
        stored = "arquivo.txt"
        (paths.UPLOAD_DIR / stored).write_text("Redação de teste.", encoding="utf-8")
        correction_id = db.create_correction("arquivo.txt", stored, "Tema")
        return correction_id, stored

    def test_run_correction_success(self):
        correction_id, stored = self._create_text_correction()
        result = grading.ReviewResult(
            note=400,
            scores={"C1": 80, "C2": 80, "C3": 80, "C4": 80, "C5": 80},
            explanation="ok",
            errors="",
            source_text="Redação de teste.",
            score_mode="llm",
            model="fake",
            provider="localhost",
            prompt_version="review-v2",
            duration_ms=10,
            tokens_in=1,
            tokens_out=1,
        )
        with mock.patch.object(grading, "obtain_text", return_value="Redação de teste."):
            with mock.patch.object(grading, "review", return_value=result):
                worker.run_correction(correction_id, "Tema", stored)
        row = db.get_correction(correction_id)
        self.assertEqual(row["status"], "corrigido")
        self.assertEqual(row["note_value"], 400)
        self.assertEqual(row["source_text"], "Redação de teste.")

    def test_run_correction_failure_marks_error(self):
        correction_id, stored = self._create_text_correction()
        with mock.patch.object(
            grading, "obtain_text", side_effect=grading.GradingError("falhou")
        ):
            worker.run_correction(correction_id, "Tema", stored)
        row = db.get_correction(correction_id)
        self.assertEqual(row["status"], "erro")
        self.assertIn("falhou", row["errors"])

    def test_missing_file_marks_error(self):
        correction_id = db.create_correction("sumiu.txt", "sumiu.txt", "Tema")
        worker.run_correction(correction_id, "Tema", "sumiu.txt")
        row = db.get_correction(correction_id)
        self.assertEqual(row["status"], "erro")
        self.assertIn("não foi encontrado", row["errors"])


if __name__ == "__main__":
    unittest.main()
