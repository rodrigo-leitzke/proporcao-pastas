"""Leitura do sistema de arquivos usada pela aplicacao."""
import os
import stat
from typing import Dict, Iterable, List, Tuple

from proporcao_pastas.domain.formatting import formatar_tamanho, formatar_tipo_item
from proporcao_pastas.domain.models import FolderStats, ItemPasta


class FileSystemScanner:
    """Calcula tamanhos, metadados e lista o conteudo de pastas com cache em memoria."""

    def __init__(self) -> None:
        self._cache: Dict[str, int] = {}
        self._stats_cache: Dict[str, FolderStats] = {}

    def clear_cache(self) -> None:
        self._cache.clear()
        self._stats_cache.clear()

    def stats(self, path: str) -> FolderStats:
        if path in self._stats_cache:
            return self._stats_cache[path]

        total = 0
        arquivos = 0
        subpastas = 0
        maior_nome = ""
        maior_tam = 0

        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            sub = self.stats(entry.path)
                            total += sub.tamanho
                            arquivos += sub.arquivos
                            subpastas += 1 + sub.subpastas
                            if sub.maior_arquivo_tam > maior_tam:
                                maior_tam = sub.maior_arquivo_tam
                                maior_nome = sub.maior_arquivo_nome
                        else:
                            f_size = entry.stat(follow_symlinks=False).st_size
                            total += f_size
                            arquivos += 1
                            if f_size > maior_tam:
                                maior_tam = f_size
                                maior_nome = entry.name
                    except OSError:
                        continue
        except OSError:
            pass

        resultado = FolderStats(
            tamanho=total,
            arquivos=arquivos,
            subpastas=subpastas,
            maior_arquivo_nome=maior_nome,
            maior_arquivo_tam=maior_tam,
        )
        self._cache[path] = total
        self._stats_cache[path] = resultado
        return resultado

    def size(self, path: str) -> int:
        return self.stats(path).tamanho

    def children(self, path: str, keep: Iterable[str] = (), max_items: int = 8) -> List[ItemPasta]:
        items: List[ItemPasta] = []
        keep = set(keep)
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            continue
                        st = entry.stat(follow_symlinks=False)
                        mtime = st.st_mtime
                        ctime = getattr(st, "st_birthtime", st.st_ctime)
                        perm = stat.filemode(st.st_mode)

                        if entry.is_dir(follow_symlinks=False):
                            dir_stats = self.stats(entry.path)
                            maior_str = (
                                f"{dir_stats.maior_arquivo_nome} ({formatar_tamanho(dir_stats.maior_arquivo_tam)})"
                                if dir_stats.maior_arquivo_nome
                                else "—"
                            )
                            items.append(ItemPasta(
                                nome=entry.name,
                                tamanho=dir_stats.tamanho,
                                eh_pasta=True,
                                arquivos=dir_stats.arquivos,
                                subpastas=dir_stats.subpastas,
                                modificado_em=mtime,
                                criado_em=ctime,
                                permissoes=perm,
                                tipo_detalhado="Pasta",
                                maior_arquivo=maior_str,
                            ))
                        else:
                            items.append(ItemPasta(
                                nome=entry.name,
                                tamanho=st.st_size,
                                eh_pasta=False,
                                arquivos=1,
                                subpastas=0,
                                modificado_em=mtime,
                                criado_em=ctime,
                                permissoes=perm,
                                tipo_detalhado=formatar_tipo_item(entry.name, False),
                                maior_arquivo="—",
                            ))
                    except OSError:
                        continue
        except OSError:
            pass

        items = [item for item in items if item.tamanho > 0]
        items.sort(key=lambda item: -item.tamanho)
        if len(items) > max_items:
            fixed = []
            rest = []
            for index, item in enumerate(items):
                (fixed if index < max_items - 1 or item.nome in keep else rest).append(item)
            if rest:
                mtimes = [i.modificado_em for i in rest if i.modificado_em is not None]
                rest_arquivos = sum(i.arquivos for i in rest)
                rest_subpastas = sum(i.subpastas + (1 if i.eh_pasta else 0) for i in rest)
                fixed.append(ItemPasta(
                    nome=f"Outros ({len(rest)} itens)",
                    tamanho=sum(item.tamanho for item in rest),
                    eh_pasta=None,
                    arquivos=rest_arquivos,
                    subpastas=rest_subpastas,
                    modificado_em=max(mtimes) if mtimes else None,
                    criado_em=None,
                    permissoes="—",
                    tipo_detalhado="Agrupado",
                    maior_arquivo=f"{rest[0].nome} ({formatar_tamanho(rest[0].tamanho)})",
                ))
            items = fixed
        return items

    @staticmethod
    def subfolders(path: str) -> List[str]:
        try:
            with os.scandir(path) as entries:
                names = [
                    entry.name for entry in entries
                    if entry.is_dir(follow_symlinks=False) and not entry.is_symlink()
                ]
        except OSError:
            return []
        return sorted(names, key=str.lower)


def parent_analysis_path(path: str, root: str, include_root_parent: bool) -> Tuple[str, bool]:
    parent = os.path.dirname(path)
    has_parent = bool(parent and parent != path and (path != root or include_root_parent))
    return parent, has_parent
