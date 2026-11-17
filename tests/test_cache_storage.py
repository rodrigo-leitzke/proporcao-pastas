"""Testes do armazenamento do cache em SQLite."""
import os
import tempfile
import unittest

from proporcao_pastas.infrastructure.cache_storage import (
    CachedFile,
    CachedFolder,
    SqliteCacheStorage,
)


def pasta(path, parent=None, tamanho=100, **extra):
    base = dict(
        path=path,
        parent=parent,
        tamanho=tamanho,
        arquivos=2,
        subpastas=0,
        maior_nome="a.bin",
        maior_tam=90,
        maior_direct_nome="a.bin",
        maior_direct_tam=90,
        modificado_em=1000.0,
        criado_em=900.0,
        permissoes="drwxr-xr-x",
        cache_updated_at=5000.0,
        arquivos_truncados=0,
        soma_truncados=0,
    )
    base.update(extra)
    return CachedFolder(**base)


class TestSqliteCacheStorage(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.storage = SqliteCacheStorage(os.path.join(self.dir.name, "cache.db"))

    def tearDown(self):
        self.storage.close()
        self.dir.cleanup()

    def test_ida_e_volta_de_pasta(self):
        self.storage.put_folder(pasta("/a"), [])
        lido = self.storage.get_folder("/a")
        self.assertEqual(lido.tamanho, 100)
        self.assertEqual(lido.maior_nome, "a.bin")
        self.assertEqual(lido.cache_updated_at, 5000.0)

    def test_pasta_inexistente_retorna_none(self):
        self.assertIsNone(self.storage.get_folder("/nao/existe"))

    def test_put_folder_substitui(self):
        self.storage.put_folder(pasta("/a"), [])
        self.storage.put_folder(pasta("/a", tamanho=777), [])
        self.assertEqual(self.storage.get_folder("/a").tamanho, 777)

    def test_arquivos_sao_gravados_e_substituidos(self):
        arquivos = [CachedFile("x.pdf", 10, 1.0, 2.0, "-rw-r--r--")]
        self.storage.put_folder(pasta("/a"), arquivos)
        self.assertEqual([f.nome for f in self.storage.get_files("/a")], ["x.pdf"])
        self.storage.put_folder(pasta("/a"), [CachedFile("y.pdf", 20, 1.0, 2.0, "-rw-r--r--")])
        self.assertEqual([f.nome for f in self.storage.get_files("/a")], ["y.pdf"])

    def test_get_subfolders_usa_parent(self):
        self.storage.put_folder(pasta("/a"), [])
        self.storage.put_folder(pasta("/a/b", parent="/a", tamanho=10), [])
        self.storage.put_folder(pasta("/a/c", parent="/a", tamanho=20), [])
        self.storage.put_folder(pasta("/outro", parent=None), [])
        nomes = sorted(s.path for s in self.storage.get_subfolders("/a"))
        self.assertEqual(nomes, ["/a/b", "/a/c"])

    def test_delete_subtree_remove_descendentes_e_arquivos(self):
        self.storage.put_folder(pasta("/a"), [CachedFile("raiz.txt", 1, 1.0, 1.0, "-rw-")])
        self.storage.put_folder(pasta("/a/b", parent="/a"), [CachedFile("f.txt", 1, 1.0, 1.0, "-rw-")])
        self.storage.put_folder(pasta("/a/b/c", parent="/a/b"), [])
        self.storage.put_folder(pasta("/z", parent=None), [])
        self.storage.delete_subtree("/a")
        self.assertIsNone(self.storage.get_folder("/a"))
        self.assertIsNone(self.storage.get_folder("/a/b"))
        self.assertIsNone(self.storage.get_folder("/a/b/c"))
        self.assertEqual(self.storage.get_files("/a/b"), [])
        self.assertIsNotNone(self.storage.get_folder("/z"))

    def test_nome_com_curinga_de_like_nao_afeta_vizinhos(self):
        self.storage.put_folder(pasta("/a%b", parent=None), [])
        self.storage.put_folder(pasta("/a_c", parent=None), [])
        self.storage.delete_subtree("/a%b")
        self.assertIsNone(self.storage.get_folder("/a%b"))
        self.assertIsNotNone(self.storage.get_folder("/a_c"))

    def test_meta_ida_e_volta(self):
        self.assertIsNone(self.storage.get_meta("roots"))
        self.storage.set_meta("roots", "C:\\")
        self.assertEqual(self.storage.get_meta("roots"), "C:\\")
        self.storage.set_meta("roots", "D:\\")
        self.assertEqual(self.storage.get_meta("roots"), "D:\\")

    def test_ultima_atualizacao_global_e_o_maior_cache_updated_at(self):
        self.assertIsNone(self.storage.ultima_atualizacao_global())
        self.storage.put_folder(pasta("/a", cache_updated_at=10.0), [])
        self.storage.put_folder(pasta("/b", cache_updated_at=99.0), [])
        self.assertEqual(self.storage.ultima_atualizacao_global(), 99.0)

    def test_reabrir_banco_preserva_dados(self):
        self.storage.put_folder(pasta("/a"), [])
        caminho = self.storage.db_path
        self.storage.close()
        self.storage = SqliteCacheStorage(caminho)
        self.assertEqual(self.storage.get_folder("/a").tamanho, 100)

    def test_delete_subtree_com_parent_autorreferente_nao_trava(self):
        self.storage.put_folder(pasta("/a", parent="/a"), [])
        self.storage.delete_subtree("/a")
        self.assertIsNone(self.storage.get_folder("/a"))
