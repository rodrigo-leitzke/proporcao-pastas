"""Modelos usados pelos casos de uso da aplicacao."""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class FolderStats:
    tamanho: int = 0
    arquivos: int = 0
    subpastas: int = 0
    maior_arquivo_nome: str = ""
    maior_arquivo_tam: int = 0


@dataclass(frozen=True)
class ItemPasta:
    nome: str
    tamanho: int
    eh_pasta: Optional[bool]
    arquivos: int = 0
    subpastas: int = 0
    modificado_em: Optional[float] = None
    criado_em: Optional[float] = None
    permissoes: str = "—"
    tipo_detalhado: str = "—"
    maior_arquivo: str = "—"

    def __iter__(self):
        """Permite a transicao gradual do formato de tupla legado."""
        return iter((self.nome, self.tamanho, self.eh_pasta))

    def __getitem__(self, index: int):
        return (self.nome, self.tamanho, self.eh_pasta)[index]
