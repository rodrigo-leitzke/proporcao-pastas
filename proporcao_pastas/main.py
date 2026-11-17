"""Ponto de entrada da aplicacao."""
import os
import platform
import sys

from proporcao_pastas.infrastructure.windows_context_menu import configure_context_menu


def main() -> None:
    sistema = platform.system()
    is_windows = sistema == "Windows" or os.name == "nt"

    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg in ("--instalar", "--remover"):
        configure_context_menu(
            os.path.abspath(os.path.join(
                os.path.dirname(__file__), os.pardir, "proporcao_pastas.py"
            )),
            remove=arg == "--remover",
        )
        return

    from proporcao_pastas.presentation.tk_app import App
    from proporcao_pastas.infrastructure.system_roots import list_system_roots

    if arg:
        path, include_root_parent = os.path.expanduser(arg.strip('"')), True
        if is_windows and len(path) == 2 and path[1] == ":":
            path += "\\"
        if path:
            App(os.path.normpath(os.path.abspath(path)), include_root_parent).rodar()
        return

    raizes = list_system_roots()
    app = App(raizes[0], False)
    app.definir_raizes(raizes)
    app.rodar()


if __name__ == "__main__":
    main()
