"""Move os arquivos da versão 1.x para ``_legado/`` (nada é apagado).

A versão 2.0 vive no pacote ``loterias/`` e em ``main.py``. Os arquivos antigos
(``mega_sena_app.py``, ``gui_main.py``, testes temporários, bancos antigos etc.)
ficam na raiz e confundem quem abre o projeto. Este script os move para
``_legado/``, preservando a estrutura. Os bancos antigos continuam sendo
importados automaticamente de lá na primeira execução.

Uso::

    python scripts/limpar_legado.py          # mostra o que será movido e pede confirmação
    python scripts/limpar_legado.py --sim    # move sem perguntar
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEGACY_DIR = ROOT / "_legado"

LEGACY_FILES = [
    "__init__.py", "analysis.py", "backtest.py", "cli.py", "config.py", "constants.py",
    "db_utils.py", "demo_multiple_backtest.py", "gui.py", "gui_db.py", "gui_main.py",
    "gui_utils.py", "logging_config.py", "mega_sena_app.py", "utils.py", "tests.py",
    "tests_fixed.py", "mega_sena_config.ini", "teste.csv", "megasena.db", "user_sets.db",
    "backtest.db", "BACKTEST_INSIGHTS_EXAMPLES.md", "BACKTEST_INSIGHTS_FEATURE.md",
    "BACKTEST_INSIGHTS_IMPLEMENTATION.md", "BACKTEST_INSIGHTS_README.txt",
    "BACKTEST_INSIGHTS_SUMMARY.txt", "GETTING_STARTED_MULTIPLE_BACKTEST.md",
    "IMPLEMENTATION_SUMMARY.md", "MELHORIAS_IMPLEMENTADAS.md", "MULTIPLE_BACKTEST_FEATURE.md",
    "RELEASE_NOTES_v1.3.0.md", "SOLUCAO_DATABASE_LOCKED.md", "scripts/clean_markdown.py",
]
LEGACY_PATTERNS = ["tmp_*.py", "tmp*.csv", "tmp*.json"]


def find_legacy() -> list[Path]:
    """Arquivos antigos presentes na raiz do projeto."""
    found = [ROOT / name for name in LEGACY_FILES if (ROOT / name).exists()]
    for pattern in LEGACY_PATTERNS:
        found += sorted(p for p in ROOT.glob(pattern) if p.is_file())
    return found


def move_all(paths: list[Path]) -> int:
    """Move cada arquivo para ``_legado/`` e devolve quantos foram movidos."""
    moved = 0
    for path in paths:
        target = LEGACY_DIR / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target = target.with_name(f"{target.stem}_1{target.suffix}")
        try:
            shutil.move(str(path), str(target))
            moved += 1
        except OSError as exc:
            logging.error("Não foi possível mover %s: %s", path.name, exc)
    for cache in ROOT.glob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    return moved


def main() -> int:
    """Lista, confirma e move."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sim", action="store_true", help="não pedir confirmação")
    args = parser.parse_args()
    paths = find_legacy()
    if not paths:
        logging.info("Nenhum arquivo legado encontrado. Nada a fazer.")
        return 0
    logging.info("Serão movidos para %s:", LEGACY_DIR)
    for path in paths:
        logging.info("  %s", path.relative_to(ROOT))
    if not args.sim and input("Continuar? [s/N] ").strip().lower() not in ("s", "sim"):
        logging.info("Cancelado.")
        return 1
    logging.info("%d arquivo(s) movido(s). Revise e apague _legado/ quando quiser.",
                 move_all(paths))
    return 0


if __name__ == "__main__":
    sys.exit(main())
