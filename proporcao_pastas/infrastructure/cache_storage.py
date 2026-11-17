"""Cache persistente das estatisticas de pastas, em SQLite."""
import dataclasses
import os
import sqlite3
import threading
from dataclasses import dataclass
from typing import List, Optional

from proporcao_pastas.infrastructure.system_roots import IS_MAC, IS_WINDOWS

MAX_ARQUIVOS_CACHE = 50
VERSAO_ESQUEMA = "1"

TABELAS = ("folders", "files", "meta")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS folders (
    path TEXT PRIMARY KEY,
    parent TEXT,
    tamanho INTEGER NOT NULL,
    arquivos INTEGER NOT NULL,
    subpastas INTEGER NOT NULL,
    maior_nome TEXT NOT NULL DEFAULT '',
    maior_tam INTEGER NOT NULL DEFAULT 0,
    maior_direct_nome TEXT NOT NULL DEFAULT '',
    maior_direct_tam INTEGER NOT NULL DEFAULT 0,
    modificado_em REAL,
    criado_em REAL,
    permissoes TEXT NOT NULL DEFAULT '-',
    cache_updated_at REAL NOT NULL,
    arquivos_truncados INTEGER NOT NULL DEFAULT 0,
    soma_truncados INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent);
CREATE TABLE IF NOT EXISTS files (
    parent TEXT NOT NULL,
    nome TEXT NOT NULL,
    tamanho INTEGER NOT NULL,
    modificado_em REAL,
    criado_em REAL,
    permissoes TEXT,
    PRIMARY KEY (parent, nome)
);
CREATE TABLE IF NOT EXISTS meta (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
"""

@dataclass
class CachedFolder:
    path: str
    parent: Optional[str]
    tamanho: int
    arquivos: int
    subpastas: int
    maior_nome: str
    maior_tam: int
    maior_direct_nome: str
    maior_direct_tam: int
    modificado_em: Optional[float]
    criado_em: Optional[float]
    permissoes: str
    cache_updated_at: float
    arquivos_truncados: int = 0
    soma_truncados: int = 0


@dataclass
class CachedFile:
    nome: str
    tamanho: int
    modificado_em: Optional[float]
    criado_em: Optional[float]
    permissoes: Optional[str]


# colunas de folders na ordem dos campos do dataclass: o DDL e o dataclass sao
# o par que sobra; o resto (SELECT, INSERT e as marcas do INSERT) sai daqui
CAMPOS_FOLDER = ", ".join(campo.name for campo in dataclasses.fields(CachedFolder))
MARCAS_FOLDER = ", ".join("?" * len(dataclasses.fields(CachedFolder)))


def caminho_padrao_cache() -> str:
    """Caminho do banco de cache conforme o SO."""
    if IS_WINDOWS:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        pasta = os.path.join(base, "ProporcaoPastas")
    elif IS_MAC:
        pasta = os.path.expanduser("~/Library/Caches/ProporcaoPastas")
    else:
        pasta = os.path.join(
            os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"),
            "proporcao-pastas",
        )
    return os.path.join(pasta, "cache.db")


class SqliteCacheStorage:
    """Le e grava o cache de pastas. Seguro para uso de varias threads."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        pasta = os.path.dirname(db_path)
        if pasta:
            os.makedirs(pasta, exist_ok=True)
        self._lock = threading.RLock()
        try:
            self._abrir()
        except (sqlite3.DatabaseError, OSError):
            # arquivo corrompido, ou de outro programa: isto e cache, apagar e
            # refazer e sempre valido. Se a segunda tentativa tambem falhar, o
            # erro sobe e quem chamou decide (a App abre sem cache).
            self._descartar_arquivo()
            self._abrir()

    def _abrir(self) -> None:
        self._con = sqlite3.connect(self.db_path, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        with self._lock:
            self._con.execute("PRAGMA journal_mode=WAL")
            self._con.execute("PRAGMA synchronous=NORMAL")
            # duas instancias ao mesmo tempo sao plausiveis (clique direito em
            # duas pastas abre dois processos): esperar e melhor que travar
            self._con.execute("PRAGMA busy_timeout=15000")
            if self._esquema_incompativel():
                self._descartar_esquema()
            self._con.executescript(ESQUEMA)
            self._con.execute(
                "INSERT OR IGNORE INTO meta (chave, valor) VALUES ('versao', ?)",
                (VERSAO_ESQUEMA,),
            )
            self._con.commit()

    def _esquema_incompativel(self) -> bool:
        """Diz se o arquivo tem um esquema de outra versao.

        CREATE TABLE IF NOT EXISTS nao mexe em uma tabela 'folders' que exista
        com outras colunas: sem esta checagem um banco de versao anterior abre
        normalmente e so quebra depois, dentro de uma thread, com
        'no such column'. Por isso meta.versao e lido antes de confiar no
        arquivo."""
        tabelas = {
            linha["name"] for linha in self._con.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if "folders" not in tabelas:
            return False  # banco novo ou vazio: nao ha nada a descartar
        if "meta" not in tabelas:
            return True
        linha = self._con.execute(
            "SELECT valor FROM meta WHERE chave = 'versao'"
        ).fetchone()
        return linha is None or linha["valor"] != VERSAO_ESQUEMA

    def _descartar_esquema(self) -> None:
        """Derruba as tabelas para o ESQUEMA ser recriado do zero."""
        for tabela in TABELAS:
            self._con.execute("DROP TABLE IF EXISTS {}".format(tabela))
        self._con.commit()

    def _descartar_arquivo(self) -> None:
        """Fecha e apaga o banco (e os arquivos auxiliares do WAL)."""
        con = getattr(self, "_con", None)
        if con is not None:
            try:
                con.close()
            except sqlite3.Error:
                pass
        for sufixo in ("", "-wal", "-shm", "-journal"):
            try:
                os.remove(self.db_path + sufixo)
            except OSError:
                pass

    def close(self) -> None:
        with self._lock:
            self._con.close()

    # ---------- escrita ----------
    def put_folder(self, folder: CachedFolder, arquivos: List[CachedFile]) -> None:
        with self._lock:
            self._con.execute(
                "INSERT OR REPLACE INTO folders ({}) VALUES ({})".format(
                    CAMPOS_FOLDER, MARCAS_FOLDER
                ),
                dataclasses.astuple(folder),
            )
            self._con.execute("DELETE FROM files WHERE parent = ?", (folder.path,))
            self._con.executemany(
                "INSERT OR REPLACE INTO files "
                "(parent, nome, tamanho, modificado_em, criado_em, permissoes) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (folder.path, a.nome, a.tamanho, a.modificado_em, a.criado_em, a.permissoes)
                    for a in arquivos
                ],
            )
            self._con.commit()

    def delete_subtree(self, path: str) -> None:
        """Remove a pasta e todos os descendentes, descendo pela coluna parent.

        Nao usa LIKE de proposito: nome de pasta com % ou _ seria curinga."""
        with self._lock:
            visitados = set()
            alvos = []
            fila = [path]
            while fila:
                atual = fila.pop()
                if atual in visitados:
                    continue
                visitados.add(atual)
                alvos.append(atual)
                filhos = [
                    linha["path"] for linha in self._con.execute(
                        "SELECT path FROM folders WHERE parent = ?", (atual,)
                    ) if linha["path"] not in visitados
                ]
                fila.extend(filhos)
            for inicio in range(0, len(alvos), 500):
                lote = alvos[inicio:inicio + 500]
                marcas = ", ".join("?" * len(lote))
                self._con.execute(
                    "DELETE FROM folders WHERE path IN ({})".format(marcas), lote
                )
                self._con.execute(
                    "DELETE FROM files WHERE parent IN ({})".format(marcas), lote
                )
            self._con.commit()

    def set_meta(self, chave: str, valor: str) -> None:
        with self._lock:
            self._con.execute(
                "INSERT OR REPLACE INTO meta (chave, valor) VALUES (?, ?)", (chave, valor)
            )
            self._con.commit()

    # ---------- leitura ----------
    def get_folder(self, path: str) -> Optional[CachedFolder]:
        with self._lock:
            linha = self._con.execute(
                "SELECT {} FROM folders WHERE path = ?".format(CAMPOS_FOLDER), (path,)
            ).fetchone()
        return CachedFolder(**dict(linha)) if linha else None

    def get_files(self, path: str) -> List[CachedFile]:
        with self._lock:
            linhas = self._con.execute(
                "SELECT nome, tamanho, modificado_em, criado_em, permissoes "
                "FROM files WHERE parent = ?",
                (path,),
            ).fetchall()
        return [CachedFile(**dict(linha)) for linha in linhas]

    def get_subfolders(self, path: str) -> List[CachedFolder]:
        with self._lock:
            linhas = self._con.execute(
                "SELECT {} FROM folders WHERE parent = ?".format(CAMPOS_FOLDER), (path,)
            ).fetchall()
        return [CachedFolder(**dict(linha)) for linha in linhas]

    # ---------- atualizacao parcial ----------
    def ancestrais(self, path: str) -> List[str]:
        """Ancestrais em cache, do pai ate a raiz.

        Guarda os caminhos ja visitados para nao entrar em loop infinito
        se uma linha tiver parent autorreferente ou formar um ciclo
        (mesmo hazard do delete_subtree, so que subindo em vez de descendo)."""
        caminhos = []
        with self._lock:
            visitados = {path}
            atual = path
            while True:
                linha = self._con.execute(
                    "SELECT parent FROM folders WHERE path = ?", (atual,)
                ).fetchone()
                pai = linha["parent"] if linha else None
                if not pai or pai in visitados:
                    break
                caminhos.append(pai)
                visitados.add(pai)
                atual = pai
        return caminhos

    def aplicar_delta(
        self,
        path: str,
        d_tamanho: int,
        d_arquivos: int,
        d_subpastas: int,
    ) -> List[str]:
        """Soma as diferencas nos ancestrais e recalcula o maior arquivo deles.

        cache_updated_at do ancestral nao muda: ele foi corrigido, nao revarrido."""
        alterados = self.ancestrais(path)
        with self._lock:
            for ancestral in alterados:
                self._con.execute(
                    "UPDATE folders SET "
                    "tamanho = MAX(0, tamanho + ?), "
                    "arquivos = MAX(0, arquivos + ?), "
                    "subpastas = MAX(0, subpastas + ?) "
                    "WHERE path = ?",
                    (d_tamanho, d_arquivos, d_subpastas, ancestral),
                )
            self._con.commit()
        for ancestral in alterados:
            self.recalcular_maior(ancestral)
        return alterados

    def recalcular_maior(self, path: str) -> None:
        """Maior arquivo de uma pasta = maior entre os arquivos diretos dela
        e o maior de cada subpasta direta que esta em cache."""
        atual = self.get_folder(path)
        if atual is None:
            return
        melhor_nome, melhor_tam = atual.maior_direct_nome, atual.maior_direct_tam
        for sub in self.get_subfolders(path):
            if sub.maior_tam > melhor_tam:
                melhor_nome, melhor_tam = sub.maior_nome, sub.maior_tam
        with self._lock:
            self._con.execute(
                "UPDATE folders SET maior_nome = ?, maior_tam = ? WHERE path = ?",
                (melhor_nome, melhor_tam, path),
            )
            self._con.commit()

    def get_meta(self, chave: str) -> Optional[str]:
        with self._lock:
            linha = self._con.execute(
                "SELECT valor FROM meta WHERE chave = ?", (chave,)
            ).fetchone()
        return linha["valor"] if linha else None

    def ultima_atualizacao_global(self) -> Optional[float]:
        with self._lock:
            linha = self._con.execute("SELECT MAX(cache_updated_at) AS m FROM folders").fetchone()
        return linha["m"] if linha and linha["m"] is not None else None
