#!/usr/bin/env python3
"""Loterias Estatístico — ponto de entrada.

* ``python main.py``            abre a interface gráfica.
* ``python main.py <comando>``  usa a linha de comando (``python main.py -h``).
"""

from __future__ import annotations

import sys

from loterias.logging_setup import setup_logging


def run() -> int:
    """Escolhe entre GUI (sem argumentos) e CLI."""
    setup_logging()
    if len(sys.argv) > 1:
        from loterias.cli import main as cli_main

        return cli_main(sys.argv[1:])
    from loterias.gui.app import launch

    launch()
    return 0


if __name__ == "__main__":
    sys.exit(run())
