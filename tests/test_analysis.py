"""Estatísticas, gerador de jogos, conferência e backtest."""

from __future__ import annotations

import math
import random
import threading
from math import comb
from typing import Iterable

import pytest
from conftest import make_draws

from loterias.backtest import expected_hits, run_backtest
from loterias.checker import best_hits, check_bet
from loterias.games import GAMES, MONTHS, GameSpec, get_game
from loterias.generator import (STRATEGIES, StrategyContext, default_max_overlap,
                                generate_games, strategies_for)
from loterias.models import Bet, Draw, PrizeTier
from loterias.stats import _upper_incomplete_gamma_q, chi_square, delays, frequency, summarize


# ------------------------------------------------------------------- estatísticas
def test_frequency_and_delay(mega: GameSpec) -> None:
    """Contagens e atrasos batem com um caso montado à mão."""
    import datetime as dt
    d = dt.date(2024, 1, 1)
    draws = [Draw("megasena", 1, d, (1, 2, 3, 4, 5, 6)),
             Draw("megasena", 2, d, (1, 7, 8, 9, 10, 11))]
    freq = frequency(mega, draws)
    assert freq[1] == 2 and freq[2] == 1 and freq[60] == 0 and len(freq) == 60
    delay = delays(mega, draws)
    assert delay[1] == 0 and delay[2] == 1 and delay[60] == 2


def test_dupla_counts_both_draws() -> None:
    """Na Dupla Sena os dois sorteios entram nas estatísticas."""
    spec = get_game("duplasena")
    draws = make_draws(spec, 5)
    assert sum(frequency(spec, draws).values()) == 5 * 2 * spec.draw_size


@pytest.mark.parametrize("x", [0.5, 2.0, 7.3, 15.0])
def test_gamma_q_closed_form(x: float) -> None:
    """Para 2 graus de liberdade, p = exp(-x/2)."""
    assert _upper_incomplete_gamma_q(1.0, x / 2) == pytest.approx(math.exp(-x / 2), rel=1e-9)


def test_chi_square_known_value() -> None:
    """Valor de referência (scipy.stats.chi2.sf(79.2, 59) ≈ 0.0410)."""
    assert _upper_incomplete_gamma_q(59 / 2, 79.2 / 2) == pytest.approx(0.0410, abs=5e-4)
    assert chi_square({1: 10, 2: 10}).p_value == pytest.approx(1.0)


def test_summarize_all_games() -> None:
    """O resumo funciona para todas as loterias."""
    for spec in GAMES.values():
        s = summarize(spec, make_draws(spec, 60))
        assert s.contests == 60 and len(s.hot) == 10 and 0 <= s.chi.p_value <= 1
        assert bool(s.trevos) == spec.has_trevos and bool(s.extras) == bool(spec.extra_name)


# ------------------------------------------------------------------------ gerador
@pytest.mark.parametrize("slug", list(GAMES))
def test_all_strategies_produce_valid_unique_bets(slug: str) -> None:
    """Toda estratégia gera jogos válidos, distintos e com trevos/mês quando aplicável."""
    spec = get_game(slug)
    ctx = StrategyContext.from_draws(spec, make_draws(spec, 200))
    for strategy in strategies_for(spec):
        n = spec.bet_max if spec.bet_min == spec.bet_max else spec.bet_min + 1
        bets = generate_games(spec, ctx, strategy.key, n, 8, random.Random(3))
        assert len({b.numbers for b in bets}) == 8
        for bet in bets:
            assert spec.validate_numbers(bet.numbers) == bet.numbers
            assert spec.validate_trevos(bet.trevos) == bet.trevos
            assert (bet.extra in MONTHS) if spec.extra_options else bet.extra == ""


