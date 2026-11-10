"""Geração de jogos a partir do histórico.

Importante: em sorteios justos toda combinação tem a mesma chance. As
estratégias abaixo mudam *quais* números você escolhe, não a probabilidade de
ganhar. "Menos populares" é a única com efeito prático conhecido: reduz a
chance de dividir o prêmio com muita gente, porque evita datas e padrões.
"""

from __future__ import annotations

import math
import random
from collections import Counter, deque
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from loterias.games import GameSpec
from loterias.models import Bet, Draw
from loterias.stats import percentile

RECENT_WINDOW = 50


@dataclass(frozen=True)
class Strategy:
    """Descrição de uma estratégia para a interface."""

    key: str
    label: str
    description: str


STRATEGIES: dict[str, Strategy] = {s.key: s for s in (
    Strategy("mais_sorteados", "Mais sorteados",
             "O 1º jogo traz as dezenas que mais saíram em toda a história; os demais "
             "sorteiam com peso proporcional à frequência."),
    Strategy("quentes", "Quentes (recentes)",
             f"Favorece as dezenas que mais saíram nos últimos {RECENT_WINDOW} concursos."),
    Strategy("atrasados", "Atrasados",
             "Favorece as dezenas que estão há mais tempo sem sair."),
    Strategy("equilibrado", "Equilibrado",
             "Aleatório, mas só aceita jogos com soma e par/ímpar dentro da faixa "
             "em que caem 80% dos sorteios reais."),
    Strategy("menos_populares", "Menos populares",
             "Evita datas (1–31) e sequências. Não aumenta a chance de ganhar, mas "
             "reduz a chance de dividir o prêmio."),
    Strategy("aleatorio", "Aleatório puro",
             "Surpresinha: todas as dezenas com o mesmo peso. Serve de referência."),
)}


def strategies_for(spec: GameSpec) -> list[Strategy]:
    """Estratégias que fazem sentido para a loteria (ex.: sem "menos populares" até 31)."""
    return [s for s in STRATEGIES.values()
            if s.key != "menos_populares" or spec.max_number > 31]


class StrategyContext:
    """Estatísticas acumuladas usadas pelas estratégias (atualizáveis incrementalmente).

    Args:
        spec: Regras da loteria.
    """

    def __init__(self, spec: GameSpec) -> None:
        self.spec = spec
        self.count = 0
        self.freq: Counter[int] = Counter()
        self.recent_freq: Counter[int] = Counter()
        self._recent: deque[tuple[int, ...]] = deque()
        self.last_seen: dict[int, int] = {}
        self.trevo_freq: Counter[int] = Counter()
        self.extra_freq: Counter[str] = Counter()
        self.sum_band: tuple[float, float] = (0.0, math.inf)
        self.odd_band: tuple[float, float] = (0.0, math.inf)

    @classmethod
    def from_draws(cls, spec: GameSpec, draws: Sequence[Draw]) -> "StrategyContext":
        """Constrói o contexto a partir de todo o histórico informado."""
        ctx = cls(spec)
        for draw in draws:
            ctx.add(draw)
        ctx.fit_bands(draws)
        return ctx

    def add(self, draw: Draw) -> None:
        """Incorpora um novo sorteio."""
        self.count += 1
        flat = tuple(n for s in draw.number_sets() for n in s)
        self.freq.update(flat)
        self._recent.append(flat)
        self.recent_freq.update(flat)
        if len(self._recent) > RECENT_WINDOW:
            self.recent_freq.subtract(self._recent.popleft())
        for n in flat:
            self.last_seen[n] = self.count
        self.trevo_freq.update(draw.trevos)
        if draw.extra:
            self.extra_freq[draw.extra] += 1

    def fit_bands(self, draws: Sequence[Draw]) -> None:
        """Calcula as faixas de soma e de ímpares que cobrem 80% dos sorteios."""
        sets = [s for d in draws for s in d.number_sets()]
        if len(sets) < 20:
            return
        sums = [sum(s) for s in sets]
        odds = [sum(n % 2 for n in s) for s in sets]
        self.sum_band = (percentile(sums, 10), percentile(sums, 90))
        self.odd_band = (percentile(odds, 10), percentile(odds, 90))

    def age(self, n: int) -> int:
        """Concursos desde a última aparição da dezena."""
        return self.count - self.last_seen.get(n, 0)


def _weights(strategy: str, ctx: StrategyContext) -> dict[int, float]:
    """Peso de cada dezena para a estratégia."""
    spec = ctx.spec
    if strategy == "mais_sorteados":
        return {n: ctx.freq[n] + 1.0 for n in spec.numbers}
    if strategy == "quentes":
        return {n: max(ctx.recent_freq[n], 0) + 0.5 for n in spec.numbers}
    if strategy == "atrasados":
        return {n: ctx.age(n) + 1.0 for n in spec.numbers}
    if strategy == "menos_populares":
        return {n: (2.5 if n > 31 else 1.0) for n in spec.numbers}
    return {n: 1.0 for n in spec.numbers}


def _weighted_sample(weights: dict[int, float], k: int, rng: random.Random) -> tuple[int, ...]:
    """Amostra ``k`` itens distintos com probabilidade proporcional ao peso."""
    keyed = sorted(weights, key=lambda n: rng.random() ** (1.0 / weights[n]), reverse=True)
    return tuple(sorted(keyed[:k]))


