"""Testes da varredura total opcional."""
import os
import tempfile
import unittest

from proporcao_pastas.infrastructure.cache_storage import SqliteCacheStorage
from proporcao_pastas.infrastructure.file_system import FileSystemScanner


class TestMapearRaizes(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.raiz = os.path.join(self.dir.name, "raiz")
        for nome in ("a", "b", "c"):
            os.makedirs(os.path.join(self.raiz, nome))
            with open(os.path.join(self.raiz, nome, "f.bin"), "wb") as f:
                f.write(b"x" * 10)
        self.storage = SqliteCacheStorage(os.path.join(self.dir.name, "cache.db"))
        self.scanner = FileSystemScanner(storage=self.storage)

    def tearDown(self):
        self.storage.close()
        self.dir.cleanup()

    def test_mapeia_e_grava_todas_as_pastas(self):
        total = self.scanner.mapear_raizes([self.raiz])
        self.assertEqual(total, 3)
        self.assertEqual(self.storage.get_folder(self.raiz).tamanho, 30)
        self.assertIsNotNone(self.storage.get_folder(os.path.join(self.raiz, "a")))

    def test_informa_progresso(self):
        vistos = []
        self.scanner.mapear_raizes([self.raiz], progresso=lambda p, i, n: vistos.append((p, i, n)))
        self.assertEqual(len(vistos), 3)
        self.assertEqual(vistos[-1][1:], (3, 3))

    def test_respeita_cancelamento(self):
        vistos = []
        self.scanner.mapear_raizes(
            [self.raiz],
            progresso=lambda p, i, n: vistos.append(p),
            cancelado=lambda: len(vistos) >= 1,
        )
        self.assertEqual(len(vistos), 1)