def test_most_drawn_first_game_is_top(mega: GameSpec, mega_draws: list[Draw]) -> None:
    """Primeiro jogo de "mais sorteados" é exatamente o top-N histórico."""
    ctx = StrategyContext.from_draws(mega, mega_draws)
    freq = frequency(mega, mega_draws)
    top = tuple(sorted(sorted(freq, key=lambda n: (-freq[n], n))[:6]))
    assert generate_games(mega, ctx, "mais_sorteados", 6, 3)[0].numbers == top


def test_reproducible_and_diverse(mega: GameSpec, mega_draws: list[Draw]) -> None:
    """Mesma semente = mesmos jogos; sobreposição limitada."""
    ctx = StrategyContext.from_draws(mega, mega_draws)
    a = generate_games(mega, ctx, "aleatorio", 6, 20, random.Random(7))
    b = generate_games(mega, ctx, "aleatorio", 6, 20, random.Random(7))
    assert a == b
    limit = default_max_overlap(mega, 6)
    assert all(len(set(x.numbers) & set(y.numbers)) <= limit
               for i, x in enumerate(a) for y in a[i + 1:])


def test_filters(mega: GameSpec, mega_draws: list[Draw]) -> None:
    """Equilibrado respeita as faixas; menos populares evita sequências e datas."""
    ctx = StrategyContext.from_draws(mega, mega_draws)
    for bet in generate_games(mega, ctx, "equilibrado", 6, 30, random.Random(1)):
        assert ctx.sum_band[0] <= sum(bet.numbers) <= ctx.sum_band[1]
    for bet in generate_games(mega, ctx, "menos_populares", 6, 30, random.Random(1)):
        assert sum(n > 31 for n in bet.numbers) >= 3


def test_generator_rejects_bad_input(mega: GameSpec, mega_draws: list[Draw]) -> None:
    """Parâmetros inválidos viram ValueError legível."""
    ctx = StrategyContext.from_draws(mega, mega_draws)
    for kwargs in ({"strategy": "x", "n_numbers": 6}, {"strategy": "aleatorio", "n_numbers": 5},
                   {"strategy": "aleatorio", "n_numbers": 6, "n_games": 0}):
        with pytest.raises(ValueError):
            generate_games(mega, ctx, **kwargs)
    assert "menos_populares" not in {s.key for s in strategies_for(get_game("lotofacil"))}
    assert set(STRATEGIES) >= {"mais_sorteados", "aleatorio"}


# ---------------------------------------------------------------------- conferência
def _draw(slug: str, numbers: Iterable[int], numbers2: Iterable[int] = (),
          trevos: Iterable[int] = (), extra: str = "",
          prizes: Iterable[PrizeTier] = ()) -> Draw:
    """Atalho para montar um resultado."""
    import datetime as dt
    return Draw(slug, 10, dt.date(2026, 1, 1), tuple(numbers), tuple(numbers2), tuple(trevos),
                extra, tuple(prizes))


def test_check_multi_number_bet(mega: GameSpec) -> None:
    """7 dezenas com 6 acertos = 1 Sena + 6 Quinas; com 5 acertos = 2 Quinas + 5 Quadras."""
    prizes = [PrizeTier(1, "6", 1, 1_000_000.0), PrizeTier(2, "5", 10, 50_000.0),
              PrizeTier(3, "4", 100, 1_000.0)]
    draw = _draw("megasena", (1, 2, 3, 4, 5, 6), prizes=prizes)
    res = check_bet(mega, Bet((1, 2, 3, 4, 5, 6, 7)), draw)
    assert {w.rule.name: w.count for w in res.wins} == {"Sena": 1, "Quina": 6}
    assert res.total_prize == pytest.approx(1_300_000.0)
    res = check_bet(mega, Bet((1, 2, 3, 4, 5, 8, 9)), draw)
    assert {w.rule.name: w.count for w in res.wins} == {"Quina": 2, "Quadra": 5}
    assert not check_bet(mega, Bet((1, 2, 3, 40, 50, 60)), draw).won


