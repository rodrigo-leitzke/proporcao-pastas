"""Testes da varredura total opcional."""
import os
import tempfile
import unittest
from unittest import mock

from proporcao_pastas.infrastructure import file_system
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

    def encher(self, pasta, quantas=5):
        """Cria subpastas com conteudo dentro de uma pasta de primeiro nivel."""
        caminhos = []
        for i in range(quantas):
            sub = os.path.join(pasta, "s%d" % i)
            os.makedirs(sub)
            with open(os.path.join(sub, "f.bin"), "wb") as f:
                f.write(b"y" * 100)
            caminhos.append(sub)
        return caminhos

    def test_cancela_dentro_de_uma_pasta_de_primeiro_nivel(self):
        alvo = os.path.join(self.raiz, "a")
        subs = self.encher(alvo)
        chamadas = []

        def cancelado():
            chamadas.append(1)
            return len(chamadas) > 4  # cancela no meio das entradas de "a"

        feitos = self.scanner.mapear_raizes([self.raiz], cancelado=cancelado)
        self.assertEqual(feitos, 0)  # "a" nao chegou ao fim
        medidas = [s for s in subs if self.storage.get_folder(s) is not None]
        self.assertLess(len(medidas), len(subs))  # parou no meio da recursao
        # total truncado nao pode ir para o disco
        self.assertIsNone(self.storage.get_folder(alvo))
        self.assertIsNone(self.storage.get_folder(self.raiz))

    def test_cancelamento_nao_deixa_total_truncado_no_cache_de_memoria(self):
        alvo = os.path.join(self.raiz, "a")
        self.encher(alvo)
        chamadas = []

        def cancelado():
            chamadas.append(1)
            return len(chamadas) > 4

        self.scanner.mapear_raizes([self.raiz], cancelado=cancelado)
        # a mesma instancia nao pode devolver o total truncado de "a"
        self.assertEqual(self.scanner.stats(alvo).tamanho, 510)

    def test_progresso_vem_de_dentro_da_recursao(self):
        subs = self.encher(os.path.join(self.raiz, "a"))
        vistos = []
        with mock.patch.object(file_system, "PASTAS_POR_AVISO", 1):
            self.scanner.mapear_raizes(
                [self.raiz], progresso=lambda p, i, n: vistos.append(p)
            )
        self.assertTrue(set(subs) & set(vistos))
