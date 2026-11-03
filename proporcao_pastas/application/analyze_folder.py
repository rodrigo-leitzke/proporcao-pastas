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
        parent, has_parent = parent_analysis_path(path, root, include_root_parent)
        parent_total = self.scanner.size(parent) if has_parent else None
        folder_stats = self.scanner.stats(path)
        return FolderAnalysis(
            path=path,
            total=folder_stats.tamanho,
            parent_total=parent_total,
            items=self.scanner.children(path, keep),
            folder_stats=folder_stats,
        )
