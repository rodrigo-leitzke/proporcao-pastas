"""Testes da escolha de raiz em modo multi-raiz."""
import unittest

from proporcao_pastas.infrastructure.file_system import parent_analysis_path, raiz_de


class TestRaizDe(unittest.TestCase):
    def test_escolhe_a_raiz_que_contem_o_caminho(self):
        raizes = ["/", "/Volumes/Backup"]
        self.assertEqual(raiz_de("/Volumes/Backup/fotos", raizes), "/Volumes/Backup")
        self.assertEqual(raiz_de("/Users/maria", raizes), "/")

    def test_prefere_a_raiz_mais_especifica(self):
        raizes = ["/", "/Volumes", "/Volumes/Backup"]
        self.assertEqual(raiz_de("/Volumes/Backup/x", raizes), "/Volumes/Backup")

    def test_caminho_fora_das_raizes_volta_ele_mesmo(self):
        self.assertEqual(raiz_de("/outro/lugar", ["/Volumes"]), "/outro/lugar")

    def test_raiz_nao_tem_pai_quando_nao_e_para_incluir(self):
        _, tem_pai = parent_analysis_path("/Volumes/Backup", "/Volumes/Backup", False)
        self.assertFalse(tem_pai)
