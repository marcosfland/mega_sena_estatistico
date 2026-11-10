"""Configuração central de logs (console + arquivo rotativo em ``logs/``)."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from loterias.settings import PROJECT_ROOT

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s:%(lineno)d %(funcName)s() - %(message)s"
_configured = False


def setup_logging(level: int = logging.INFO, console: bool = True) -> None:
    """Configura o logger raiz uma única vez.

    Args:
        level: Nível mínimo de log.
        console: Também escreve no terminal.
    """
    global _configured
    if _configured:
        return
    log_dir = PROJECT_ROOT / "logs"
    root = logging.getLogger()
    root.setLevel(level)
    formatter = logging.Formatter(_FORMAT, "%Y-%m-%d %H:%M:%S")
    try:
        log_dir.mkdir(exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "loterias.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError as exc:
        logging.basicConfig(level=level)
        logging.getLogger(__name__).warning("Log em arquivo indisponível: %s", exc)
    if console:
        stream = logging.StreamHandler()
        stream.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        stream.setLevel(max(level, logging.ERROR))
        root.addHandler(stream)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    _configured = True
