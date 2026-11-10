"""Estatísticas descritivas sobre o histórico de sorteios.

Todas as funções são puras (recebem a lista de sorteios e as regras do jogo) e
contam os dois sorteios da Dupla Sena como conjuntos independentes.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations
from typing import Sequence

from loterias.games import GameSpec
from loterias.models import Draw


def last_n(draws: Sequence[Draw], n: int | None) -> list[Draw]:
    """Os ``n`` concursos mais recentes (todos, se ``n`` for ``None`` ou 0)."""
    return list(draws[-n:]) if n else list(draws)


def frequency(spec: GameSpec, draws: Sequence[Draw]) -> dict[int, int]:
    """Quantas vezes cada dezena saiu (inclui as que nunca saíram, com 0)."""
    counts = Counter(n for d in draws for s in d.number_sets() for n in s)
    return {n: counts.get(n, 0) for n in spec.numbers}


def delays(spec: GameSpec, draws: Sequence[Draw]) -> dict[int, int]:
    """Atraso: concursos desde a última aparição (0 = saiu no último concurso)."""
    result = {n: len(draws) for n in spec.numbers}
    pending = set(spec.numbers)
    for age, draw in enumerate(reversed(draws)):
        for numbers in draw.number_sets():
            for n in pending.intersection(numbers):
                result[n] = age
            pending.difference_update(numbers)
        if not pending:
            break
    return result


def top_pairs(draws: Sequence[Draw], k: int = 10) -> list[tuple[tuple[int, int], int]]:
    """Os ``k`` pares de dezenas que mais saíram juntos."""
    counter: Counter[tuple[int, int]] = Counter()
    for draw in draws:
        for numbers in draw.number_sets():
            counter.update(combinations(numbers, 2))
    return counter.most_common(k)


def parity_distribution(draws: Sequence[Draw]) -> Counter[int]:
    """Distribuição da quantidade de dezenas ímpares por sorteio."""
    return Counter(sum(n % 2 for n in s) for d in draws for s in d.number_sets())


def sums(draws: Sequence[Draw]) -> list[int]:
    """Soma das dezenas de cada sorteio."""
    return [sum(s) for d in draws for s in d.number_sets()]


def repeats_from_previous(draws: Sequence[Draw]) -> Counter[int]:
    """Quantas dezenas se repetiram em relação ao concurso anterior."""
    pairs = zip(draws, draws[1:], strict=False)
    return Counter(len(set(a.numbers) & set(b.numbers)) for a, b in pairs)


def trevo_frequency(spec: GameSpec, draws: Sequence[Draw]) -> dict[int, int]:
    """Frequência de cada trevo (+Milionária)."""
    counts = Counter(t for d in draws for t in d.trevos)
    return {t: counts.get(t, 0) for t in range(1, spec.trevo_max + 1)}


def extra_frequency(draws: Sequence[Draw], k: int = 12) -> list[tuple[str, int]]:
    """Mês da Sorte / Time do Coração mais sorteados."""
    return Counter(d.extra for d in draws if d.extra).most_common(k)


def percentile(values: Sequence[float], q: float) -> float:
    """Percentil ``q`` (0–100) com interpolação linear."""
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q / 100
    low, high = math.floor(pos), math.ceil(pos)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def _upper_incomplete_gamma_q(a: float, x: float) -> float:
    """Função gama incompleta superior regularizada Q(a, x) (Numerical Recipes)."""
    if x <= 0:
        return 1.0
    log_prefix = -x + a * math.log(x) - math.lgamma(a)
    if x < a + 1:  # série
        term = total = 1.0 / a
        ap = a
        for _ in range(500):
            ap += 1
            term *= x / ap
            total += term
            if abs(term) < abs(total) * 1e-12:
                break
        return max(0.0, 1.0 - total * math.exp(log_prefix))
    b, c, d = x + 1 - a, 1e300, 1 / (x + 1 - a)  # fração contínua de Lentz
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-12:
            break
    return min(1.0, math.exp(log_prefix) * h)


@dataclass(frozen=True)
class ChiSquare:
    """Resultado do teste qui-quadrado de uniformidade."""

    statistic: float
    dof: int
    p_value: float

    def verdict(self) -> str:
        """Interpretação em português."""
        if self.p_value >= 0.05:
            return ("compatível com sorteio uniforme: as diferenças de frequência "
                    "são do tamanho esperado pelo acaso")
        return ("diferença estatisticamente significativa (p < 0,05); ainda assim, "
                "isso não permite prever o próximo sorteio")


def chi_square(freq: dict[int, int]) -> ChiSquare:
    """Testa se as frequências observadas são compatíveis com dezenas equiprováveis."""
    total = sum(freq.values())
    if total == 0 or len(freq) < 2:
        return ChiSquare(0.0, max(len(freq) - 1, 1), 1.0)
    expected = total / len(freq)
    stat = sum((obs - expected) ** 2 / expected for obs in freq.values())
    dof = len(freq) - 1
    return ChiSquare(stat, dof, _upper_incomplete_gamma_q(dof / 2, stat / 2))


@dataclass
class StatsSummary:
    """Pacote de estatísticas pronto para a interface."""

    contests: int
    freq: dict[int, int]
    expected: float
    delay: dict[int, int]
    hot: list[int]
    cold: list[int]
    overdue: list[int]
    chi: ChiSquare
    parity: Counter[int]
    sum_mean: float
    sum_band: tuple[float, float]
    pairs: list[tuple[tuple[int, int], int]]
    repeats: Counter[int]
    sum_values: list[int] = field(default_factory=list)
    trevos: dict[int, int] = field(default_factory=dict)
    extras: list[tuple[str, int]] = field(default_factory=list)


def summarize(spec: GameSpec, draws: Sequence[Draw], top: int = 10) -> StatsSummary:
    """Calcula todas as estatísticas de uma vez."""
    freq = frequency(spec, draws)
    delay = delays(spec, draws)
    by_freq = sorted(freq, key=lambda n: (-freq[n], n))
    total_sets = sum(1 for d in draws for _ in d.number_sets())
    sum_list = sums(draws)
    return StatsSummary(
        contests=len(draws),
        freq=freq,
        expected=total_sets * spec.draw_size / spec.pool_size,
        delay=delay,
        hot=by_freq[:top],
        cold=by_freq[::-1][:top],
        overdue=sorted(delay, key=lambda n: (-delay[n], n))[:top],
        chi=chi_square(freq),
        parity=parity_distribution(draws),
        sum_mean=sum(sum_list) / len(sum_list) if sum_list else 0.0,
        sum_band=(percentile(sum_list, 10), percentile(sum_list, 90)),
        pairs=top_pairs(draws, top),
        repeats=repeats_from_previous(draws),
        sum_values=sum_list,
        trevos=trevo_frequency(spec, draws) if spec.has_trevos else {},
        extras=extra_frequency(draws) if spec.extra_name else [],
    )
