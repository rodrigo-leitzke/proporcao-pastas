"""Cache persistente das estatisticas de pastas, em SQLite."""
import os
import platform
import sqlite3
import sys
import threading
from dataclasses import dataclass
from typing import List, Optional

MAX_ARQUIVOS_CACHE = 50
VERSAO_ESQUEMA = "1"

IS_WINDOWS = platform.system() == "Windows" or os.name == "nt"
IS_MAC = platform.system() == "Darwin" or sys.platform == "darwin"

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

CAMPOS_FOLDER = (
    "path, parent, tamanho, arquivos, subpastas, maior_nome, maior_tam, "
    "maior_direct_nome, maior_direct_tam, modificado_em, criado_em, permissoes, "
    "cache_updated_at, arquivos_truncados, soma_truncados"
)


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
        self._con = sqlite3.connect(db_path, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        with self._lock:
            self._con.execute("PRAGMA journal_mode=WAL")
            self._con.execute("PRAGMA synchronous=NORMAL")
            self._con.executescript(ESQUEMA)
            self._con.execute(
                "INSERT OR IGNORE INTO meta (chave, valor) VALUES ('versao', ?)",
                (VERSAO_ESQUEMA,),
            )
            self._con.commit()

    def close(self) -> None:
        with self._lock:
            self._con.close()

    # ---------- escrita ----------
    def put_folder(self, folder: CachedFolder, arquivos: List[CachedFile]) -> None:
        with self._lock:
            self._con.execute(
                "INSERT OR REPLACE INTO folders ({}) VALUES ({})".format(
                    CAMPOS_FOLDER, ", ".join("?" * 15)
                ),
                (
                    folder.path, folder.parent, folder.tamanho, folder.arquivos,
                    folder.subpastas, folder.maior_nome, folder.maior_tam,
                    folder.maior_direct_nome, folder.maior_direct_tam,
                    folder.modificado_em, folder.criado_em, folder.permissoes,
                    folder.cache_updated_at, folder.arquivos_truncados,
                    folder.soma_truncados,
                ),
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
            alvos = [path]
            fila = [path]
            while fila:
                atual = fila.pop()
                filhos = [
                    linha["path"] for linha in self._con.execute(
                        "SELECT path FROM folders WHERE parent = ?", (atual,)
                    )
                ]
                alvos.extend(filhos)
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
