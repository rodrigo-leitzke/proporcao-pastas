"""Testes das partes do tk_app que nao dependem de uma janela.

Nao da para construir a App de verdade em ambiente sem tela (tk.Tk() falha),
entao os metodos sao chamados com App.__new__ e dubles no lugar dos widgets.
Tudo o que esta aqui so toca filas, dados e callbacks - nunca o Tk.
"""
import queue
import unittest
from unittest import mock

from proporcao_pastas.domain.models import ItemPasta
from proporcao_pastas.presentation import tk_app
from proporcao_pastas.presentation.tk_app import (
    COLUNAS_TABELA,
    FIM_MAPEAMENTO,
    PREFIXO_ERRO,
    App,
    valores_da_linha,
)


class TestColunasDaTabela(unittest.TestCase):
    """Tripwire de paridade: uma coluna para cada valor, e vice-versa."""

    def test_arquivo(self):
        item = ItemPasta(nome="a.bin", tamanho=10, eh_pasta=False)
        self.assertEqual(len(valores_da_linha(item, 50.0)), len(COLUNAS_TABELA))

    def test_pasta(self):
        item = ItemPasta(nome="sub", tamanho=10, eh_pasta=True, arquivos=2, subpastas=1)
        self.assertEqual(len(valores_da_linha(item, 50.0)), len(COLUNAS_TABELA))

    def test_agrupado_em_outros(self):
        item = ItemPasta(nome="Outros (3 itens)", tamanho=10, eh_pasta=None)
        self.assertEqual(len(valores_da_linha(item, 50.0)), len(COLUNAS_TABELA))

    def test_tupla_legada_de_tres_itens(self):
        # preencher_tabela aceita o formato de tupla antigo
        self.assertEqual(len(valores_da_linha(("a", 10, False), 50.0)), len(COLUNAS_TABELA))


class AnalisadorQueExplode:
    def execute(self, *a, **k):
        raise RuntimeError("falha na analise")

    def refresh(self, *a, **k):
        raise RuntimeError("falha no refresh")


class ScannerQueExplode:
    def mapear_raizes(self, raizes, progresso=None, cancelado=None):
        raise RuntimeError("falha no mapeamento")


class ScannerQueAnota:
    def __init__(self):
        self.recebidas = None

    def mapear_raizes(self, raizes, progresso=None, cancelado=None):
        self.recebidas = list(raizes)
        return len(self.recebidas)


def montar_app(**extra):
    app = App.__new__(App)  # sem __init__: nao da para criar janela sem tela
    app.raizes = ["/raiz"]
    app.pai_na_raiz = False
    app.fila = queue.Queue()
    app.fila_status = queue.Queue()
    app.cancelar_mapeamento = False
    app.logs = []
    app.gravar_log = app.logs.append
    for nome, valor in extra.items():
        setattr(app, nome, valor)
    return app


def mensagens(fila):
    saida = []
    while not fila.empty():
        saida.append(fila.get_nowait())
    return saida


class TestFalhaNaThreadDeAnalise(unittest.TestCase):
    def test_erro_vai_para_a_barra_de_status_e_para_o_log(self):
        app = montar_app(analyze_folder=AnalisadorQueExplode())
        app.trabalho("/raiz", 1, set())
        self.assertTrue(app.fila.empty())  # nada a mostrar
        avisos = mensagens(app.fila_status)
        self.assertEqual(len(avisos), 1)
        self.assertTrue(avisos[0].startswith(PREFIXO_ERRO))
        self.assertIn("falha na analise", avisos[0])
        self.assertIn("falha na analise", app.logs[0])
        self.assertIn("Traceback", app.logs[0])

    def test_erro_no_refresh_tambem_e_informado(self):
        app = montar_app(analyze_folder=AnalisadorQueExplode())
        app.trabalho("/raiz", 1, set(), revarrer=True)
        avisos = mensagens(app.fila_status)
        self.assertTrue(any("falha no refresh" in m for m in avisos))


class TestFalhaNaThreadDeMapeamento(unittest.TestCase):
    def test_erro_informa_e_libera_o_botao(self):
        app = montar_app(scanner=ScannerQueExplode())
        app._mapear()
        avisos = mensagens(app.fila_status)
        self.assertIn(FIM_MAPEAMENTO, avisos)  # botao volta a "Mapear discos"
        self.assertTrue(any(m.startswith(PREFIXO_ERRO) for m in avisos))
        self.assertIn("falha no mapeamento", app.logs[0])

    def test_mapeia_as_raizes_do_sistema_e_nao_a_pasta_trocada(self):
        scanner = ScannerQueAnota()
        app = montar_app(scanner=scanner, raizes=["/apenas/uma/pasta"])
        with mock.patch.object(tk_app, "list_system_roots", lambda: ["/", "/Volumes/Backup"]):
            app._mapear()
        self.assertEqual(scanner.recebidas, ["/", "/Volumes/Backup"])
        self.assertIn(FIM_MAPEAMENTO, mensagens(app.fila_status))

    def test_fim_do_mapeamento_normal_tambem_libera_o_botao(self):
        app = montar_app(scanner=ScannerQueAnota())
        with mock.patch.object(tk_app, "list_system_roots", lambda: ["/"]):
            app._mapear()
        avisos = mensagens(app.fila_status)
        self.assertEqual(avisos, ["Mapeamento concluído", FIM_MAPEAMENTO])
        self.assertEqual(app.logs, [])
