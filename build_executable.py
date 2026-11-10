"""Gera um executável da interface com PyInstaller.

Uso::

    pip install pyinstaller
    python build_executable.py

O resultado fica em ``dist/LoteriasEstatistico/``. A pasta ``data/`` é criada ao
lado do executável na primeira execução e as bases são baixadas automaticamente.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build() -> int:
    """Executa o PyInstaller e devolve o código de saída."""
    try:
        import customtkinter
    except ImportError:
        logging.error("Instale as dependências antes: pip install -r requirements.txt")
        return 1
    ctk_path = Path(customtkinter.__file__).parent
    sep = ";" if sys.platform == "win32" else ":"
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed",
        "--name", "LoteriasEstatistico",
        "--add-data", f"{ctk_path}{sep}customtkinter",
        str(ROOT / "main.py"),
    ]
    logging.info("Executando: %s", " ".join(cmd))
    try:
        return subprocess.run(cmd, cwd=ROOT, check=False).returncode
    except OSError as exc:
        logging.error("PyInstaller não encontrado (pip install pyinstaller): %s", exc)
        return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(build())
