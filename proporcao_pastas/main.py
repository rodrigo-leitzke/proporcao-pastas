"""Ponto de entrada da aplicacao."""
import os
import sys

from proporcao_pastas.infrastructure.windows_context_menu import configure_context_menu


def main() -> None:
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
        path, include_root_parent = arg.strip('"'), True
        if len(path) == 2 and path[1] == ":":
            path += "\\"
    else:
        root = tk.Tk()
        root.withdraw()
        path, include_root_parent = filedialog.askdirectory(
            title="Escolha a pasta inicial"
        ), False
        root.destroy()
    if path:
        App(os.path.normpath(os.path.abspath(path)), include_root_parent).rodar()


if __name__ == "__main__":
    main()
