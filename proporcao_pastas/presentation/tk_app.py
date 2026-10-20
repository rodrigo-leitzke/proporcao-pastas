"""
Proporcao de pastas: ao clicar em uma pasta, mostra quanto ela ocupa da pasta
pai e como o espaco dela se divide entre subpastas e arquivos (grafico de pizza).
Ao selecionar varios itens da tabela (Ctrl/Shift+clique) ou fatias da pizza,
soma os selecionados e mostra quanto representam da pasta.

Uso:
    python proporcao_pastas.py                 abre e pergunta a pasta inicial
    python proporcao_pastas.py "C:\\Users\\x"   abre direto nessa pasta
    python proporcao_pastas.py --instalar      adiciona ao menu de clique direito
    python proporcao_pastas.py --remover       remove do menu de clique direito

So usa a biblioteca padrao do Python (tkinter e winreg), sem instalar nada.
"""
import math
import os
import queue
import threading
import traceback
import tkinter as tk
from tkinter import ttk, filedialog

from proporcao_pastas.application.analyze_folder import AnalyzeFolder
from proporcao_pastas.domain.formatting import clarear_cor as clarear
from proporcao_pastas.domain.formatting import formatar_tamanho as fmt
from proporcao_pastas.infrastructure.file_system import FileSystemScanner

CORES = ["#4E79A7", "#F28E2B", "#E15759", "#76B7B2",
         "#59A14F", "#EDC948", "#B07AA1", "#9C755F"]
CINZA = "#BAB0AC"
AZUL_EXPLORER = "#26A0DA"
FUNDO_BARRA = "#F3F3F3"
DICA = "Para somar: Ctrl+clique ou Shift+clique nos itens da tabela (ou clique nas fatias da pizza)"
COR_DICA, FONTE_DICA = "#777777", ("Segoe UI", 9)
COR_SEL, FONTE_SEL = "#0B6FA4", ("Segoe UI", 10, "bold")
# geometria da pizza (canvas 300x300)
CENTRO = 150
RAIO = 132
RAIO_FURO = 65
EXPLOSAO = 8  # quanto as fatias selecionadas saem do centro

# ---------------------------------------------------------------- icones
def icone_pasta(master):
    """Pasta amarela 16x16 desenhada pixel a pixel (sem arquivos externos)."""
    img = tk.PhotoImage(master=master, width=16, height=16)
    img.put("#E1A92A", to=(1, 2, 7, 5))     # aba
    img.put("#E1A92A", to=(1, 4, 15, 14))   # contorno
    img.put("#FBD76B", to=(2, 5, 14, 13))   # corpo
    return img


def quadrado(master, cor):
    img = tk.PhotoImage(master=master, width=12, height=12)
    img.put(cor, to=(0, 0, 12, 12))
    return img


