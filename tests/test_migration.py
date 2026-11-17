from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from src import db, paths


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.old = {
            "DATA_DIR": paths.DATA_DIR,
            "UPLOAD_DIR": paths.UPLOAD_DIR,
            "DB_PATH": paths.DB_PATH,
            "ENV_PATH": paths.ENV_PATH,
            "SECRET_PATH": paths.SECRET_PATH,
        }
        self.tmp = tempfile.TemporaryDirectory()
        paths.configure(data_dir=Path(self.tmp.name))

    def tearDown(self):
        paths.configure(data_dir=self.old["DATA_DIR"])
        paths.UPLOAD_DIR = self.old["UPLOAD_DIR"]
        paths.DB_PATH = self.old["DB_PATH"]
        paths.ENV_PATH = self.old["ENV_PATH"]
        paths.SECRET_PATH = self.old["SECRET_PATH"]
        self.tmp.cleanup()

    def test_old_database_is_migrated(self):
        conn = sqlite3.connect(paths.DB_PATH)
        conn.executescript(
            """
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                theme TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pendente',
                note TEXT NOT NULL DEFAULT '',
                explanation TEXT NOT NULL DEFAULT '',
                errors TEXT NOT NULL DEFAULT ''
            );
            INSERT INTO settings (key, value) VALUES ('api_key_hash', 'abc');
            INSERT INTO corrections
                (filename, stored_name, theme, created_at, status, note,
                 explanation, errors)
            VALUES ('a.txt', 'a.txt', 'Tema', '01/01/2026 10:00', 'corrigido',
                    '840', 'antiga', '');
            """
        )
        conn.commit()
        conn.close()

        db.init_db()
        row = db.query("SELECT * FROM corrections")[0]
        self.assertEqual(row["note_value"], 840)
        self.assertEqual(row["scores"], "{}")
        keys = {item["key"] for item in db.query("SELECT key FROM settings")}
        self.assertNotIn("api_key_hash", keys)
        self.assertIn("base_url", keys)


if __name__ == "__main__":
    unittest.main()
