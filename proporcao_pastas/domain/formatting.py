"""Formatacao de valores apresentada pela aplicacao."""
from datetime import datetime
import os
from typing import Optional


def formatar_tamanho(valor: float) -> str:
    """Formata bytes em B, KB, MB, GB ou TB."""
    for unidade in ("B", "KB", "MB", "GB", "TB"):
        if valor < 1024 or unidade == "TB":
            return f"{valor:.0f} {unidade}" if unidade == "B" else f"{valor:.2f} {unidade}"
        valor /= 1024


def clarear_cor(cor: str, fator: float = 0.65) -> str:
    """Mistura uma cor hexadecimal com branco."""
    rgb = (int(cor[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(int(c + (255 - c) * fator) for c in rgb)


def formatar_data(timestamp: Optional[float]) -> str:
    """Formata um timestamp POSIX em dd/mm/aaaa HH:MM."""
    if not timestamp:
        return "—"
    try:
        return datetime.fromtimestamp(timestamp).strftime("%d/%m/%Y %H:%M")
    except (OSError, OverflowError, ValueError):
        return "—"


def formatar_tipo_item(nome: str, eh_pasta: Optional[bool]) -> str:
    """Retorna 'Pasta', 'Arq (.ext)' ou 'Outros'."""
    if eh_pasta is None:
        return "Outros"
    if eh_pasta:
        return "Pasta"
    _, ext = os.path.splitext(nome)
    ext = ext.lower()
    if ext:
        return f"Arq ({ext})"
    return "Arquivo (s/ ext)"


def formatar_contagem(eh_pasta: Optional[bool], arquivos: int, subpastas: int) -> str:
    """Formata a quantidade de arquivos e subpastas de um item."""
    if eh_pasta is False:
        return "1 arq"
    if subpastas > 0:
        return f"{arquivos} arq, {subpastas} sub"
    return f"{arquivos} arq"
