"""Caminhos e preferências do usuário (``data/settings.json``)."""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

if getattr(sys, "frozen", False):  # executável PyInstaller: dados ao lado do .exe
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    """Pasta de dados (banco, configurações). Pode ser trocada por ``LOTERIAS_DATA_DIR``."""
    path = Path(os.getenv("LOTERIAS_DATA_DIR", PROJECT_ROOT / "data"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_db_path() -> Path:
    """Caminho do banco SQLite principal."""
    return data_dir() / "loterias.db"


@dataclass
class Settings:
    """Preferências persistidas.

    Attributes:
        auto_update: Atualiza as bases ao abrir o app e periodicamente.
        notifications: Avisa (notificação do sistema) quando um jogo salvo ou bolão ganha.
        update_interval_min: Intervalo entre verificações com o app aberto.
        appearance: ``"system"``, ``"light"`` ou ``"dark"``.
        last_game: Última loteria aberta.
        prices: Sobrescrita de preços por loteria (``slug -> R$``).
    """

    auto_update: bool = True
    notifications: bool = True
    update_interval_min: int = 30
    appearance: str = "system"
    last_game: str = "megasena"
    prices: dict[str, float] = field(default_factory=dict)

    _lock = threading.Lock()

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        """Lê as preferências; usa padrões se o arquivo não existir ou for inválido."""
        path = path or data_dir() / "settings.json"
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("settings.json ilegível (%s); usando padrões.", exc)
            return cls()
        known = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
        try:
            settings = cls(**known)
        except TypeError as exc:
            logger.warning("settings.json com campos inválidos (%s); usando padrões.", exc)
            return cls()
        settings.update_interval_min = max(5, int(settings.update_interval_min))
        if settings.appearance not in ("system", "light", "dark"):
            settings.appearance = "system"
        return settings

    def save(self, path: Path | None = None) -> None:
        """Grava as preferências de forma atômica."""
        path = path or data_dir() / "settings.json"
        with self._lock:
            tmp = path.with_suffix(".tmp")
            try:
                tmp.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False),
                               encoding="utf-8")
                tmp.replace(path)
            except OSError as exc:
                logger.error("Não foi possível salvar as preferências: %s", exc)
