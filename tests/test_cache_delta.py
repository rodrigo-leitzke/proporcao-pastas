"""Testes da propagacao de delta e do recalculo do maior arquivo."""
import os
import tempfile
import unittest

from proporcao_pastas.infrastructure.cache_storage import CachedFolder, SqliteCacheStorage


def pasta(path, parent, tamanho, arquivos=1, subpastas=0,
          maior=("", 0), maior_direto=("", 0), quando=100.0):
    return CachedFolder(
        path=path, parent=parent, tamanho=tamanho, arquivos=arquivos, subpastas=subpastas,
        maior_nome=maior[0], maior_tam=maior[1],
        maior_direct_nome=maior_direto[0], maior_direct_tam=maior_direto[1],
        modificado_em=1.0, criado_em=1.0, permissoes="drwxr-xr-x",
        cache_updated_at=quando, arquivos_truncados=0, soma_truncados=0,
    )


class TestDelta(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.storage = SqliteCacheStorage(os.path.join(self.dir.name, "cache.db"))
        # /raiz (300) -> /raiz/docs (200) -> /raiz/docs/fac (50)
        self.storage.put_folder(pasta("/raiz", None, 300, arquivos=6, subpastas=2,
                                      maior=("filme.mp4", 180), maior_direto=("leia.txt", 10)), [])
        self.storage.put_folder(pasta("/raiz/docs", "/raiz", 200, arquivos=4, subpastas=1,
                                      maior=("filme.mp4", 180), maior_direto=("nota.pdf", 20)), [])
        self.storage.put_folder(pasta("/raiz/docs/fac", "/raiz/docs", 50, arquivos=2,
                                      maior=("filme.mp4", 180), maior_direto=("filme.mp4", 180)), [])

    def tearDown(self):
        self.storage.close()
        self.dir.cleanup()

    def test_ancestrais_do_mais_proximo_ao_mais_distante(self):
        self.assertEqual(
            self.storage.ancestrais("/raiz/docs/fac"), ["/raiz/docs", "/raiz"]
        )

    def test_ancestrais_para_quem_nao_tem_pai_em_cache(self):
        self.assertEqual(self.storage.ancestrais("/raiz"), [])

    def test_aplicar_delta_soma_nos_ancestrais(self):
        alterados = self.storage.aplicar_delta("/raiz/docs/fac", 25, 2, 1)
        self.assertEqual(alterados, ["/raiz/docs", "/raiz"])
        self.assertEqual(self.storage.get_folder("/raiz/docs").tamanho, 225)
        self.assertEqual(self.storage.get_folder("/raiz").tamanho, 325)
        self.assertEqual(self.storage.get_folder("/raiz/docs").arquivos, 6)
        self.assertEqual(self.storage.get_folder("/raiz").subpastas, 3)

    def test_aplicar_delta_nao_mexe_no_cache_updated_at_do_ancestral(self):
        self.storage.aplicar_delta("/raiz/docs/fac", 25, 0, 0)
        self.assertEqual(self.storage.get_folder("/raiz").cache_updated_at, 100.0)

    def test_aplicar_delta_nao_deixa_valor_negativo(self):
        self.storage.aplicar_delta("/raiz/docs/fac", -10_000, -100, -100)
        pai = self.storage.get_folder("/raiz/docs")
        self.assertEqual((pai.tamanho, pai.arquivos, pai.subpastas), (0, 0, 0))

    def test_recalcular_maior_quando_o_maior_desaparece(self):
        # o maior arquivo (filme.mp4, 180) sai de /raiz/docs/fac
        self.storage.put_folder(
            pasta("/raiz/docs/fac", "/raiz/docs", 5, maior=("resto.txt", 5),
                  maior_direto=("resto.txt", 5), quando=500.0),
            [],
        )
        self.storage.recalcular_maior("/raiz/docs")
        docs = self.storage.get_folder("/raiz/docs")
        self.assertEqual((docs.maior_nome, docs.maior_tam), ("nota.pdf", 20))
        self.storage.recalcular_maior("/raiz")
        raiz = self.storage.get_folder("/raiz")
        self.assertEqual((raiz.maior_nome, raiz.maior_tam), ("nota.pdf", 20))

    def test_recalcular_maior_prefere_subpasta_quando_ela_e_maior(self):
        self.storage.recalcular_maior("/raiz/docs")
        docs = self.storage.get_folder("/raiz/docs")
        self.assertEqual((docs.maior_nome, docs.maior_tam), ("filme.mp4", 180))

    def test_recalcular_maior_em_pasta_fora_do_cache_nao_quebra(self):
        self.storage.recalcular_maior("/nao/existe")

    def test_ancestrais_com_parent_autorreferente_nao_entra_em_loop(self):
        # linha corrompida: parent aponta para o proprio path
        self.storage.put_folder(
            pasta("/raiz/docs/fac", "/raiz/docs/fac", 50, maior=("filme.mp4", 180),
                  maior_direto=("filme.mp4", 180)),
            [],
        )
        self.assertEqual(self.storage.ancestrais("/raiz/docs/fac"), [])
