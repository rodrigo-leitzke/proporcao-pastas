"""Ponto de entrada da aplicacao."""
import os
import platform
import sys

from proporcao_pastas.infrastructure.windows_context_menu import configure_context_menu


def main() -> None:
    sistema = platform.system()
    is_windows = sistema == "Windows" or os.name == "nt"
    is_mac = sistema == "Darwin" or sys.platform == "darwin"

    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg in ("--instalar", "--remover"):
        configure_context_menu(
            os.path.abspath(os.path.join(
                os.path.dirname(__file__), os.pardir, "proporcao_pastas.py"
            )),
            remove=arg == "--remover",
        )
        return

    from tkinter import filedialog
    import tkinter as tk
    from proporcao_pastas.presentation.tk_app import App

    if arg:
        path, include_root_parent = os.path.expanduser(arg.strip('"')), True
        if is_windows and len(path) == 2 and path[1] == ":":
            path += "\\"
        if path:
            App(os.path.normpath(os.path.abspath(path)), include_root_parent).rodar()
    else:
        root = tk.Tk()
        root.withdraw()
        if is_mac:
            root.update_idletasks()
        path, include_root_parent = filedialog.askdirectory(
            title="Escolha a pasta inicial"
        ), False
        if path:
            App(
                os.path.normpath(os.path.abspath(path)),
                include_root_parent,
                master=root,
            ).rodar()
        else:
            root.destroy()


if __name__ == "__main__":
    main()
