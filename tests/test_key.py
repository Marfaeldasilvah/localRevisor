from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path

from dotenv import dotenv_values

from src import paths, secrets_store


class KeyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_env = paths.ENV_PATH
        self.old_secret = paths.SECRET_PATH
        paths.configure(env_path=Path(self.tmp.name) / ".env")
        paths.SECRET_PATH = Path(self.tmp.name) / ".secret"
        os.environ.pop("OPENAI_API_KEY", None)

    def tearDown(self):
        paths.ENV_PATH = self.old_env
        paths.SECRET_PATH = self.old_secret
        os.environ.pop("OPENAI_API_KEY", None)
        self.tmp.cleanup()

    def test_save_and_load_key(self):
        persisted, _ = secrets_store.save_api_key("abc#123")
        self.assertTrue(persisted)
        self.assertTrue(secrets_store.key_configured())
        values = dotenv_values(paths.ENV_PATH)
        self.assertEqual(values["OPENAI_API_KEY"], "abc#123")
        mode = stat.S_IMODE(paths.ENV_PATH.stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_remove_key(self):
        secrets_store.save_api_key("minha-chave")
        persisted, _ = secrets_store.remove_api_key()
        self.assertTrue(persisted)
        self.assertFalse(secrets_store.key_configured())
        self.assertNotIn("OPENAI_API_KEY", paths.ENV_PATH.read_text())
        self.assertFalse(os.environ.get("OPENAI_API_KEY"))

    def test_reject_whitespace(self):
        with self.assertRaises(ValueError):
            secrets_store.save_api_key("chave com espaço")

    def test_preserves_other_env_lines(self):
        paths.ENV_PATH.write_text('OUTRA="coisa"\n', encoding="utf-8")
        secrets_store.save_api_key("k")
        text = paths.ENV_PATH.read_text()
        self.assertIn('OUTRA="coisa"', text)
        self.assertIn("OPENAI_API_KEY=", text)

    def test_secret_is_stable(self):
        first = secrets_store.load_or_create_secret()
        second = secrets_store.load_or_create_secret()
        self.assertEqual(first, second)
        self.assertGreaterEqual(len(first), 32)


if __name__ == "__main__":
    unittest.main()
