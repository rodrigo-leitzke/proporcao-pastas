"""Integracao opcional com o menu de contexto do Windows."""
import os
import sys


def configure_context_menu(script_path: str, remove: bool = False) -> None:
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
