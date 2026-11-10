"""Avisos de prêmio: confere "Meus jogos" e os bolões quando sai um concurso novo.

Cada concurso gera aviso uma única vez (marcado em ``meta``), seja pela
interface, pela CLI ou pela tarefa agendada.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from loterias import bolao as bl
from loterias.checker import check_bet
from loterias.formatting import brl
from loterias.games import get_game
from loterias.models import Draw
from loterias.storage import Storage
from loterias.updater import SyncResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PrizeAlert:
    """Um jogo salvo ou bolão premiado."""

    game: str
    contest: int
    kind: str
    label: str
    detail: str
    total: float

    def title(self) -> str:
        """Título curto da notificação."""
        return f"{get_game(self.game).name} {self.contest}: {self.kind} premiado!"

    def message(self) -> str:
        """Corpo da notificação."""
        value = f" · {brl(self.total)}" if self.total else ""
        return f"{self.label}: {self.detail}{value}"


def _applies(target: int | None, contest: int) -> bool:
    """Jogo vale para o concurso (sem concurso definido vale para todos)."""
    return target is None or target == contest


def find_alerts(storage: Storage, draw: Draw) -> list[PrizeAlert]:
    """Jogos salvos e bolões premiados num concurso.

    Args:
        storage: Base local.
        draw: Resultado a conferir.

    Returns:
        Avisos encontrados (lista vazia se nada foi premiado).
    """
    spec = get_game(draw.game)
    alerts: list[PrizeAlert] = []
    for saved in storage.list_bets(spec.slug):
        if not _applies(saved.target_contest, draw.contest):
            continue
        result = check_bet(spec, saved.bet, draw)
        if result.won:
            alerts.append(PrizeAlert(spec.slug, draw.contest, "jogo", saved.label,
                                     result.summary(), result.total_prize))
    for bolao_id, name, _updated in storage.list_boloes(spec.slug):
        payload = storage.load_bolao(bolao_id)
        if payload is None:
            continue
        try:
            bolao = bl.Bolao.from_dict(payload, bolao_id)
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Bolão %s ilegível, ignorado nos avisos: %s", bolao_id, exc)
            continue
        if not _applies(bolao.target_contest, draw.contest):
            continue
        check = bl.check_bolao(spec, bolao, draw)
        if check.winning_bets:
            alerts.append(PrizeAlert(spec.slug, draw.contest, "bolão", f"Bolão {name}",
                                     f"{len(check.winning_bets)} jogo(s) premiado(s)",
                                     check.total_prize))
    return alerts


def check_new_results(storage: Storage, results: Iterable[SyncResult]) -> list[PrizeAlert]:
    """Avisos dos concursos recém-baixados, sem repetir concursos já avisados."""
    alerts: list[PrizeAlert] = []
    for result in results:
        if not result.ok or not result.added:
            continue
        draw = storage.latest_draw(result.game)
        if draw is None:
            continue
        key = f"alerted:{result.game}"
        if storage.get_meta(key) == str(draw.contest):
            continue
        alerts.extend(find_alerts(storage, draw))
        storage.set_meta(key, str(draw.contest))
    if alerts:
        logger.info("%d aviso(s) de prêmio gerado(s)", len(alerts))
    return alerts
