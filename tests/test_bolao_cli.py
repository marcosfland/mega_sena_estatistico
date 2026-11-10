"""Bolão, CLI e serviços."""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from conftest import FakeSource, make_draws

from loterias import bolao as bl
from loterias.cli import main as cli_main
from loterias.export import export_bets_csv, export_draws_csv
from loterias.games import GameSpec, get_game
from loterias.generator import StrategyContext
from loterias.models import Draw, PrizeTier
from loterias.services import Services, build_services


def test_plan_budget(mega: GameSpec) -> None:
    """Quantos jogos cabem e quanto sobra."""
    plan = bl.plan_budget(mega, 100.0, 6)
    assert (plan.n_bets, plan.total, plan.leftover) == (16, 96.0, 4.0)
    assert bl.plan_budget(mega, 42.0, 7).n_bets == 1
    with pytest.raises(ValueError, match="insuficiente"):
        bl.plan_budget(mega, 41.99, 7)


def test_parse_participants() -> None:
    """Formatos aceitos e erros claros."""
    people = bl.parse_participants("Ana, 2\nBruno\n\nCarla Souza; 3 cotas\nDavi\t4")
    assert [(p.name, p.cotas) for p in people] == [("Ana", 2), ("Bruno", 1),
                                                   ("Carla Souza", 3), ("Davi", 4)]
    for bad in ("", "Ana\nana", "Ana, 0", "Ana, 101"):
        with pytest.raises(ValueError):
            bl.parse_participants(bad)


def test_create_check_and_share(mega: GameSpec, mega_draws: list[Draw]) -> None:
    """Fluxo completo: montar, ratear e conferir."""
    ctx = StrategyContext.from_draws(mega, mega_draws)
    people = bl.parse_participants("Ana, 2\nBruno\nCarla")
    bolao = bl.create_bolao(mega, ctx, "Firma", 100.0, 6, people, "equilibrado",
                            random.Random(1), target_contest=401)
    assert len(bolao.bets) == 16 and bolao.total_cost(mega) == 96.0
    assert bolao.cota_value(mega) == 24.0 and bolao.amount_due(mega, people[0]) == 48.0
    winning = bolao.bets[0].numbers
    draw = make_draws(mega, 1, start=401)[0]
    draw = draw.__class__(**{**draw.__dict__, "numbers": winning,
                             "prizes": (PrizeTier(1, "6", 1, 1000.0),)})
    check = bl.check_bolao(mega, bolao, draw)
    assert check.total_prize >= 1000.0
    assert check.shares["Ana"] == pytest.approx(check.total_prize / 2, abs=0.01)
    assert sum(check.shares.values()) <= check.total_prize
    text = bl.share_text(mega, bolao)
    assert "Bolão Firma" in text and "concurso 401" in text and text.count("\n01)") == 1
    assert "Prêmio total" in bl.result_text(mega, bolao, check)
    restored = bl.Bolao.from_dict(bolao.to_dict(), 5)
    assert restored.bets == bolao.bets and restored.id == 5


def test_create_bolao_validation(mega: GameSpec, mega_draws: list[Draw]) -> None:
    """Nome e estratégia obrigatórios."""
    ctx = StrategyContext.from_draws(mega, mega_draws)
    people = bl.parse_participants("Ana")
    with pytest.raises(ValueError):
        bl.create_bolao(mega, ctx, " ", 100.0, 6, people)
    with pytest.raises(ValueError):
        bl.create_bolao(mega, ctx, "X", 100.0, 6, people, "magia")


def test_exports(tmp_path: Path) -> None:
    """CSV de sorteios e de jogos."""
    spec = get_game("maismilionaria")
    draws = make_draws(spec, 3)
    content = export_draws_csv(spec, draws, tmp_path / "s.csv").read_text("utf-8-sig")
    assert content.splitlines()[0].startswith("Concurso;Data;D1") and "Trevo 1" in content
    payload = {"name": "x", "game": spec.slug, "n_numbers": 6, "participants": [],
               "bets": [{"numbers": [1, 2, 3, 4, 5, 6], "trevos": [1, 2]}]}
    bets = bl.Bolao.from_dict(payload).bets
    assert "R$ 6,00" in export_bets_csv(spec, bets, tmp_path / "j.csv").read_text("utf-8-sig")


@pytest.fixture
def services(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Services:
    """Serviços isolados com API falsa e Mega-Sena/+Milionária pré-carregadas."""
    monkeypatch.setenv("LOTERIAS_DATA_DIR", str(tmp_path))
    source = FakeSource({"megasena": make_draws(get_game("megasena"), 120),
                         "maismilionaria": make_draws(get_game("maismilionaria"), 80)})
    svc = build_services(tmp_path / "cli.db", source=source, migrate=False)
    svc.updater.request_delay = 0
    return svc


def test_cli_commands(services: Services, capsys: pytest.CaptureFixture[str]) -> None:
    """Principais subcomandos funcionam de ponta a ponta."""
    assert cli_main(["atualizar", "-j", "megasena"], services) == 0
    assert "120 concurso(s) novo(s)" in capsys.readouterr().out
    assert cli_main(["gerar", "-q", "2", "-n", "7"], services) == 0
    assert "R$ 84,00" in capsys.readouterr().out
    assert cli_main(["estatisticas", "--ultimos", "50"], services) == 0
    assert "50 concursos" in capsys.readouterr().out
    draw = services.storage.latest_draw("megasena")
    numbers = " ".join(map(str, draw.numbers))
    assert cli_main(["conferir", numbers], services) == 0
    assert "Sena" in capsys.readouterr().out
    assert cli_main(["bolao", "--orcamento", "60", "-p", "Ana:2,Bruno", "--salvar"],
                    services) == 0
    assert "Bolão salvo" in capsys.readouterr().out
    assert cli_main(["backtest", "--concursos", "50", "--semente", "1"], services) == 0
    assert cli_main(["jogos"], services) == 0
    assert "base vazia" in capsys.readouterr().out


def test_cli_errors(services: Services, capsys: pytest.CaptureFixture[str]) -> None:
    """Erros de entrada retornam código 2 com mensagem; base vazia orienta o usuário."""
    services.updater.sync_game("maismilionaria")
    assert cli_main(["conferir", "-j", "maismilionaria", "1 2 3 4 5 6"], services) == 2
    assert "trevos" in capsys.readouterr().err
    with pytest.raises(SystemExit, match="atualizar"):
        cli_main(["gerar", "-j", "quina"], services)