def _longest_run(numbers: Sequence[int]) -> int:
    """Maior sequência de dezenas consecutivas."""
    best = run = 1
    for a, b in zip(numbers, numbers[1:], strict=False):
        run = run + 1 if b == a + 1 else 1
        best = max(best, run)
    return best if numbers else 0


def _accept(strategy: str, numbers: tuple[int, ...], ctx: StrategyContext) -> bool:
    """Filtros das estratégias "equilibrado" e "menos populares"."""
    k = ctx.spec.draw_size
    scale = len(numbers) / k
    if strategy == "equilibrado":
        low_s, high_s = ctx.sum_band
        low_o, high_o = ctx.odd_band
        odds = sum(n % 2 for n in numbers)
        return (low_s * scale <= sum(numbers) <= high_s * scale
                and math.floor(low_o * scale) <= odds <= math.ceil(high_o * scale))
    if strategy == "menos_populares":
        return _longest_run(numbers) < 3 and sum(n > 31 for n in numbers) >= len(numbers) / 2
    return True


def default_max_overlap(spec: GameSpec, n_numbers: int) -> int:
    """Máximo de dezenas em comum entre dois jogos do mesmo lote."""
    expected = n_numbers * n_numbers / spec.pool_size
    return min(n_numbers - 1, max(math.ceil(expected) + 1, n_numbers // 2))


def _pick_trevos(strategy: str, ctx: StrategyContext, n_trevos: int,
                 rng: random.Random) -> tuple[int, ...]:
    """Escolhe os trevos (+Milionária)."""
    spec = ctx.spec
    if not spec.has_trevos:
        return ()
    if strategy in ("mais_sorteados", "quentes"):
        weights = {t: ctx.trevo_freq[t] + 1.0 for t in range(1, spec.trevo_max + 1)}
    else:
        weights = {t: 1.0 for t in range(1, spec.trevo_max + 1)}
    return _weighted_sample(weights, n_trevos, rng)


def _pick_extra(strategy: str, ctx: StrategyContext, rng: random.Random) -> str:
    """Sugere o Mês da Sorte (Dia de Sorte)."""
    options = ctx.spec.extra_options
    if not options:
        return ""
    if strategy == "mais_sorteados" and ctx.extra_freq:
        return ctx.extra_freq.most_common(1)[0][0]
    return rng.choice(options)


def generate_games(spec: GameSpec, ctx: StrategyContext, strategy: str, n_numbers: int,
                   n_games: int = 1, rng: Optional[random.Random] = None,
                   n_trevos: int = 2, max_overlap: Optional[int] = None,
                   progress: Optional[Callable[[int, int], None]] = None) -> list[Bet]:
    """Gera jogos distintos e diversificados.

    Args:
        spec: Regras da loteria.
        ctx: Estatísticas do histórico (:meth:`StrategyContext.from_draws`).
        strategy: Chave de :data:`STRATEGIES`.
        n_numbers: Dezenas por jogo.
        n_games: Quantidade de jogos (1–500).
        rng: Gerador aleatório (passe um com semente para resultados reproduzíveis).
        n_trevos: Trevos por jogo (+Milionária).
        max_overlap: Máximo de dezenas em comum entre jogos; padrão automático.
        progress: Callback ``(feitos, total)``.

    Returns:
        Lista de :class:`Bet` sem repetições.

    Raises:
        ValueError: Parâmetros fora dos limites, com mensagem para o usuário.
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"Estratégia desconhecida: {strategy}")
    spec.bet_cost(n_numbers, n_trevos)  # valida limites de dezenas e trevos
    if not 1 <= n_games <= 500:
        raise ValueError("Gere de 1 a 500 jogos por vez.")
    rng = rng or random.Random()
    weights = _weights(strategy, ctx)
    overlap = default_max_overlap(spec, n_numbers) if max_overlap is None else max_overlap
    games: list[Bet] = []
    seen: set[tuple[int, ...]] = set()

    if strategy == "mais_sorteados":
        top = tuple(sorted(sorted(spec.numbers, key=lambda n: (-ctx.freq[n], n))[:n_numbers]))
        games.append(Bet(top, _pick_trevos(strategy, ctx, n_trevos, rng),
                         _pick_extra(strategy, ctx, rng)))
        seen.add(top)

    attempts = 0
    while len(games) < n_games:
        attempts += 1
        if attempts % 300 == 0 and overlap < n_numbers - 1:
            overlap += 1  # relaxa a diversidade se estiver difícil encontrar jogos
        if attempts > 20000:
            raise ValueError("Não foi possível gerar tantos jogos distintos; reduza a quantidade.")
        candidate = _weighted_sample(weights, n_numbers, rng)
        if candidate in seen:
            continue
        if attempts % 300 < 250 and not _accept(strategy, candidate, ctx):
            continue
        cset = set(candidate)
        if any(len(cset.intersection(g.numbers)) > overlap for g in games):
            continue
        seen.add(candidate)
        games.append(Bet(candidate, _pick_trevos(strategy, ctx, n_trevos, rng),
                         _pick_extra(strategy, ctx, rng)))
        if progress:
            progress(len(games), n_games)
    return games
