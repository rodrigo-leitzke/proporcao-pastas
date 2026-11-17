"""Testes do caso de uso com dados de cache."""
import os
import tempfile
import unittest

from proporcao_pastas.application.analyze_folder import AnalyzeFolder
from proporcao_pastas.infrastructure.cache_storage import SqliteCacheStorage
from proporcao_pastas.infrastructure.file_system import FileSystemScanner


class TestAnalyzeFolderComCache(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.raiz = os.path.join(self.dir.name, "raiz")
        os.makedirs(os.path.join(self.raiz, "sub"))
        with open(os.path.join(self.raiz, "sub", "a.bin"), "wb") as f:
            f.write(b"x" * 100)
        self.storage = SqliteCacheStorage(os.path.join(self.dir.name, "cache.db"))
        self.scanner = FileSystemScanner(storage=self.storage)
        self.caso = AnalyzeFolder(self.scanner)

    def tearDown(self):
        self.storage.close()
        self.dir.cleanup()

    def test_execute_traz_dados_do_cache(self):
        analise = self.caso.execute(self.raiz, self.raiz, False)
        self.assertEqual(analise.total, 100)
        self.assertIsNotNone(analise.cache_updated_at)
        self.assertIsNotNone(analise.global_cache_updated_at)
        self.assertFalse(analise.is_outdated)

    def test_refresh_revarre_e_devolve_total_novo(self):
        self.caso.execute(self.raiz, self.raiz, False)
        with open(os.path.join(self.raiz, "sub", "b.bin"), "wb") as f:
            f.write(b"y" * 50)
        analise = self.caso.refresh(os.path.join(self.raiz, "sub"), self.raiz, True)
        self.assertEqual(analise.total, 150)
        self.assertFalse(analise.is_outdated)
        self.assertEqual(self.storage.get_folder(self.raiz).tamanho, 150)

    def test_refresh_repassa_o_progresso(self):
        self.caso.execute(self.raiz, self.raiz, False)
        vistos = []
        self.caso.refresh(self.raiz, self.raiz, False, progresso=vistos.append)
        self.assertTrue(vistos)
