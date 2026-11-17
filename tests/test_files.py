from __future__ import annotations

import io
import unittest

from werkzeug.datastructures import FileStorage

from src import files, paths
from tests import support


def storage(data: bytes, filename: str, content_type: str = "application/octet-stream"):
    return FileStorage(stream=io.BytesIO(data), filename=filename, content_type=content_type)


class FileTests(unittest.TestCase):
    def setUp(self):
        support.reset()

    def test_text_upload_and_read(self):
        stored, kind = files.validate_and_store(
            storage("Olá, ação e coração.".encode("utf-8"), "redacao.txt", "text/plain"),
            "redacao.txt",
        )
        self.assertEqual(kind, "text")
        self.assertTrue((paths.UPLOAD_DIR / stored).exists())
        self.assertEqual(files.read_text(paths.UPLOAD_DIR / stored), "Olá, ação e coração.")

    def test_pdf_magic_required(self):
        stored, kind = files.validate_and_store(
            storage(b"%PDF-1.4\nconteudo", "redacao.pdf", "application/pdf"),
            "redacao.pdf",
        )
        self.assertEqual(kind, "pdf")
        self.assertTrue(stored.endswith(".pdf"))

        with self.assertRaises(files.UploadError):
            files.validate_and_store(
                storage(b"nao e pdf", "falso.pdf", "application/pdf"), "falso.pdf"
            )

    def test_image_magic_and_canonical_suffix(self):
        png = b"\x89PNG\r\n\x1a\n" + b"0" * 20
        stored, kind = files.validate_and_store(
            storage(png, "foto.jpg", "image/jpeg"), "foto.jpg"
        )
        self.assertEqual(kind, "image")
        self.assertTrue(stored.endswith(".png"))

    def test_webp_supported(self):
        webp = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"0" * 20
        stored, kind = files.validate_and_store(
            storage(webp, "foto.webp", "image/webp"), "foto.webp"
        )
        self.assertEqual(kind, "image")
        self.assertTrue(stored.endswith(".webp"))

    def test_unsupported_extension(self):
        with self.assertRaises(files.UploadError):
            files.validate_and_store(
                storage(b"#!/bin/sh", "script.sh", "text/plain"), "script.sh"
            )

    def test_empty_file(self):
        with self.assertRaises(files.UploadError):
            files.validate_and_store(
                storage(b"", "vazio.txt", "text/plain"), "vazio.txt"
            )

    def test_invalid_utf8_text(self):
        with self.assertRaises(files.UploadError):
            files.validate_and_store(
                storage(b"\xff\xfe\x00", "binario.txt", "text/plain"), "binario.txt"
            )

    def test_save_text(self):
        stored = files.save_text("conteúdo")
        self.assertTrue((paths.UPLOAD_DIR / stored).exists())
        self.assertEqual(files.kind_from_name(stored), "text")

    def test_kind_from_name(self):
        self.assertEqual(files.kind_from_name("a.pdf"), "pdf")
        self.assertEqual(files.kind_from_name("a.webp"), "image")
        self.assertEqual(files.kind_from_name("a.txt"), "text")

    def test_size_limit(self):
        old = paths.MAX_UPLOAD_BYTES
        paths.MAX_UPLOAD_BYTES = 4
        try:
            with self.assertRaises(files.UploadError):
                files.validate_and_store(
                    storage(b"12345", "a.txt", "text/plain"), "a.txt"
                )
        finally:
            paths.MAX_UPLOAD_BYTES = old


if __name__ == "__main__":
    unittest.main()
