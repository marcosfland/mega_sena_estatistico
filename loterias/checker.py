"""Conferência de apostas contra um resultado.

Uma aposta com mais dezenas que o mínimo equivale a várias apostas simples
(ex.: 7 dezenas na Mega-Sena = 7 jogos de 6). Se ela acertar ``h`` dezenas, o
número de apostas simples com exatamente ``j`` acertos é
``C(h, j) · C(n − h, k − j)``, e é assim que os prêmios são contados aqui.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import comb
from typing import Optional

from loterias.games import GameSpec, PrizeRule
from loterias.models import Bet, Draw


@dataclass(frozen=True)
class TierWin:
    """Prêmios obtidos numa faixa."""

    rule: PrizeRule
    count: int
    faixa: int
    amount_each: Optional[float]
    draw_index: int = 1
    double_draw: bool = False

    @property
    def total(self) -> Optional[float]:
        """Valor total da faixa (``None`` se a Caixa não divulgou o rateio)."""
        return None if self.amount_each is None else self.amount_each * self.count

    def label(self) -> str:
        """Ex.: ``"2× Quadra (1º sorteio)"``."""
        suffix = f" ({self.draw_index}º sorteio)" if self.double_draw else ""
        return f"{self.count}× {self.rule.name}{suffix}"


@dataclass
class CheckResult:
    """Resultado da conferência de uma aposta."""

    bet: Bet
    contest: int
    hits: list[int]
    matched: list[tuple[int, ...]]
    trevo_hits: int = 0
    extra_hit: bool = False
    wins: list[TierWin] = field(default_factory=list)

    @property
    def won(self) -> bool:
        """Se ganhou algum prêmio."""
        return bool(self.wins)

    @property
    def total_prize(self) -> float:
        """Soma dos prêmios com valor conhecido."""
        return sum(w.total or 0.0 for w in self.wins)

    @property
    def prize_pending(self) -> bool:
        """Há faixa ganha cujo valor ainda não foi divulgado."""
        return any(w.amount_each is None for w in self.wins)

    def summary(self) -> str:
        """Frase curta para a interface."""
        hits = " / ".join(str(h) for h in self.hits)
        text = f"{hits} acerto(s)"
        if self.trevo_hits:
            text += f" + {self.trevo_hits} trevo(s)"
        if not self.wins:
            return text + " — sem prêmio"
        return text + " — " + ", ".join(w.label() for w in self.wins)


def _subbet_count(spec: GameSpec, n: int, h: int, j: int) -> int:
    """Apostas simples com exatamente ``j`` acertos dentro de uma aposta de ``n`` dezenas."""
    if spec.bet_min != spec.draw_size:  # Lotomania / Timemania: aposta única
        return 1 if h == j else 0
    k = spec.draw_size
    if j > h or k - j > n - h or j > k:
        return 0
    return comb(h, j) * comb(n - h, k - j)


def _column_counts(spec: GameSpec, bet: tuple[int, ...], drawn: tuple[int, ...]) -> list[int]:
    """Super Sete: apostas simples com exatamente ``j`` colunas certas (índice = ``j``).

    Cada coluna com ``n`` marcações, das quais ``a`` (0 ou 1) é o dígito sorteado,
    contribui com o fator ``(n − a) + a·x``; o coeficiente de ``x^j`` do produto
    é a quantidade de combinações com ``j`` acertos.
    """
    poly = [1]
    hit_codes = set(drawn)
    for digits_codes in _codes_by_column(spec, bet):
        a = sum(1 for code in digits_codes if code in hit_codes)
        b = len(digits_codes) - a
        nxt = [0] * (len(poly) + 1)
        for power, coef in enumerate(poly):
            nxt[power] += coef * b
            nxt[power + 1] += coef * a
        poly = nxt
    return poly


def _codes_by_column(spec: GameSpec, bet: tuple[int, ...]) -> list[list[int]]:
    """Códigos da aposta agrupados por coluna."""
    groups: list[list[int]] = [[] for _ in range(spec.columns)]
    for code in bet:
        groups[code // 10].append(code)
    return groups


def _trevo_count(spec: GameSpec, n_trevos: int, th: int, t: int) -> int:
    """Combinações de 2 trevos com exatamente ``t`` acertos."""
    k = spec.trevo_draw
    if t > th or k - t > n_trevos - th:
        return 0
    return comb(th, t) * comb(n_trevos - th, k - t)


def check_bet(spec: GameSpec, bet: Bet, draw: Draw) -> CheckResult:
    """Confere uma aposta contra um concurso.

    Args:
        spec: Regras da loteria.
        bet: Aposta a conferir.
        draw: Resultado oficial.

    Returns:
        Acertos e prêmios por faixa (com valores, quando o rateio já saiu).
    """
    picked = set(bet.numbers)
    result = CheckResult(bet=bet, contest=draw.contest, hits=[], matched=[])
    result.trevo_hits = len(set(bet.trevos) & set(draw.trevos))
    for index, numbers in enumerate(draw.number_sets(), start=1):
        matched = tuple(sorted(picked.intersection(numbers)))
        h = len(matched)
        result.hits.append(h)
        result.matched.append(matched)
        offset = (index - 1) * len(spec.prizes)
        by_hits = _column_counts(spec, bet.numbers, numbers) if spec.is_columns else None
        for rule in spec.prizes:
            if by_hits is not None:
                count = by_hits[rule.hits] if rule.hits < len(by_hits) else 0
            else:
                count = _subbet_count(spec, len(bet.numbers), h, rule.hits)
            if rule.trevos is not None:
                count *= sum(_trevo_count(spec, len(bet.trevos), result.trevo_hits, t)
                             for t in rule.trevos)
            if count:
                faixa = rule.faixa + offset
                result.wins.append(TierWin(rule, count, faixa, draw.prize_amount(faixa),
                                           index, spec.double_draw))
    if spec.extra_faixa and bet.extra and draw.extra \
            and bet.extra.casefold() == draw.extra.casefold():
        result.extra_hit = True
        rule = PrizeRule(spec.extra_faixa, 0, spec.extra_name or "Extra")
        result.wins.append(TierWin(rule, 1, spec.extra_faixa,
                                   draw.prize_amount(spec.extra_faixa)))
    return result


def best_hits(spec: GameSpec, bet_numbers: tuple[int, ...], draw: Draw) -> int:
    """Maior número de acertos entre os sorteios do concurso (atalho para o backtest)."""
    picked = set(bet_numbers)
    return max(len(picked.intersection(s)) for s in draw.number_sets())