@pytest.mark.parametrize("n,h", [(16, 15), (18, 13), (20, 11)])
def test_lotofacil_combinatorics(n: int, h: int) -> None:
    """Total de apostas simples premiadas confere com a soma das combinações."""
    spec = get_game("lotofacil")
    draw = _draw("lotofacil", range(1, 16))
    bet = Bet(tuple(range(1, h + 1)) + tuple(range(16, 16 + n - h)))
    res = check_bet(spec, bet, draw)
    expected = sum(comb(h, j) * comb(n - h, 15 - j) for j in range(11, 16))
    assert sum(w.count for w in res.wins) == expected


def test_lotomania_zero_hits_and_dupla_second_draw() -> None:
    """Lotomania premia 0 acertos; Dupla Sena usa a faixa do 2º sorteio."""
    loto = get_game("lotomania")
    res = check_bet(loto, Bet(tuple(range(50, 100))), _draw("lotomania", range(0, 20)))
    assert [w.rule.name for w in res.wins] == ["0 acertos"]
    dupla = get_game("duplasena")
    draw = _draw("duplasena", (1, 2, 3, 4, 5, 6), (10, 11, 12, 13, 14, 15),
                 prizes=[PrizeTier(7, "4 acertos 2º", 3, 120.0)])
    res = check_bet(dupla, Bet((10, 11, 12, 13, 40, 41)), draw)
    assert res.hits == [0, 4] and res.wins[0].faixa == 7 and res.total_prize == 120.0
    assert "2º sorteio" in res.summary()


def test_mais_milionaria_and_dia_de_sorte() -> None:
    """Trevos definem a faixa; Mês da Sorte gera prêmio próprio."""
    mais = get_game("maismilionaria")
    draw = _draw("maismilionaria", (1, 2, 3, 4, 5, 6), trevos=(1, 2))
    res = check_bet(mais, Bet((1, 2, 3, 10, 11, 12), (1, 2)), draw)
    assert [w.rule.name for w in res.wins] == ["3 + 2 trevos"]
    res = check_bet(mais, Bet((1, 2, 10, 11, 12, 13), (3, 4)), draw)
    assert not res.won  # 2 acertos sem trevo não premia
    res = check_bet(mais, Bet((1, 2, 3, 4, 5, 6), (1, 3, 4)), draw)
    assert {w.rule.name: w.count for w in res.wins} == {"6 + 0/1 trevo": 3}
    dia = get_game("diadesorte")
    res = check_bet(dia, Bet((1, 2, 3, 20, 21, 22, 23), extra="Maio"),
                    _draw("diadesorte", (1, 2, 3, 4, 5, 6, 7), extra="Maio"))
    assert res.extra_hit and res.wins[-1].faixa == 5
    assert best_hits(dia, (1, 2, 3), _draw("diadesorte", (1, 2, 3, 4, 5, 6, 7))) == 3


# ------------------------------------------------------------------------- backtest
def test_backtest_runs_and_is_honest(mega: GameSpec, mega_draws: list[Draw]) -> None:
    """Todas as estratégias ficam perto da média teórica do acaso."""
    results = run_backtest(mega, mega_draws, list(STRATEGIES), 300, seed=1)
    assert [r.strategy for r in results] == list(STRATEGIES)
    for r in results:
        assert r.contests == 300 and r.spent == pytest.approx(1800.0)
        assert abs(r.mean_hits - expected_hits(mega, 6)) < 0.2


def test_backtest_validation_and_cancel(mega: GameSpec, mega_draws: list[Draw]) -> None:
    """Erros de parâmetro e cancelamento imediato."""
    with pytest.raises(ValueError, match="insuficiente"):
        run_backtest(mega, mega_draws[:50], ["aleatorio"], 100)
    with pytest.raises(ValueError):
        run_backtest(mega, mega_draws, [], 100)
    cancel = threading.Event()
    cancel.set()
    assert run_backtest(mega, mega_draws, ["aleatorio"], 50, cancel=cancel)[0].contests == 0
