"""Ponto único de montagem dos serviços (usado pela CLI e pela GUI)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from loterias.api_client import LotteryApiClient
from loterias.games import apply_price_overrides
from loterias.migration import run_migrations
from loterias.settings import PROJECT_ROOT, Settings, default_db_path
from loterias.storage import Storage
from loterias.updater import ResultSource, Updater

logger = logging.getLogger(__name__)


@dataclass
class Services:
    """Agrupa configurações, banco e atualizador."""

    settings: Settings
    storage: Storage
    updater: Updater
    client: Optional[LotteryApiClient] = None

    def close(self) -> None:
        """Libera conexões HTTP abertas."""
        if self.client is not None:
            self.client.close()


def build_services(db_path: Optional[Path] = None,
                   source: Optional[ResultSource] = None,
                   migrate: bool = True) -> Services:
    """Cria os serviços com as preferências do usuário aplicadas.

    Args:
        db_path: Banco alternativo (padrão: ``data/loterias.db``).
        source: Fonte de resultados alternativa (testes); padrão: APIs públicas.
        migrate: Importa a base antiga da Mega-Sena, se existir.
    """
    settings = Settings.load()
    apply_price_overrides(settings.prices)
    storage = Storage(db_path or default_db_path())
    if migrate:
        run_migrations(storage, PROJECT_ROOT)
    client = None
    if source is None:
        client = LotteryApiClient()
        source = client
    return Services(settings, storage, Updater(storage, source), client)
