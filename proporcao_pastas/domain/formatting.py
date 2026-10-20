"""Formatacao de valores apresentada pela aplicacao."""


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
