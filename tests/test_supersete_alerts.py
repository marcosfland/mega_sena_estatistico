"""Super Sete (loteria por colunas), avisos de prêmio e notificações do sistema."""

from __future__ import annotations

import datetime as dt
import random
import subprocess
from typing import Any

import pytest
from conftest import make_draws

from loterias import bolao as bl
from loterias import columns, notifier
from loterias.alerts import check_new_results, find_alerts
from loterias.checker import check_bet
from loterias.export import export_draws_csv
from loterias.games import get_game
from loterias.generator import StrategyContext, generate_games, strategies_for
from loterias.models import Bet, Draw, PrizeTier
from loterias.parsers import ParseError, parse_community, parse_official
from loterias.storage import Storage
from loterias.updater import SyncResult

SUPER = get_game("supersete")
# Resposta real da API comunitária (concurso 920, 09/11/2026): dígitos repetidos são válidos.
COMMUNITY_SUPER = {"concurso": 920, "data": "09/11/2026",
                   "dezenas": ["5", "8", "1", "3", "8", "2", "0"],
                   "dezenasOrdemSorteio": ["5", "8", "1", "3", "8", "2", "0"],
                   "premiacoes": [{"descricao": "6 acertos", "faixa": 2, "ganhadores": 2,
                                   "valorPremio": 9030.02}]}


def _draw(text: str, prizes: tuple[PrizeTier, ...] = ()) -> Draw:
    """Sorteio da Super Sete a partir dos 7 dígitos."""
    return Draw("supersete", 920, dt.date(2026, 11, 9), tuple(SUPER.parse_input(text)),
                prizes=prizes)


# ---------------------------------------------------------------------- Super Sete
def test_parse_super_sete_keeps_column_order() -> None:
    """Dígitos viram códigos coluna*10+dígito, inclusive repetidos."""
    draw = parse_community(SUPER, COMMUNITY_SUPER)
    assert draw.numbers == (5, 18, 21, 33, 48, 52, 60)
    assert columns.digits_of(draw.numbers) == [5, 8, 1, 3, 8, 2, 0]
    official = parse_official(SUPER, {"numero": 920, "dataApuracao": "09/11/2026",
                                      "listaDezenas": ["5", "8", "1", "3", "8", "2", "0"]})
    assert official.numbers == draw.numbers
    with pytest.raises(ParseError):
        parse_community(SUPER, {**COMMUNITY_SUPER, "dezenas": ["1"] * 6,
                                "dezenasOrdemSorteio": []})


@pytest.mark.parametrize("text,cost", [("5 8 1 3 8 2 0", 3.0), ("5/6 8 1 3 8 2 0", 6.0),
                                       ("5/6/7 8/9 1 3 8 2 0", 18.0)])
def test_super_sete_cost_and_format(text: str, cost: float) -> None:
    """Custo = preço × produto das marcações por coluna; texto por coluna."""
    numbers = SUPER.validate_numbers(SUPER.parse_input(text))
    assert SUPER.cost_of(numbers) == cost
    assert SUPER.format_bet(numbers).replace(" | ", " ") == text
    assert SUPER.bet_cost(21) == 3.0 * 3 ** 7


@pytest.mark.parametrize("text", ["5 8 1 3 8 2", "5 8 1 3 8 2 x", "5/6/7/8 8 1 3 8 2 0",
                                  "5 8 1 3 8 2 10"])
def test_super_sete_invalid_input(text: str) -> None:
    """Colunas faltando, dígito inválido ou mais de 3 por coluna."""
    with pytest.raises(ValueError):
        SUPER.validate_numbers(SUPER.parse_input(text))


def test_super_sete_prize_combinatorics() -> None:
    """Coeficientes do produto por coluna: 2 colunas duplas = 1×7, 2×6 e 1×5."""
    draw = _draw("5 8 1 3 8 2 0", (PrizeTier(1, "7", 0, 0.0), PrizeTier(2, "6", 2, 9030.02)))
    res = check_bet(SUPER, Bet(tuple(SUPER.parse_input("5/6 8/9 1 3 8 2 0"))), draw)
    assert {w.rule.name: w.count for w in res.wins} == {"7 colunas": 1, "6 colunas": 2,
                                                         "5 colunas": 1}
    assert res.total_prize == pytest.approx(2 * 9030.02)
    miss = check_bet(SUPER, Bet(tuple(SUPER.parse_input("5 8 0 0 0 0 1"))), draw)
    assert miss.hits == [2] and not miss.won


