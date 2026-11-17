from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from src import bert_notas


class BertValidationTests(unittest.TestCase):
    def setUp(self):
        self._old = os.environ.get("BERT_DIR")
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        os.environ["BERT_DIR"] = str(self.dir)

    def tearDown(self):
        if self._old is None:
            os.environ.pop("BERT_DIR", None)
        else:
            os.environ["BERT_DIR"] = self._old
        self.tmp.cleanup()

    def write_config(self, **extra):
        config = {"architectures": ["BertForMaskedLM"], **extra}
        (self.dir / "config.json").write_text(json.dumps(config), encoding="utf-8")

    def test_missing_dir(self):
        os.environ["BERT_DIR"] = str(self.dir / "nao-existe")
        self.assertIn("não foi encontrada", bert_notas.motivo_indisponivel())

    def test_base_model_is_rejected(self):
        self.write_config()
        self.assertFalse(bert_notas._ajustado())
        self.assertIn("BERTimbau base", bert_notas.motivo_indisponivel())

    def test_two_outputs_rejected(self):
        self.write_config(
            architectures=["BertForSequenceClassification"], num_labels=2
        )
        self.assertFalse(bert_notas._ajustado())
        self.assertIn("5 saídas", bert_notas.motivo_indisponivel())

    def test_five_outputs_accepted(self):
        self.write_config(
            architectures=["BertForSequenceClassification"], num_labels=5
        )
        self.assertTrue(bert_notas._ajustado())
        reason = bert_notas.motivo_indisponivel()
        if reason:
            # Em ambientes sem torch/transformers, o motivo correto é dependência.
            self.assertIn("dependências", reason)

    def test_id2label_accepts_five_competencies(self):
        self.write_config(
            architectures=["BertForSequenceClassification"],
            id2label={"0": "C1", "1": "C2", "2": "C3", "3": "C4", "4": "C5"},
        )
        self.assertTrue(bert_notas._ajustado())

    def test_wrong_id2label_rejected(self):
        self.write_config(
            architectures=["BertForSequenceClassification"],
            num_labels=5,
            id2label={"0": "A", "1": "B", "2": "C", "3": "D", "4": "E"},
        )
        self.assertFalse(bert_notas._ajustado())
        self.assertFalse(bert_notas._rotulos_validos(bert_notas._config()))
        self.assertIn("5 saídas", bert_notas.motivo_indisponivel())

    def test_default_labels_accepted(self):
        self.write_config(
            architectures=["BertForSequenceClassification"],
            id2label={
                "0": "LABEL_0",
                "1": "LABEL_1",
                "2": "LABEL_2",
                "3": "LABEL_3",
                "4": "LABEL_4",
            },
        )
        self.assertTrue(bert_notas._ajustado())

    def test_invalid_json(self):
        (self.dir / "config.json").write_text("{", encoding="utf-8")
        self.assertFalse(bert_notas._ajustado())
        self.assertIn("config.json", bert_notas.motivo_indisponivel())


if __name__ == "__main__":
    unittest.main()
