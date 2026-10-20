"""Modelos usados pelos casos de uso da aplicacao."""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ItemPasta:
    nome: str
    tamanho: int
    eh_pasta: Optional[bool]

    def __iter__(self):
        """Permite a transicao gradual do formato de tupla legado."""
        return iter((self.nome, self.tamanho, self.eh_pasta))

    def __getitem__(self, index: int):
        return (self.nome, self.tamanho, self.eh_pasta)[index]
