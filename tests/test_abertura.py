"""Testes da decisao de analisar (ou nao) a pasta inicial ao abrir.

O ambiente de teste nao tem tela, entao nao da para construir a App de verdade
(tk.Tk() falha sem display). A decisao de abertura foi extraida para
deve_analisar_na_abertura justamente para poder ser testada sem janela.
"""
import inspect
import os
import sqlite3
import tempfile
import unittest
from unittest import mock

from proporcao_pastas.infrastructure.cache_storage import SqliteCacheStorage
from proporcao_pastas.infrastructure.file_system import FileSystemScanner
from proporcao_pastas.presentation import tk_app
from proporcao_pastas.presentation.tk_app import App, deve_analisar_na_abertura


class TestDeveAnalisarNaAbertura(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.raiz = os.path.join(self.dir.name, "raiz")
        os.makedirs(self.raiz)
        with open(os.path.join(self.raiz, "a.bin"), "wb") as f:
            f.write(b"x" * 10)
        self.storage = SqliteCacheStorage(os.path.join(self.dir.name, "cache.db"))

    def tearDown(self):
        self.storage.close()
        self.dir.cleanup()

    def test_raiz_fora_do_cache_nao_analisa(self):
        self.assertFalse(deve_analisar_na_abertura(self.raiz, self.storage))

    def test_raiz_em_cache_analisa(self):
        FileSystemScanner(storage=self.storage).stats(self.raiz)
        self.assertTrue(deve_analisar_na_abertura(self.raiz, self.storage))

    def test_sem_storage_nao_analisa(self):
        self.assertFalse(deve_analisar_na_abertura(self.raiz, None))

    def test_app_recebe_as_raizes_no_construtor(self):
        # garante que main() nao precisa chamar definir_raizes depois de abrir,
        # o que montaria a arvore (e dispararia a analise) duas vezes
        self.assertIn("raizes", inspect.signature(App.__init__).parameters)


class TestAbrirCache(unittest.TestCase):
    def test_cache_que_nao_abre_vira_aviso_e_storage_none(self):
        def explode(_caminho):
            raise sqlite3.DatabaseError("file is not a database")

        with mock.patch.object(tk_app, "SqliteCacheStorage", explode):
            storage, aviso = tk_app.abrir_cache()
        self.assertIsNone(storage)
        self.assertIn("Cache desativado", aviso)
        # sem storage o scanner continua medindo na hora, e a App abre parada
        self.assertFalse(deve_analisar_na_abertura("/qualquer", storage))
        self.assertEqual(FileSystemScanner(storage=storage).ultima_atualizacao_global(), None)

    def test_cache_que_abre_nao_tem_aviso(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "cache.db")
            with mock.patch.object(tk_app, "caminho_padrao_cache", lambda: caminho):
                storage, aviso = tk_app.abrir_cache()
            try:
                self.assertEqual(aviso, "")
                self.assertIsNotNone(storage)
            finally:
                storage.close()


class ArvoreFalsa:
    """So o que selecionar() usa da Treeview."""

    def __init__(self, selecao):
        self.selecao = tuple(selecao)

    def selection(self):
        return self.selecao


class TestSelecionarIgnoraSelecaoAutomatica(unittest.TestCase):
    """Exercita o App.selecionar de verdade, com dublês no lugar dos widgets."""

    def montar(self, selecao, ignorar):
        app = App.__new__(App)  # sem __init__: nao da para criar janela sem tela
        app.tree = ArvoreFalsa(selecao)
        app.nos = {"i1": "/raiz", "i2": "/raiz/sub"}
        app.ignorar_selecao = ignorar
        app.analisadas = []
        app.analisar = lambda path, **kwargs: app.analisadas.append(path)
        return app

    def test_selecao_automatica_da_abertura_nao_analisa(self):
        app = self.montar(("i1",), "i1")
        App.selecionar(app, None)
        self.assertEqual(app.analisadas, [])
        self.assertIsNone(app.ignorar_selecao)

    def test_abertura_com_cache_analisa(self):
        app = self.montar(("i1",), None)
        App.selecionar(app, None)
        self.assertEqual(app.analisadas, ["/raiz"])

    def test_clique_seguinte_do_usuario_analisa(self):
        app = self.montar(("i1",), "i1")
        App.selecionar(app, None)
        app.tree.selecao = ("i2",)
        App.selecionar(app, None)
        self.assertEqual(app.analisadas, ["/raiz/sub"])

    def test_clique_em_outra_pasta_nao_e_engolido(self):
        # se o evento automatico nunca chegasse, o clique do usuario ainda vale
        app = self.montar(("i2",), "i1")
        App.selecionar(app, None)
        self.assertEqual(app.analisadas, ["/raiz/sub"])