# ---------------------------------------------------------------- interface
class App:
    def __init__(self, raiz, pai_na_raiz):
        self.pai_na_raiz = pai_na_raiz
        self.raiz = raiz
        self.scanner = FileSystemScanner()
        self.analyze_folder = AnalyzeFolder(self.scanner)
        self.token = 0
        self.pronto = False      # False enquanto a analise esta em andamento
        self.nos = {}            # id na arvore -> caminho
        self.linhas = {}         # id na tabela -> caminho (so pastas)
        self.ids = []            # ids da tabela, na ordem das fatias
        self.lista = []          # itens (nome, tamanho, eh_pasta) da pasta atual
        self.total = 0
        self.faixas = []         # (inicio, fim) em graus de cada fatia, p/ clique
        self.sel_idx = set()     # indices dos itens selecionados
        self.pct = None          # % da pasta atual em relacao a pasta pai
        self.pct_sel = None      # % dos selecionados em relacao a pasta atual
        self.marcar = set()      # nomes a pre-selecionar na tabela (multi-selecao na arvore)
        self.fila = queue.Queue()

        self.w = tk.Tk()
        self.w.title("Proporção de pastas")
        self.w.geometry("1120x680")
        self.w.minsize(900, 560)
        self.w.report_callback_exception = self.erro  # mostra erros na barra de status

        estilo = ttk.Style(self.w)
        try:
            estilo.theme_use("vista")  # visual nativo do Windows
        except tk.TclError:
            pass
        estilo.configure("Treeview", rowheight=22, font=("Segoe UI", 9))
        estilo.configure("Treeview.Heading", font=("Segoe UI", 9))

        self.ic_pasta = icone_pasta(self.w)
        self.ic_grande = self.ic_pasta.zoom(3)
        self.quadrados = {c: quadrado(self.w, c) for c in CORES + [CINZA]}

        # barra de status (embaixo)
        self.status = tk.Label(self.w, text="Pronto", anchor="w", bg=FUNDO_BARRA,
                               font=("Segoe UI", 9), padx=8, pady=3)
        self.status.pack(side="bottom", fill="x")

        # barra de ferramentas (em cima)
        barra = tk.Frame(self.w, bg=FUNDO_BARRA, padx=8, pady=6)
        barra.pack(side="top", fill="x")
        tk.Label(barra, text="Pasta:", bg=FUNDO_BARRA,
                 font=("Segoe UI", 9)).pack(side="left")
        self.endereco = tk.StringVar()
        ttk.Entry(barra, textvariable=self.endereco, state="readonly").pack(
            side="left", fill="x", expand=True, padx=6)
        ttk.Button(barra, text="Atualizar", command=self.atualizar).pack(side="left", padx=2)
        ttk.Button(barra, text="Trocar pasta...", command=self.trocar).pack(side="left", padx=2)
        ttk.Button(barra, text="Abrir no Explorer", command=self.abrir_explorer).pack(side="left", padx=2)

        painel = ttk.PanedWindow(self.w, orient="horizontal")
        painel.pack(fill="both", expand=True)

        # painel de navegacao (esquerda)
        esq = ttk.Frame(painel)
        painel.add(esq, weight=1)
        self.tree = ttk.Treeview(esq, show="tree")
        sb = ttk.Scrollbar(esq, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

        # painel de detalhes (direita)
        dir_ = tk.Frame(painel, bg="white")
        painel.add(dir_, weight=3)

        topo = tk.Frame(dir_, bg="white")
        topo.pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(topo, image=self.ic_grande, bg="white").pack(side="left")
        txt = tk.Frame(topo, bg="white")
        txt.pack(side="left", fill="x", expand=True, padx=12)
        self.nome = tk.Label(txt, bg="white", font=("Segoe UI", 15), anchor="w")
        self.nome.pack(fill="x")
        self.caminho = tk.Label(txt, bg="white", fg="#666666", font=("Segoe UI", 9),
                                anchor="w", justify="left", wraplength=700)
        self.caminho.pack(fill="x")

        # uso da pasta atual em relacao a pasta pai
        self.uso = tk.Label(dir_, bg="white", font=("Segoe UI", 10), anchor="w")
        self.uso.pack(fill="x", padx=16)
        self.barra = tk.Canvas(dir_, height=16, bg="white", highlightthickness=0)
        self.barra.pack(fill="x", padx=16, pady=(2, 10))
        self.barra.bind("<Configure>", lambda e: self.desenhar_barra(self.barra, self.pct))

        # soma dos itens selecionados em relacao a pasta atual
        self.sel_frame = tk.Frame(dir_, bg="white")
        self.sel_frame.pack(fill="x", padx=16, pady=(0, 10))
        self.sel_texto = tk.Label(self.sel_frame, bg="white", fg=COR_DICA,
                                  font=FONTE_DICA, anchor="w", text=DICA)
        self.sel_texto.pack(fill="x")
        self.barra_sel = tk.Canvas(self.sel_frame, height=16, bg="white", highlightthickness=0)
        self.barra_sel.pack(fill="x", pady=(2, 0))
        self.barra_sel.bind("<Configure>",
                            lambda e: self.desenhar_barra(self.barra_sel, self.pct_sel))

        self.corpo = tk.Frame(dir_, bg="white")
        self.corpo.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        self.cv = tk.Canvas(self.corpo, width=300, height=300, bg="white",
                            highlightthickness=0)
        self.cv.pack(side="left", anchor="n")
        self.cv.bind("<Button-1>", self.clique_pizza)

        self.tab = ttk.Treeview(self.corpo, columns=("tam", "pct", "tipo"), height=10,
                                selectmode="extended")
        self.tab.heading("#0", text="Nome", anchor="w")
        self.tab.heading("tam", text="Tamanho", anchor="e")
        self.tab.heading("pct", text="%", anchor="e")
        self.tab.heading("tipo", text="Tipo", anchor="w")
        self.tab.column("#0", width=220, stretch=True)
        self.tab.column("tam", width=90, anchor="e", stretch=False)
        self.tab.column("pct", width=60, anchor="e", stretch=False)
        self.tab.column("tipo", width=70, anchor="w", stretch=False)
        self.tab.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self.tab.bind("<Double-1>", self.entrar_na_pasta)
        self.tab.bind("<<TreeviewSelect>>", self.selecao_mudou)
        self.tab.bind("<Control-a>", self.selecionar_tudo)

        self.tree.bind("<<TreeviewOpen>>", lambda e: self.popular(self.tree.focus()))
        self.tree.bind("<<TreeviewSelect>>", self.selecionar)

        self.definir_raiz(raiz)
        self.w.after(100, self.poll)

    def erro(self, exc, val, tb):
        """Erros de callbacks: mostra na barra de status e grava em um .log
        (com pythonw nao existe console, entao falhas ficariam invisiveis)."""
        msg = "".join(traceback.format_exception(exc, val, tb))
        try:
            log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "proporcao_pastas.log")
            with open(log, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except OSError:
            pass
        self.status.config(text=f"Erro: {val}  (detalhes em proporcao_pastas.log)", fg="#B00020")

    # ---------- arvore de pastas ----------
    def inserir(self, pai_id, caminho, texto):
        iid = self.tree.insert(pai_id, "end", text=texto, image=self.ic_pasta)
        self.nos[iid] = caminho
        self.tree.insert(iid, "end", text="...")  # item falso p/ mostrar a seta
        return iid

    def popular(self, iid):
        filhos = self.tree.get_children(iid)
        if len(filhos) == 1 and filhos[0] not in self.nos:  # so o item falso
            self.tree.delete(filhos[0])
            for nome in self.scanner.subfolders(self.nos[iid]):
                self.inserir(iid, os.path.join(self.nos[iid], nome), nome)

    def definir_raiz(self, caminho):
        self.raiz = caminho
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.nos.clear()
        iid = self.inserir("", caminho, os.path.basename(caminho) or caminho)
        self.popular(iid)
        self.tree.item(iid, open=True)
        self.tree.selection_set(iid)

    def trocar(self):
        p = filedialog.askdirectory(title="Escolha a pasta inicial", initialdir=self.raiz)
        if p:
            self.pai_na_raiz = False
            self.definir_raiz(os.path.normpath(p))

    def atualizar(self):
        self.scanner.clear_cache()
        sel = self.tree.selection()
        if sel and sel[0] in self.nos:
            self.analisar(self.nos[sel[0]])

    def abrir_explorer(self):
        sel = self.tree.selection()
        if sel and sel[0] in self.nos and hasattr(os, "startfile"):
            os.startfile(self.nos[sel[0]])

    def entrar_na_pasta(self, evento):
        """Duplo clique numa subpasta da tabela: seleciona ela na arvore."""
        linha = self.tab.identify_row(evento.y)
        destino = self.linhas.get(linha)
        sel = self.tree.selection()
        if not destino or not sel:
            return
        self.popular(sel[0])
        self.tree.item(sel[0], open=True)
        for f in self.tree.get_children(sel[0]):
            if self.nos.get(f) == destino:
                self.tree.selection_set(f)
                self.tree.see(f)
                break

    # ---------- analise em segundo plano ----------
    def selecionar(self, _evento):
        sel = [i for i in self.tree.selection() if i in self.nos]
        if len(sel) == 1:
            self.analisar(self.nos[sel[0]])
        elif len(sel) > 1:  # varias pastas na arvore: soma se forem irmas
            caminhos = [self.nos[i] for i in sel]
            pais = {os.path.dirname(c) for c in caminhos}
            if len(pais) == 1:
                self.analisar(pais.pop(), marcar={os.path.basename(c) for c in caminhos})
            else:
                self.status.config(text="Para somar, selecione pastas que estejam "
                                        "dentro da mesma pasta.", fg="black")

    def analisar(self, path, marcar=()):
        self.token += 1
        tok = self.token
        self.marcar = set(marcar)
        self.pronto = False
        self.endereco.set(path)
        self.nome.config(text=os.path.basename(path) or path)
        self.caminho.config(text=path)
        self.uso.config(text="Calculando...")
        self.status.config(text="Calculando... (a primeira leitura de pastas grandes pode demorar)",
                           fg="black")
        self.pct = None
        self.desenhar_barra(self.barra, None)
        self.pct_sel = None
        self.desenhar_barra(self.barra_sel, None)
        self.sel_texto.config(text=DICA, fg=COR_DICA, font=FONTE_DICA)
        self.cv.delete("all")
        self.tab.delete(*self.tab.get_children())
        self.linhas.clear()
        self.ids, self.lista, self.sel_idx = [], [], set()
        threading.Thread(target=self.trabalho, args=(path, tok, self.marcar), daemon=True).start()

    def trabalho(self, path, tok, marcar):
        resultado = self.analyze_folder.execute(
            path, self.raiz, self.pai_na_raiz, marcar
        )
        self.fila.put((
            resultado.path,
            resultado.total,
            resultado.parent_total,
            resultado.items,
            tok,
        ))

    def poll(self):
        try:
            while True:
                self.mostrar(*self.fila.get_nowait())
        except queue.Empty:
            pass
        finally:  # um erro em mostrar() nao pode parar as proximas atualizacoes
            self.w.after(100, self.poll)

    # ---------- exibicao ----------
    def mostrar(self, path, total, total_pai, lista, tok):
        if tok != self.token:  # usuario ja clicou em outra pasta
            return
        self.lista, self.total, self.sel_idx = lista, total, set()
        if total_pai:
            self.pct = total / total_pai * 100
            self.uso.config(text=f"{fmt(total)} de {fmt(total_pai)} da pasta pai "
                                 f"({self.pct:.1f}%)")
        else:
            self.pct = None
            self.uso.config(text=f"Tamanho total: {fmt(total)}")
        self.desenhar_barra(self.barra, self.pct)
        self.status.config(text=f"Pronto  |  {len(lista)} itens exibidos  |  "
                                f"Ctrl/Shift+clique para somar vários itens")
        self.preencher_tabela(path, lista)
        self.pronto = True
        self.desenhar_pizza()
        if self.marcar:  # veio de multi-selecao na arvore: destaca as pastas escolhidas
            self.tab.selection_set([self.ids[i] for i, (n, _, p) in enumerate(lista)
                                    if p and n in self.marcar])
            self.status.config(text="Mostrando a pasta pai com as pastas selecionadas destacadas")

    def preencher_tabela(self, path, lista):
        soma = sum(i[1] for i in lista) or 1
        self.ids = []
        for i, (nome, s, eh_pasta) in enumerate(lista):
            cor = CINZA if eh_pasta is None else CORES[i % len(CORES)]
            tipo = "—" if eh_pasta is None else ("Pasta" if eh_pasta else "Arquivo")
            iid = self.tab.insert("", "end", text=nome, image=self.quadrados[cor],
                                  values=(fmt(s), f"{s / soma * 100:.1f}%", tipo))
            self.ids.append(iid)
            if eh_pasta:
                self.linhas[iid] = os.path.join(path, nome)

    # ---------- selecao e soma ----------
    def selecionar_tudo(self, _evento):
        self.tab.selection_set(self.tab.get_children())
        return "break"

    def selecao_mudou(self, _evento=None):
        if not self.pronto:
            return
        marcados = set(self.tab.selection())
        self.sel_idx = {i for i, iid in enumerate(self.ids) if iid in marcados}
        self.atualizar_soma()
        self.desenhar_pizza()

    def atualizar_soma(self):
        if not self.sel_idx:
            self.pct_sel = None
            self.sel_texto.config(text=DICA, fg=COR_DICA, font=FONTE_DICA)
            self.desenhar_barra(self.barra_sel, None)
            return
        soma = sum(i[1] for i in self.lista) or 1
        sel = sum(self.lista[i][1] for i in self.sel_idx)
        n = len(self.sel_idx)
        self.pct_sel = sel / soma * 100
        self.sel_texto.config(
            text=f"{n} {'item selecionado' if n == 1 else 'itens selecionados'}: "
                 f"{fmt(sel)} de {fmt(soma)} ({self.pct_sel:.1f}%)",
            fg=COR_SEL, font=FONTE_SEL)
        self.desenhar_barra(self.barra_sel, self.pct_sel)

    def clique_pizza(self, ev):
        """Clicar numa fatia liga/desliga a selecao do item correspondente."""
        if not self.pronto or not self.lista:
            return
        dx, dy = ev.x - CENTRO, CENTRO - ev.y
        r = math.hypot(dx, dy)
        if r < RAIO_FURO or r > RAIO + EXPLOSAO:
            return
        graus = (90 - math.degrees(math.atan2(dy, dx))) % 360  # horario, a partir do topo
        for i, (ini, fim) in enumerate(self.faixas):
            if ini <= graus < fim:
                self.tab.selection_toggle(self.ids[i])
                break

    # ---------- desenho ----------
    def desenhar_barra(self, canvas, pct):
        canvas.delete("all")
        if pct is None:
            return
        larg = max(canvas.winfo_width() - 1, 10)
        canvas.create_rectangle(0, 0, larg, 15, fill="#E6E6E6", outline="#BCBCBC")
        canvas.create_rectangle(0, 0, larg * min(pct, 100) / 100, 15,
                                fill=AZUL_EXPLORER, outline=AZUL_EXPLORER)

    def desenhar_pizza(self):
        cv, lista = self.cv, self.lista
        cv.delete("all")
        self.faixas = []
        if not lista:
            cv.create_text(CENTRO, CENTRO, text="Pasta vazia",
                           font=("Segoe UI", 12), fill="#666666")
            return
        soma = sum(i[1] for i in lista)
        tem_sel = bool(self.sel_idx)
        explodir = tem_sel and len(self.sel_idx) < len(lista)
        ang = 90  # comeca no topo e segue no sentido horario
        for i, (_, s, eh_pasta) in enumerate(lista):
            cor = CINZA if eh_pasta is None else CORES[i % len(CORES)]
            graus = s / soma * 360
            inicio = (90 - ang) % 360
            self.faixas.append((inicio, inicio + graus))
            marcada = i in self.sel_idx
            if tem_sel and not marcada:
                cor = clarear(cor)
            dx = dy = 0
            if explodir and marcada:
                meio = math.radians(ang - graus / 2)
                dx, dy = EXPLOSAO * math.cos(meio), -EXPLOSAO * math.sin(meio)
            box = (CENTRO - RAIO + dx, CENTRO - RAIO + dy,
                   CENTRO + RAIO + dx, CENTRO + RAIO + dy)
            if graus >= 359.9:
                cv.create_oval(*box, fill=cor, outline="white", width=2)
            else:
                cv.create_arc(*box, start=ang, extent=-graus, fill=cor,
                              outline="white", width=2, style="pieslice")
            ang -= graus
        cv.create_oval(CENTRO - RAIO_FURO, CENTRO - RAIO_FURO,
                       CENTRO + RAIO_FURO, CENTRO + RAIO_FURO,
                       fill="white", outline="white")  # furo da rosca
        if tem_sel:
            valor = sum(lista[i][1] for i in self.sel_idx)
            legenda = "selecionados" if len(self.sel_idx) > 1 else "selecionado"
        else:
            valor, legenda = self.total, "nesta pasta"
        cv.create_text(CENTRO, CENTRO - 8, text=fmt(valor), font=("Segoe UI", 13, "bold"))
        cv.create_text(CENTRO, CENTRO + 14, text=legenda, font=("Segoe UI", 9), fill="#666666")

    def rodar(self):
        self.w.mainloop()
