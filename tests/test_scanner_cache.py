"""Testes da integracao entre o scanner e o cache persistente."""
import os
import tempfile
import time
import unittest

from proporcao_pastas.infrastructure.cache_storage import SqliteCacheStorage
from proporcao_pastas.infrastructure.file_system import FileSystemScanner


def escrever(caminho, conteudo):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "wb") as f:
        f.write(conteudo)


class TestScannerComCache(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.raiz = os.path.join(self.dir.name, "raiz")
        escrever(os.path.join(self.raiz, "a.bin"), b"x" * 100)
        escrever(os.path.join(self.raiz, "sub", "b.bin"), b"y" * 50)
        self.storage = SqliteCacheStorage(os.path.join(self.dir.name, "cache.db"))
        self.scanner = FileSystemScanner(storage=self.storage)

    def tearDown(self):
        self.storage.close()
        self.dir.cleanup()

    def test_stats_grava_no_banco(self):
        stats = self.scanner.stats(self.raiz)
        self.assertEqual(stats.tamanho, 150)
        gravado = self.storage.get_folder(self.raiz)
        self.assertIsNotNone(gravado)
        self.assertEqual(gravado.tamanho, 150)
        self.assertEqual(gravado.maior_nome, "a.bin")
        self.assertEqual(gravado.maior_direct_nome, "a.bin")

    def test_stats_grava_subpastas_com_parent(self):
        self.scanner.stats(self.raiz)
        sub = self.storage.get_folder(os.path.join(self.raiz, "sub"))
        self.assertEqual(sub.parent, self.raiz)
        self.assertEqual(sub.tamanho, 50)

    def test_segundo_scanner_le_do_banco_sem_tocar_o_disco(self):
        self.scanner.stats(self.raiz)
        outro = FileSystemScanner(storage=self.storage)
        # apaga o conteudo: se ler o disco, o tamanho cai
        os.remove(os.path.join(self.raiz, "a.bin"))
        self.assertEqual(outro.stats(self.raiz).tamanho, 150)
        self.assertIsNotNone(outro.stats(self.raiz).cache_updated_at)

    def test_children_vem_do_cache_e_mantem_metadados(self):
        self.scanner.stats(self.raiz)
        outro = FileSystemScanner(storage=self.storage)
        nomes = {i.nome: i for i in outro.children(self.raiz)}
        self.assertEqual(set(nomes), {"a.bin", "sub"})
        self.assertEqual(nomes["sub"].tamanho, 50)
        self.assertTrue(nomes["sub"].eh_pasta)
        self.assertEqual(nomes["a.bin"].tipo_detalhado, "Arq (.bin)")
        self.assertIsNotNone(nomes["sub"].cache_updated_at)

    def test_children_agrupa_arquivos_truncados_em_outros(self):
        for i in range(60):
            escrever(os.path.join(self.raiz, "muitos", "f%02d.bin" % i), b"z" * (i + 1))
        self.scanner.stats(os.path.join(self.raiz, "muitos"))
        outro = FileSystemScanner(storage=self.storage)
        itens = outro.children(os.path.join(self.raiz, "muitos"), max_items=8)
        self.assertEqual(len(itens), 8)
        outros = itens[-1]
        self.assertIsNone(outros.eh_pasta)
        total_disco = sum(range(1, 61))
        self.assertEqual(sum(i.tamanho for i in itens), total_disco)

    def test_sem_storage_funciona_como_antes(self):
        simples = FileSystemScanner()
        self.assertEqual(simples.stats(self.raiz).tamanho, 150)
        self.assertEqual(len(simples.children(self.raiz)), 2)

    def test_is_folder_outdated_quando_a_pasta_muda(self):
        self.scanner.stats(self.raiz)
        self.assertFalse(self.scanner.is_folder_outdated(self.raiz))
        time.sleep(0.01)
        escrever(os.path.join(self.raiz, "novo.bin"), b"n")
        os.utime(self.raiz, (time.time() + 10, time.time() + 10))
        self.assertTrue(self.scanner.is_folder_outdated(self.raiz))

    def test_is_folder_outdated_quando_subpasta_muda(self):
        self.scanner.stats(self.raiz)
        futuro = time.time() + 10
        os.utime(os.path.join(self.raiz, "sub"), (futuro, futuro))
        self.assertTrue(self.scanner.is_folder_outdated(self.raiz))

    def test_is_folder_outdated_por_idade(self):
        self.scanner.stats(self.raiz)
        velho = FileSystemScanner(storage=self.storage, idade_maxima=-1)
        self.assertTrue(velho.is_folder_outdated(self.raiz))

    def test_is_folder_outdated_para_pasta_fora_do_cache(self):
        self.assertTrue(self.scanner.is_folder_outdated(os.path.join(self.raiz, "sub")))

    def test_refresh_folder_atualiza_a_pasta_e_os_ancestrais(self):
        self.scanner.stats(self.raiz)
        sub = os.path.join(self.raiz, "sub")
        escrever(os.path.join(sub, "c.bin"), b"w" * 25)
        novo = self.scanner.refresh_folder(sub)
        self.assertEqual(novo.tamanho, 75)
        self.assertEqual(self.storage.get_folder(sub).tamanho, 75)
        self.assertEqual(self.storage.get_folder(self.raiz).tamanho, 175)
        self.assertEqual(self.storage.get_folder(self.raiz).arquivos, 3)

    def test_refresh_folder_corrige_maior_arquivo_do_ancestral(self):
        escrever(os.path.join(self.raiz, "sub", "enorme.bin"), b"g" * 5000)
        self.scanner.stats(self.raiz)
        self.assertEqual(self.storage.get_folder(self.raiz).maior_nome, "enorme.bin")
        os.remove(os.path.join(self.raiz, "sub", "enorme.bin"))
        self.scanner.refresh_folder(os.path.join(self.raiz, "sub"))
        self.assertEqual(self.storage.get_folder(self.raiz).maior_nome, "a.bin")

    def test_refresh_folder_chama_o_progresso(self):
        self.scanner.stats(self.raiz)
        vistos = []
        self.scanner.refresh_folder(self.raiz, progresso=vistos.append)
        self.assertTrue(vistos)

    def test_refresh_folder_atualiza_ancestral_ja_em_cache_de_memoria(self):
        # popula o cache em memoria do ancestral ANTES do refresh
        self.scanner.stats(self.raiz)
        sub = os.path.join(self.raiz, "sub")
        escrever(os.path.join(sub, "c.bin"), b"w" * 25)
        self.scanner.refresh_folder(sub)
        # mesma instancia de scanner: nao pode devolver o total antigo do cache em memoria
        self.assertEqual(self.scanner.stats(self.raiz).tamanho, 175)

    def test_refresh_folder_corrige_maior_arquivo_do_ancestral_ja_em_cache(self):
        sub = os.path.join(self.raiz, "sub")
        escrever(os.path.join(sub, "enorme.bin"), b"g" * 5000)
        # popula o cache em memoria do ancestral com "enorme.bin" como maior
        self.assertEqual(self.scanner.stats(self.raiz).maior_arquivo_nome, "enorme.bin")
        os.remove(os.path.join(sub, "enorme.bin"))
        self.scanner.refresh_folder(sub)
        # mesma instancia de scanner: o maior arquivo em cache tem que ser corrigido
        self.assertEqual(self.scanner.stats(self.raiz).maior_arquivo_nome, "a.bin")
