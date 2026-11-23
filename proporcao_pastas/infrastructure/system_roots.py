"""Raizes de disco e caminhos que a varredura deve ignorar."""
import os
import platform
import string
import sys
from typing import List

IS_WINDOWS = platform.system() == "Windows" or os.name == "nt"
IS_MAC = platform.system() == "Darwin" or sys.platform == "darwin"

# Firmlinks do APFS espelham /Users e /Applications; contar duas vezes inflaria o total.
IGNORADOS_MAC = ("/System/Volumes/Data", "/dev", "/proc", "/net", "/Volumes/Recovery")
# WinSxS e cheio de hardlinks (conta duas vezes); as outras travam ou negam leitura.
IGNORADOS_WINDOWS = (
    "\\windows\\winsxs",
    "\\system volume information",
    "\\$recycle.bin",
    "\\pagefile.sys",
    "\\hiberfil.sys",
    "\\swapfile.sys",
)


def list_system_roots() -> List[str]:
    """Raizes para montar a arvore: unidades no Windows, '/' nos demais."""
    if not IS_WINDOWS:
        return ["/"]
    # os.listdrives() existe so no Python 3.12+; o projeto suporta 3.8.
    return [f"{letra}:\\" for letra in string.ascii_uppercase if os.path.exists(f"{letra}:\\")]


def caminho_ignorado(path: str) -> bool:
    """Diz se o caminho deve ficar fora da varredura."""
    if IS_WINDOWS:
        baixo = path.lower().rstrip("\\")
        return any(baixo.endswith(sufixo) for sufixo in IGNORADOS_WINDOWS)
    if IS_MAC:
        return path.rstrip("/") in [i.rstrip("/") for i in IGNORADOS_MAC]
    return path.rstrip("/") in ("/dev", "/proc", "/sys", "/run")
