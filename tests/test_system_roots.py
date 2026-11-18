"""Testes da deteccao de raizes do sistema."""
import unittest
from unittest import mock

from proporcao_pastas.infrastructure import system_roots


class TestListSystemRoots(unittest.TestCase):
    def test_windows_lista_unidades_existentes(self):
        existentes = {"C:\\", "D:\\"}
        with mock.patch.object(system_roots, "IS_WINDOWS", True), \
             mock.patch.object(system_roots.os.path, "exists", lambda p: p in existentes):
            self.assertEqual(system_roots.list_system_roots(), ["C:\\", "D:\\"])

    def test_nao_windows_retorna_barra(self):
        with mock.patch.object(system_roots, "IS_WINDOWS", False):
            self.assertEqual(system_roots.list_system_roots(), ["/"])


class TestCaminhoIgnorado(unittest.TestCase):
    def test_ignora_firmlink_do_mac(self):
        with mock.patch.object(system_roots, "IS_WINDOWS", False), \
             mock.patch.object(system_roots, "IS_MAC", True):
            self.assertTrue(system_roots.caminho_ignorado("/System/Volumes/Data"))
            self.assertTrue(system_roots.caminho_ignorado("/dev"))
            self.assertFalse(system_roots.caminho_ignorado("/Users/maria"))

    def test_ignora_winsxs_e_system_volume_information(self):
        with mock.patch.object(system_roots, "IS_WINDOWS", True), \
             mock.patch.object(system_roots, "IS_MAC", False):
            self.assertTrue(system_roots.caminho_ignorado("C:\\Windows\\WinSxS"))
            self.assertTrue(system_roots.caminho_ignorado("D:\\System Volume Information"))
            self.assertFalse(system_roots.caminho_ignorado("C:\\Users\\cesoler"))

    def test_comparacao_ignora_caixa(self):
        with mock.patch.object(system_roots, "IS_WINDOWS", True), \
             mock.patch.object(system_roots, "IS_MAC", False):
            self.assertTrue(system_roots.caminho_ignorado("c:\\windows\\winsxs"))
