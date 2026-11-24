from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src import bench, grading
from src.bench.__main__ import parse_args
from tests import support


class BenchTests(unittest.TestCase):
    def setUp(self):
        support.reset()

    def test_parse_args_accepts_debug_and_accented_command(self):
        args = parse_args(["--debug", "benchredação", "bert"])
        self.assertTrue(args.debug)
        self.assertEqual(args.mode, "bert")
        self.assertIsNone(args.limit)

        args_ai = parse_args(["--debug", "benchredacao", "bert_ai", "-n", "3"])
        self.assertTrue(args_ai.debug)
        self.assertEqual(args_ai.mode, "bert_ai")
        self.assertEqual(args_ai.limit, 3)

    def test_load_essay_br_and_stratified_sampling(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "prompts.csv").write_text(
                "id,title,description,category\n"
                "1,Tema Um,[],sociedade\n"
                "2,Tema Dois,[],educacao\n",
                encoding="utf-8",
            )
            (root / "extended_essay-br.csv").write_text(
                'prompt,title,essay,c1,c2,c3,c4,c5,score\n'
                '1,T1,"[\'Paragrafo 1.\', \'Paragrafo 2.\']",40,40,40,40,40,200\n'
                '2,T2,"[\'Texto bom.\']",200,200,160,200,160,920\n'
                '1,T3,"[\'Texto medio.\']",120,120,120,120,120,600\n',
                encoding="utf-8",
            )
            samples = bench.load_samples(
                root / "extended_essay-br.csv", root / "prompts.csv"
            )
            self.assertEqual(len(samples), 3)
            self.assertEqual(samples[0].theme, "Tema Um")
            self.assertEqual(samples[0].text, "Paragrafo 1.\n\nParagrafo 2.")
            picked = bench.sample_stratified(samples, 2, seed=7)
            self.assertEqual(len(picked), 2)
            self.assertLess(picked[0].total, picked[1].total)

    def test_qwk_and_summary(self):
        self.assertAlmostEqual(
            bench.quadratic_weighted_kappa([40, 120, 200], [40, 120, 200]), 1.0
        )
        records = [
            bench.BenchRecord(
                sample_id="1",
                theme="Tema",
                true_scores={"C1": 120, "C2": 120, "C3": 120, "C4": 120, "C5": 120},
                pred_scores={"C1": 160, "C2": 120, "C3": 120, "C4": 120, "C5": 80},
                true_total=600,
                pred_total=600,
                duration_ms=250,
            )
        ]
        summary = bench.summarize(records)
        self.assertEqual(summary["TOTAL"]["mae"], 0.0)
        self.assertEqual(summary["C1"]["bias"], 40.0)
        text = bench.format_summary("bert", records, model_info="BERT", bert_limit=2048)
        self.assertIn("=== Resumo benchredação (bert) ===", text)

    def test_run_benchmark_bert_and_bert_ai_with_csv(self):
        support.configure_models("modelo-teste")
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "valid.csv"
            csv_path.write_text(
                "id,tema,texto,C1,C2,C3,C4,C5\n"
                "10,Tema Teste,Redação completa de exemplo.,120,160,120,120,160\n",
                encoding="utf-8",
            )
            fake_scores = {"C1": 120, "C2": 160, "C3": 120, "C4": 120, "C5": 120}
            with mock.patch("src.bert_notas.motivo_indisponivel", return_value=None):
                with mock.patch(
                    "src.bert_notas.estimar", return_value=(fake_scores, False)
                ):
                    records = bench.run_benchmark(
                        mode="bert",
                        limit=1,
                        csv_path=csv_path,
                        debug=True,
                        allow_download=False,
                    )
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].pred_total, 640)

            fake_review = grading.ReviewResult(
                note=640,
                scores=fake_scores,
                explanation="ok",
                errors="",
                source_text="Redação completa de exemplo.",
                score_mode="bert+llm",
                model="modelo-teste",
                provider="localhost",
                prompt_version=grading.PROMPT_VERSION_HYBRID,
                duration_ms=500,
                tokens_in=50,
                tokens_out=80,
            )
            with mock.patch("src.bert_notas.motivo_indisponivel", return_value=None):
                with mock.patch.object(grading, "review", return_value=fake_review) as rev:
                    records_ai = bench.run_benchmark(
                        mode="bert_ai",
                        limit=1,
                        csv_path=csv_path,
                        debug=True,
                        allow_download=False,
                    )
            self.assertEqual(len(records_ai), 1)
            self.assertEqual(records_ai[0].tokens_in, 50)
            self.assertEqual(rev.call_args.args[2]["use_bert"], "1")


if __name__ == "__main__":
    unittest.main()
