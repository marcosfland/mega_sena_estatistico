"""Backtest "walk-forward": cada estratégia joga os concursos passados sem ver o futuro.

Para cada concurso ``i`` do período testado, a estratégia gera um jogo usando
apenas os concursos anteriores a ``i``; depois o jogo é conferido contra o
resultado real. O resultado é comparado com a média teórica de acertos de um
jogo aleatório, ``n · k / N``, o que mostra de forma honesta se alguma
estratégia se destaca do acaso.
"""

from __future__ import annotations

import random
import threading
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from loterias.checker import check_bet
from loterias.games import GameSpec
from loterias.generator import STRATEGIES, StrategyContext, generate_games
from loterias.models import Draw


@dataclass
class BacktestResult:
    """Desempenho de uma estratégia no período testado."""

    strategy: str
    contests: int = 0
    total_hits: int = 0
    distribution: Counter[int] = field(default_factory=Counter)
    wins: int = 0
    spent: float = 0.0
    won: float = 0.0
    unknown_prizes: int = 0

    @property
    def label(self) -> str:
        """Nome amigável da estratégia."""
        return STRATEGIES[self.strategy].label

    @property
    def mean_hits(self) -> float:
        """Média de acertos por concurso."""
        return self.total_hits / self.contests if self.contests else 0.0

    @property
    def win_rate(self) -> float:
        """Fração de concursos em que o jogo teria sido premiado."""
        return self.wins / self.contests if self.contests else 0.0


def expected_hits(spec: GameSpec, n_numbers: int) -> float:
    """Média teórica de acertos de um jogo qualquer (``n · k / N``)."""
    return n_numbers * spec.draw_size / spec.pool_size


def run_backtest(spec: GameSpec, draws: Sequence[Draw], strategies: Sequence[str],
                 n_contests: int = 200, n_numbers: Optional[int] = None,
                 seed: Optional[int] = None,
                 progress: Optional[Callable[[int, int], None]] = None,
                 cancel: Optional[threading.Event] = None) -> list[BacktestResult]:
    """Executa o backtest.

    Args:
        spec: Regras da loteria.
        draws: Histórico completo em ordem crescente.
        strategies: Chaves das estratégias a comparar.
        n_contests: Quantos concursos finais testar (10–2000).
        n_numbers: Dezenas por jogo (padrão: mínimo da loteria).
        seed: Semente para reprodutibilidade.
        progress: Callback ``(feitos, total)``.
        cancel: Evento que interrompe o teste.

    Returns:
        Um :class:`BacktestResult` por estratégia, na ordem pedida.

    Raises:
        ValueError: Se o histórico for curto demais ou os parâmetros inválidos.
    """
    n_numbers = n_numbers or spec.bet_min
    cost = spec.bet_cost(n_numbers)
    if not strategies:
        raise ValueError("Escolha ao menos uma estratégia.")
    unknown = [s for s in strategies if s not in STRATEGIES]
    if unknown:
        raise ValueError(f"Estratégias desconhecidas: {', '.join(unknown)}")
    if not 10 <= n_contests <= 2000:
        raise ValueError("Teste entre 10 e 2000 concursos.")
    if len(draws) < n_contests + 30:
        raise ValueError(f"Histórico insuficiente: são necessários ao menos "
                         f"{n_contests + 30} concursos (há {len(draws)}).")

    start = len(draws) - n_contests
    ctx = StrategyContext.from_draws(spec, draws[:start])
    rngs = {s: random.Random(None if seed is None else seed + i)
            for i, s in enumerate(strategies)}
    results = {s: BacktestResult(s) for s in strategies}

    for step, draw in enumerate(draws[start:], start=1):
        if cancel is not None and cancel.is_set():
            break
        for strategy in strategies:
            bet = generate_games(spec, ctx, strategy, n_numbers, 1, rngs[strategy])[0]
            checked = check_bet(spec, bet, draw)
            res = results[strategy]
            res.contests += 1
            res.total_hits += checked.hits[0]
            res.distribution[checked.hits[0]] += 1
            res.spent += cost
            if checked.won:
                res.wins += 1
                res.won += checked.total_prize
                res.unknown_prizes += int(checked.prize_pending)
        ctx.add(draw)
        if progress:
            progress(step, n_contests)
    return [results[s] for s in strategies]
