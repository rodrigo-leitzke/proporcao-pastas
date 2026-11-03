"""Integracao opcional com o menu de contexto do Windows (com deteccao automatica de SO)."""
import os
import platform
import sys

from proporcao_pastas.infrastructure.macos_context_menu import configure_macos_context_menu


def configure_windows_context_menu(script_path: str, remove: bool = False) -> None:
    import winreg

    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable
    targets = {
        r"Software\Classes\Directory\shell\ProporcaoPastas": "%1",
        r"Software\Classes\Directory\Background\shell\ProporcaoPastas": "%V",
    }
    for key, variable in targets.items():
        if remove:
            for subkey in (key + r"\command", key):
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, subkey)
                except FileNotFoundError:
                    pass
            continue
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as registry_key:
            winreg.SetValueEx(
                registry_key, "", 0, winreg.REG_SZ, "Ver proporção de pastas"
            )
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key + r"\command") as registry_key:
            winreg.SetValueEx(
                registry_key,
                "",
                0,
                winreg.REG_SZ,
                f'"{pythonw}" "{script_path}" "{variable}"',
            )
    print("Menu removido." if remove else "Menu instalado: clique direito em uma pasta.")


def configure_context_menu(script_path: str, remove: bool = False) -> None:
    sistema = platform.system()
    if sistema == "Windows" or os.name == "nt":
        configure_windows_context_menu(script_path, remove=remove)
    elif sistema == "Darwin" or sys.platform == "darwin":
        configure_macos_context_menu(script_path, remove=remove)
    else:
        print(f"Integração de menu de contexto não suportada para o sistema: {sistema}.")
