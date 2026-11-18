"""Testes dos ajustes feitos depois do review final da branch.

Cobrem tres pontos que o review apontou como residuais:
- o pai nao pode contar uma pasta que nao tem linha no banco (senao a contagem
  de subpastas dele cresce de novo no proximo "Atualizar cache" dessa pasta);
- medir a pasta pai so vale a pena quando ela nao e uma raiz de disco fora do
  cache, para a porcentagem nao custar uma varredura de disco inteira;
- o mapeamento pula alvos ja medidos e em dia, o que o torna retomavel.
"""
import os
import tempfile
import unittest
from unittest import mock

from proporcao_pastas.infrastructure import file_system
from proporcao_pastas.infrastructure.cache_storage import SqliteCacheStorage
from proporcao_pastas.infrastructure.file_system import FileSystemScanner


def escrever(caminho, conteudo):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "wb") as f:
        f.write(conteudo)


class BaseScanner(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.raiz = os.path.join(self.dir.name, "raiz")
        escrever(os.path.join(self.raiz, "a.bin"), b"x" * 100)
        self.storage = SqliteCacheStorage(os.path.join(self.dir.name, "cache.db"))
        self.scanner = FileSystemScanner(storage=self.storage)

    def tearDown(self):
        self.storage.close()
        self.dir.cleanup()


class TestPastaSemLinhaNoBanco(BaseScanner):
    def test_pasta_ilegivel_nao_entra_na_contagem_do_pai(self):
        sub = os.path.join(self.raiz, "sub")
        escrever(os.path.join(sub, "b.bin"), b"y" * 50)
        os.chmod(sub, 0o000)
        if os.access(sub, os.R_OK):  # root ignora permissao
            os.chmod(sub, 0o755)
            self.skipTest("rodando como root: nao da para tornar a pasta ilegivel")
        try:
            self.scanner.stats(self.raiz)
            linha = self.storage.get_folder(self.raiz)
            # a subpasta nao tem linha, entao nao conta no pai
            self.assertIsNone(self.storage.get_folder(sub))
            self.assertEqual(linha.subpastas, 0)
            self.assertEqual(linha.tamanho, 100)
        finally:
            os.chmod(sub, 0o755)

    def test_refresh_depois_de_ilegivel_nao_duplica_subpastas(self):
        sub = os.path.join(self.raiz, "sub")
        escrever(os.path.join(sub, "b.bin"), b"y" * 50)
        escrever(os.path.join(sub, "neta", "c.bin"), b"z" * 25)
        os.chmod(sub, 0o000)
        if os.access(sub, os.R_OK):
            os.chmod(sub, 0o755)
            self.skipTest("rodando como root: nao da para tornar a pasta ilegivel")
        try:
            self.scanner.stats(self.raiz)
        finally:
            os.chmod(sub, 0o755)
        self.scanner.refresh_folder(sub)
        linha = self.storage.get_folder(self.raiz)
        # verdade no disco: raiz tem sub + sub/neta = 2 subpastas, 175 bytes
        self.assertEqual(linha.subpastas, 2)
        self.assertEqual(linha.tamanho, 175)
        self.assertEqual(linha.arquivos, 3)


class TestPaiMensuravel(BaseScanner):
    def test_pasta_comum_sempre_vale_medir(self):
        self.assertTrue(self.scanner.pai_mensuravel(self.raiz))

    def test_raiz_fora_do_cache_nao_vale_medir(self):
        with mock.patch.object(file_system, "list_system_roots", lambda: [self.raiz]):
            self.assertFalse(self.scanner.pai_mensuravel(self.raiz))

    def test_raiz_em_cache_volta_a_valer(self):
        with mock.patch.object(file_system, "list_system_roots", lambda: [self.raiz]):
            self.scanner.stats(self.raiz)
            self.assertTrue(self.scanner.pai_mensuravel(self.raiz))


class TestMapeamentoRetomavel(BaseScanner):
    def test_alvo_ja_medido_e_em_dia_nao_e_revarrido(self):
        alvo = os.path.join(self.raiz, "sub")
        escrever(os.path.join(alvo, "b.bin"), b"y" * 50)
        self.scanner.stats(alvo)
        antes = self.storage.get_folder(alvo).cache_updated_at
        feitos = self.scanner.mapear_raizes([self.raiz])
        self.assertEqual(feitos, 1)
        # mesma linha, nao uma medicao nova
        self.assertEqual(self.storage.get_folder(alvo).cache_updated_at, antes)

    def test_alvo_desatualizado_e_revarrido(self):
        alvo = os.path.join(self.raiz, "sub")
        escrever(os.path.join(alvo, "b.bin"), b"y" * 50)
        self.scanner.stats(alvo)
        antes = self.storage.get_folder(alvo).cache_updated_at
        escrever(os.path.join(alvo, "c.bin"), b"z" * 25)
        futuro = antes + 10
        os.utime(alvo, (futuro, futuro))
        self.scanner.clear_cache()
        self.scanner.mapear_raizes([self.raiz])
        linha = self.storage.get_folder(alvo)
        self.assertEqual(linha.tamanho, 75)
        self.assertGreater(linha.cache_updated_at, antes)
