"""Sincronização incremental das bases de cada loteria.

Fluxo de :meth:`Updater.sync_game`:

1. Descobre o último concurso publicado.
2. Se faltarem muitos concursos (base nova), baixa o histórico inteiro de uma vez.
3. Preenche os buracos restantes concurso a concurso.
4. Grava em lotes, então uma interrupção não perde o que já foi baixado.
"""

from __future__ import annotations

import datetime as dt
import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Protocol

from loterias.games import GAMES, GameSpec, get_game
from loterias.models import Draw
from loterias.storage import Storage

logger = logging.getLogger(__name__)

ProgressFn = Callable[[str, int, int], None]
"""``progress(slug, feitos, total)``."""

BULK_THRESHOLD = 30
"""A partir de quantos concursos faltantes vale baixar o histórico completo."""

MAX_INDIVIDUAL = 400
"""Limite de requisições individuais por sincronização (evita abusar da API)."""


class ResultSource(Protocol):
    """Contrato mínimo do cliente de API (facilita testes com dublês)."""

    def fetch_latest(self, spec: GameSpec) -> Draw:
        """Último concurso."""

    def fetch_contest(self, spec: GameSpec, contest: int) -> Draw:
        """Um concurso específico."""

    def fetch_all(self, spec: GameSpec) -> list[Draw]:
        """Histórico completo."""


@dataclass
class SyncResult:
    """Resumo da sincronização de uma loteria."""

    game: str
    added: int = 0
    latest_contest: int = 0
    error: str = ""
    up_to_date: bool = False

    @property
    def ok(self) -> bool:
        """``True`` se não houve erro."""
        return not self.error

    def message(self) -> str:
        """Texto curto para mostrar ao usuário."""
        name = get_game(self.game).name
        if self.error:
            return f"{name}: falha ao atualizar ({self.error})"
        if self.added:
            return f"{name}: {self.added} concurso(s) novo(s), até o {self.latest_contest}"
        return f"{name}: já atualizada (concurso {self.latest_contest})"


class Updater:
    """Mantém a base local em dia com as APIs.

    Args:
        storage: Base local.
        source: Cliente de API (``LotteryApiClient`` ou dublê de teste).
        request_delay: Pausa entre requisições individuais, em segundos.
    """

    def __init__(self, storage: Storage, source: ResultSource,
                 request_delay: float = 0.15) -> None:
        self.storage = storage
        self.source = source
        self.request_delay = request_delay

    def sync_game(self, slug: str, progress: Optional[ProgressFn] = None,
                  cancel: Optional[threading.Event] = None) -> SyncResult:
        """Atualiza uma loteria. Nunca levanta exceção: erros vão em ``SyncResult.error``."""
        spec = get_game(slug)
        result = SyncResult(spec.slug)
        try:
            latest = self.source.fetch_latest(spec)
        except Exception as exc:  # noqa: BLE001 - qualquer falha vira mensagem ao usuário
            logger.warning("%s: não foi possível consultar o último concurso: %s",
                           spec.name, exc)
            result.error = "APIs indisponíveis, verifique a internet"
            result.latest_contest = self.storage.latest_contest(spec.slug)
            return result

        result.latest_contest = latest.contest
        before = self.storage.count_draws(spec.slug)
        missing = self.storage.missing_contests(spec.slug, latest.contest - 1)
        self.storage.upsert_draws([latest])
        if missing:
            if len(missing) >= BULK_THRESHOLD:
                missing = self._bulk(spec, missing, progress)
            self._individual(spec, missing, progress, cancel)
        result.added = self.storage.count_draws(spec.slug) - before
        result.up_to_date = not self.storage.missing_contests(spec.slug, latest.contest)
        self._touch(spec)
        logger.info(result.message())
        return result

    def _bulk(self, spec: GameSpec, missing: list[int],
              progress: Optional[ProgressFn]) -> list[int]:
        """Baixa o histórico completo e devolve o que ainda falta."""
        if progress:
            progress(spec.slug, 0, len(missing))
        try:
            draws = self.source.fetch_all(spec)
        except Exception as exc:  # noqa: BLE001 - cai para o modo individual
            logger.warning("%s: histórico completo indisponível (%s); baixando um a um",
                           spec.name, exc)
            return missing
        wanted = set(missing)
        self.storage.upsert_draws(d for d in draws if d.contest in wanted)
        return self.storage.missing_contests(spec.slug, max(missing))

    def _individual(self, spec: GameSpec, missing: list[int],
                    progress: Optional[ProgressFn],
                    cancel: Optional[threading.Event]) -> None:
        """Baixa concursos um a um, gravando em lotes de 20."""
        todo = missing[-MAX_INDIVIDUAL:]
        if len(missing) > len(todo):
            logger.warning("%s: %d concursos antigos ficarão para a próxima atualização",
                           spec.name, len(missing) - len(todo))
        batch: list[Draw] = []
        for done, contest in enumerate(todo, start=1):
            if cancel is not None and cancel.is_set():
                logger.info("%s: atualização cancelada", spec.name)
                break
            try:
                batch.append(self.source.fetch_contest(spec, contest))
            except Exception as exc:  # noqa: BLE001 - concurso isolado não interrompe o resto
                logger.warning("%s: concurso %d não baixado: %s", spec.name, contest, exc)
            if len(batch) >= 20:
                self.storage.upsert_draws(batch)
                batch.clear()
            if progress:
                progress(spec.slug, done, len(todo))
            if self.request_delay:
                time.sleep(self.request_delay)
        self.storage.upsert_draws(batch)

    def _touch(self, spec: GameSpec) -> None:
        """Registra o horário da última sincronização bem-sucedida."""
        self.storage.set_meta(f"last_sync:{spec.slug}",
                              dt.datetime.now().isoformat(timespec="seconds"))

    def sync_all(self, slugs: Optional[Iterable[str]] = None,
                 progress: Optional[ProgressFn] = None,
                 cancel: Optional[threading.Event] = None) -> list[SyncResult]:
        """Atualiza várias loterias (todas, por padrão)."""
        results = []
        for slug in slugs or list(GAMES):
            if cancel is not None and cancel.is_set():
                break
            results.append(self.sync_game(slug, progress, cancel))
        return results

    def last_sync(self, slug: str) -> Optional[dt.datetime]:
        """Horário da última sincronização bem-sucedida, se houver."""
        raw = self.storage.get_meta(f"last_sync:{slug}")
        try:
            return dt.datetime.fromisoformat(raw) if raw else None
        except ValueError:
            logger.warning("Metadado last_sync inválido para %s: %r", slug, raw)
            return None
