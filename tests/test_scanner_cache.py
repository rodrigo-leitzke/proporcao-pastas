"""Testes da integracao entre o scanner e o cache persistente."""
import os
import tempfile
import threading
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

    def test_refresh_folder_de_pasta_nova_corrige_os_ancestrais(self):
        # pasta que nunca esteve em cache: o delta tem que valer "novo - 0",
        # mais 1 subpasta (a propria pasta nova) na contagem recursiva do pai
        self.scanner.stats(self.raiz)
        novo = os.path.join(self.raiz, "novo")
        escrever(os.path.join(novo, "d.bin"), b"d" * 400)
        escrever(os.path.join(novo, "dentro", "e.bin"), b"e" * 100)
        medido = self.scanner.refresh_folder(novo)
        self.assertEqual(medido.tamanho, 500)
        self.assertEqual(medido.subpastas, 1)
        raiz_gravada = self.storage.get_folder(self.raiz)
        self.assertEqual(raiz_gravada.tamanho, 650)
        self.assertEqual(raiz_gravada.arquivos, 4)
        self.assertEqual(raiz_gravada.subpastas, 1 + medido.subpastas + 1)
        self.assertEqual(self.scanner.stats(self.raiz).tamanho, 650)
        # o total da raiz tem que bater com a soma dos filhos gravados
        filhos = self.storage.get_subfolders(self.raiz)
        soma_filhos = sum(f.tamanho for f in filhos)
        self.assertEqual(raiz_gravada.tamanho, soma_filhos + 100)  # 100 = a.bin direto

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

    def test_pasta_ilegivel_nao_e_gravada_no_cache(self):
        travada = os.path.join(self.raiz, "travada")
        escrever(os.path.join(travada, "x.bin"), b"x" * 10)
        os.chmod(travada, 0o000)
        if os.access(travada, os.R_OK):  # root (ou Windows) ignora o chmod
            os.chmod(travada, 0o755)
            self.skipTest("o chmod nao nega a leitura neste ambiente")
        try:
            self.assertEqual(self.scanner.stats(self.raiz).tamanho, 150)
        finally:
            os.chmod(travada, 0o755)
        # o 0 da pasta ilegivel nao pode ficar gravado por 7 dias
        self.assertIsNone(self.storage.get_folder(travada))
        self.assertEqual(self.storage.get_folder(self.raiz).tamanho, 150)
        # quando a leitura volta, a pasta e gravada normalmente
        outro = FileSystemScanner(storage=self.storage)
        self.assertEqual(outro.stats(travada).tamanho, 10)
        self.assertEqual(self.storage.get_folder(travada).tamanho, 10)

    def test_refresh_nao_duplica_delta_com_varredura_concorrente(self):
        """A varredura e o refresh sao serializados pelo scanner.

        Sem isso, uma varredura abandonada do ancestral (o usuario clicou em
        outra pasta) grava no meio do refresh e o delta acaba somado em cima de
        um total que ja estava corrigido."""
        self.scanner.stats(self.raiz)  # raiz = 150 em cache
        sub = os.path.join(self.raiz, "sub")
        escrever(os.path.join(sub, "c.bin"), b"w" * 25)  # sub vai de 50 para 75
        original = self.storage.aplicar_delta
        concorrentes = []

        def aplicar_delta(*args, **kwargs):
            # no meio da correcao, outra thread tenta varrer o ancestral
            thread = threading.Thread(
                target=lambda: self.scanner.stats(self.raiz, usar_cache=False)
            )
            concorrentes.append(thread)
            thread.start()
            time.sleep(0.05)
            return original(*args, **kwargs)

        self.storage.aplicar_delta = aplicar_delta
        try:
            self.scanner.refresh_folder(sub)
        finally:
            del self.storage.aplicar_delta
        for thread in concorrentes:
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
        self.assertEqual(self.storage.get_folder(self.raiz).tamanho, 175)

    def test_refresh_folder_corrige_maior_arquivo_do_ancestral_ja_em_cache(self):
        sub = os.path.join(self.raiz, "sub")
        escrever(os.path.join(sub, "enorme.bin"), b"g" * 5000)
        # popula o cache em memoria do ancestral com "enorme.bin" como maior
        self.assertEqual(self.scanner.stats(self.raiz).maior_arquivo_nome, "enorme.bin")
        os.remove(os.path.join(sub, "enorme.bin"))
        self.scanner.refresh_folder(sub)
        # mesma instancia de scanner: o maior arquivo em cache tem que ser corrigido
        self.assertEqual(self.scanner.stats(self.raiz).maior_arquivo_nome, "a.bin")
