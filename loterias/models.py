"""Estruturas de dados compartilhadas (sorteios, apostas, prêmios)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Iterator, Optional


@dataclass(frozen=True)
class PrizeTier:
    """Rateio de uma faixa num concurso, como informado pela Caixa."""

    faixa: int
    description: str
    winners: int
    amount: float


@dataclass(frozen=True)
class Draw:
    """Resultado de um concurso.

    Attributes:
        game: Slug da loteria.
        contest: Número do concurso.
        date: Data do sorteio.
        numbers: Dezenas sorteadas, ordenadas.
        numbers2: Dezenas do 2º sorteio (Dupla Sena), ordenadas.
        trevos: Trevos sorteados (+Milionária).
        extra: Time do Coração ou Mês da Sorte, normalizado.
        prizes: Rateio por faixa.
        accumulated: Se o prêmio principal acumulou.
        next_date: Data prevista do próximo concurso.
        next_estimate: Estimativa de prêmio do próximo concurso (R$).
    """

    game: str
    contest: int
    date: dt.date
    numbers: tuple[int, ...]
    numbers2: tuple[int, ...] = ()
    trevos: tuple[int, ...] = ()
    extra: str = ""
    prizes: tuple[PrizeTier, ...] = ()
    accumulated: bool = False
    next_date: Optional[dt.date] = None
    next_estimate: Optional[float] = None

    def number_sets(self) -> Iterator[tuple[int, ...]]:
        """Itera sobre os conjuntos sorteados (1 ou 2, no caso da Dupla Sena)."""
        yield self.numbers
        if self.numbers2:
            yield self.numbers2

    def prize_amount(self, faixa: int) -> Optional[float]:
        """Valor pago por ganhador numa faixa, se a Caixa já divulgou."""
        for tier in self.prizes:
            if tier.faixa == faixa:
                return tier.amount
        return None


@dataclass(frozen=True)
class Bet:
    """Uma aposta (simples ou com mais dezenas).

    Attributes:
        numbers: Dezenas marcadas, ordenadas.
        trevos: Trevos marcados (+Milionária).
        extra: Mês da Sorte / Time do Coração escolhido (opcional).
    """

    numbers: tuple[int, ...]
    trevos: tuple[int, ...] = ()
    extra: str = ""

    def as_text(self) -> str:
        """Representação curta, ex.: ``"05 12 23 34 45 56 | trevos 1 4"``."""
        text = " ".join(f"{n:02d}" for n in self.numbers)
        if self.trevos:
            text += " | trevos " + " ".join(str(t) for t in self.trevos)
        if self.extra:
            text += f" | {self.extra}"
        return text


@dataclass
class SavedBet:
    """Aposta persistida em "Meus jogos"."""

    id: int
    game: str
    label: str
    bet: Bet
    created_at: str
    target_contest: Optional[int] = None
    tags: list[str] = field(default_factory=list)


def parse_numbers(text: str) -> list[int]:
    """Extrai dezenas de um texto livre ("5, 12 23-34;45").

    Args:
        text: Texto digitado pelo usuário.

    Returns:
        Lista de inteiros na ordem em que aparecem.

    Raises:
        ValueError: Se houver algo que não seja número.
    """
    import re

    tokens = [tok for tok in re.split(r"[\s,;\-/]+", text.strip()) if tok]
    numbers: list[int] = []
    for tok in tokens:
        if not tok.isdigit():
            raise ValueError(f"'{tok}' não é uma dezena válida.")
        numbers.append(int(tok))
    return numbers
