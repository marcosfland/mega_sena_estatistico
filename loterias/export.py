"""Exportação de sorteios e jogos para CSV (abre direto no Excel com ``;``)."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Sequence

from loterias import columns
from loterias.formatting import brl, date_br
from loterias.games import GameSpec
from loterias.models import Bet, Draw

logger = logging.getLogger(__name__)


def export_draws_csv(spec: GameSpec, draws: Sequence[Draw], path: Path | str) -> Path:
    """Grava o histórico de sorteios.

    Raises:
        OSError: Se o arquivo não puder ser escrito.
    """
    path = Path(path)
    prefix = "Coluna " if spec.is_columns else "D"
    header = ["Concurso", "Data"] + [f"{prefix}{i}" for i in range(1, spec.draw_size + 1)]
    if spec.double_draw:
        header += [f"2º D{i}" for i in range(1, spec.draw_size + 1)]
    if spec.has_trevos:
        header += ["Trevo 1", "Trevo 2"]
    if spec.extra_name:
        header.append(spec.extra_name)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(header)
        for d in draws:
            values = columns.digits_of(d.numbers) if spec.is_columns else d.numbers
            row: list[object] = [d.contest, date_br(d.date), *values]
            if spec.double_draw:
                row += list(d.numbers2)
            if spec.has_trevos:
                row += list(d.trevos)
            if spec.extra_name:
                row.append(d.extra)
            writer.writerow(row)
    logger.info("Exportados %d sorteios de %s para %s", len(draws), spec.name, path)
    return path


def export_bets_csv(spec: GameSpec, bets: Sequence[Bet], path: Path | str) -> Path:
    """Grava uma lista de jogos com o custo de cada um.

    Raises:
        OSError: Se o arquivo não puder ser escrito.
    """
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["Jogo", "Dezenas", "Trevos", "Extra", "Custo"])
        for i, bet in enumerate(bets, start=1):
            writer.writerow([
                i, spec.format_bet(bet.numbers),
                " ".join(str(t) for t in bet.trevos), bet.extra,
                brl(spec.cost_of(bet.numbers, len(bet.trevos))),
            ])
    logger.info("Exportados %d jogos de %s para %s", len(bets), spec.name, path)
    return path
