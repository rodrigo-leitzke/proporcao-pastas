"""Leitura do sistema de arquivos usada pela aplicacao."""
import os
from typing import Iterable, List, Tuple

from proporcao_pastas.domain.models import ItemPasta


class FileSystemScanner:
    """Calcula tamanhos e lista o conteudo de pastas com cache em memoria."""

    def __init__(self) -> None:
        self._cache = {}

    def clear_cache(self) -> None:
        self._cache.clear()

    def size(self, path: str) -> int:
        if path in self._cache:
            return self._cache[path]

        total = 0
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            total += self.size(entry.path)
                        else:
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            pass
        self._cache[path] = total
        return total

    def children(self, path: str, keep: Iterable[str] = (), max_items: int = 8) -> List[ItemPasta]:
        items: List[ItemPasta] = []
        keep = set(keep)
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            items.append(ItemPasta(entry.name, self.size(entry.path), True))
                        else:
                            items.append(ItemPasta(
                                entry.name,
                                entry.stat(follow_symlinks=False).st_size,
                                False,
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
                fixed.append(ItemPasta(
                    f"Outros ({len(rest)} itens)",
                    sum(item.tamanho for item in rest),
                    None,
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