def test_super_sete_generator_one_to_three_per_column() -> None:
    """Jogos gerados respeitam as colunas; estratégias de soma/datas não se aplicam."""
    ctx = StrategyContext.from_draws(SUPER, make_draws(SUPER, 120))
    keys = {s.key for s in strategies_for(SUPER)}
    assert "equilibrado" not in keys and "menos_populares" not in keys
    for n in (7, 10, 21):
        for strategy in keys:
            for bet in generate_games(SUPER, ctx, strategy, n, 5, random.Random(2)):
                assert SUPER.validate_numbers(bet.numbers) == bet.numbers
                assert len(bet.numbers) == n
    with pytest.raises(ValueError, match="não se aplica"):
        generate_games(SUPER, ctx, "equilibrado", 7)


def test_super_sete_bolao_and_export(tmp_path: Any) -> None:
    """Bolão usa o custo exato; CSV mostra os dígitos por coluna."""
    ctx = StrategyContext.from_draws(SUPER, make_draws(SUPER, 50))
    bolao = bl.create_bolao(SUPER, ctx, "Super", 30.0, 8, bl.parse_participants("Ana"),
                            "aleatorio", random.Random(1))
    assert len(bolao.bets) == 5 and bolao.total_cost(SUPER) == 30.0
    assert " | " in bl.share_text(SUPER, bolao)
    path = export_draws_csv(SUPER, [_draw("5 8 1 3 8 2 0")], tmp_path / "s.csv")
    assert "920;09/11/2026;5;8;1;3;8;2;0" in path.read_text("utf-8-sig")


# ------------------------------------------------------------------------- avisos
def test_alerts_once_per_contest(storage: Storage) -> None:
    """Jogo salvo e bolão premiados geram aviso uma única vez por concurso."""
    mega = get_game("megasena")
    draws = make_draws(mega, 3)
    latest = draws[-1]
    storage.upsert_draws(draws)
    storage.save_bet("megasena", Bet(latest.numbers), "Sorte grande", latest.contest)
    storage.save_bet("megasena", Bet(latest.numbers), "Outro concurso", latest.contest + 5)
    bolao = bl.Bolao("Firma", "megasena", [Bet(latest.numbers)], [bl.Participant("Ana")], 6,
                     target_contest=latest.contest)
    storage.save_bolao("megasena", "Firma", bolao.to_dict())
    alerts = find_alerts(storage, latest)
    assert [a.kind for a in alerts] == ["jogo", "bolão"]
    assert "Sena" in alerts[0].message() and "premiado" in alerts[0].title()
    result = SyncResult("megasena", added=1, latest_contest=latest.contest)
    assert len(check_new_results(storage, [result])) == 2
    assert check_new_results(storage, [result]) == []  # já avisado
    assert check_new_results(storage, [SyncResult("quina", error="x")]) == []


# -------------------------------------------------------------------- notificação
def test_notifier_builds_safe_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    """Título/mensagem vão por variável de ambiente ou argumento, nunca no script."""
    calls: list[tuple[list[str], dict[str, str]]] = []

    def fake_run(cmd: list[str], env: dict[str, str], **_kw: Any) -> Any:
        calls.append((cmd, env))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(notifier.subprocess, "run", fake_run)
    monkeypatch.setattr(notifier.platform, "system", lambda: "Windows")
    assert notifier.notify("Título'; rm -rf /", "msg")
    cmd, env = calls[-1]
    assert cmd[0] == "powershell" and "rm -rf" not in " ".join(cmd)
    assert env["LOTERIAS_TITLE"] == "Título'; rm -rf /"
    monkeypatch.setattr(notifier.platform, "system", lambda: "Darwin")
    assert notifier.notify("T", "M") and calls[-1][0][-2:] == ["T", "M"]
    monkeypatch.setattr(notifier.platform, "system", lambda: "Linux")
    monkeypatch.setattr(notifier.shutil, "which", lambda _name: None)
    assert notifier.notify("T", "M") is False


def test_notifier_handles_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Erro ao executar ou código de saída ≠ 0 devolve False, sem exceção."""
    monkeypatch.setattr(notifier.platform, "system", lambda: "Darwin")

    def boom(*_a: Any, **_k: Any) -> Any:
        raise OSError("sem osascript")

    monkeypatch.setattr(notifier.subprocess, "run", boom)
    assert notifier.notify("T", "M") is False
    monkeypatch.setattr(notifier.subprocess, "run",
                        lambda cmd, **_k: subprocess.CompletedProcess(cmd, 1, "", "erro"))
    assert notifier.notify("T", "M") is False
