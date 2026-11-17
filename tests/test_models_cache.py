"""Testes dos campos de cache nos modelos."""
import dataclasses
import unittest

from proporcao_pastas.domain.models import FolderStats, ItemPasta


class TestCamposDeCache(unittest.TestCase):
    def test_folder_stats_tem_padroes(self):
        stats = FolderStats(tamanho=10)
        self.assertIsNone(stats.cache_updated_at)
        self.assertFalse(stats.cache_desatualizado)

    def test_item_pasta_tem_padroes(self):
        item = ItemPasta(nome="a", tamanho=1, eh_pasta=False)
        self.assertIsNone(item.cache_updated_at)
        self.assertFalse(item.cache_desatualizado)

    def test_replace_atualiza_sem_quebrar_frozen(self):
        stats = FolderStats(tamanho=10)
        novo = dataclasses.replace(stats, cache_updated_at=123.0, cache_desatualizado=True)
        self.assertEqual(novo.cache_updated_at, 123.0)
        self.assertTrue(novo.cache_desatualizado)
        self.assertIsNone(stats.cache_updated_at)

    def test_tupla_legada_continua_com_tres_itens(self):
        item = ItemPasta(nome="a", tamanho=1, eh_pasta=True, cache_updated_at=5.0)
        self.assertEqual(tuple(item), ("a", 1, True))
        self.assertEqual(item[1], 1)
