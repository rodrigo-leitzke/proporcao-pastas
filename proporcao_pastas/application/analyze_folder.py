"""Orquestracao da analise de uma pasta."""
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from proporcao_pastas.domain.models import FolderStats, ItemPasta
from proporcao_pastas.infrastructure.file_system import FileSystemScanner, parent_analysis_path


@dataclass(frozen=True)
class FolderAnalysis:
    path: str
    total: int
    parent_total: Optional[int]
    items: List[ItemPasta]
    folder_stats: FolderStats = field(default_factory=FolderStats)
    cache_updated_at: Optional[float] = None
    global_cache_updated_at: Optional[float] = None
    is_outdated: bool = False


class AnalyzeFolder:
    def __init__(self, scanner: FileSystemScanner) -> None:
        self.scanner = scanner

    def execute(
        self,
        path: str,
        root: str,
        include_root_parent: bool,
        keep: Iterable[str] = (),
    ) -> FolderAnalysis:
        folder_stats = self.scanner.stats(path)
        return self._montar(path, root, include_root_parent, keep, folder_stats)

    def refresh(
        self,
        path: str,
        root: str,
        include_root_parent: bool,
        keep: Iterable[str] = (),
        progresso=None,
    ) -> FolderAnalysis:
        """Revarre a pasta e devolve a analise ja com o cache novo."""
        folder_stats = self.scanner.refresh_folder(path, progresso=progresso)
        return self._montar(path, root, include_root_parent, keep, folder_stats)

    def _montar(self, path, root, include_root_parent, keep, folder_stats) -> FolderAnalysis:
        parent, has_parent = parent_analysis_path(path, root, include_root_parent)
        parent_total = self.scanner.size(parent) if has_parent else None
        return FolderAnalysis(
            path=path,
            total=folder_stats.tamanho,
            parent_total=parent_total,
            items=self.scanner.children(path, keep),
            folder_stats=folder_stats,
            cache_updated_at=folder_stats.cache_updated_at,
            global_cache_updated_at=self.scanner.ultima_atualizacao_global(),
            is_outdated=self.scanner.is_folder_outdated(path),
        )
