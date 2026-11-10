"""Regras das loterias, custos e utilitários de modelos/formatação."""

import pytest

from loterias.formatting import brl, brl_compact, thousands
from loterias.games import GAMES, apply_price_overrides, get_game
from loterias.models import Bet, parse_numbers


@pytest.mark.parametrize("slug,n,trevos,expected", [
    ("megasena", 6, 2, 6.00), ("megasena", 7, 2, 42.00), ("megasena", 8, 2, 168.00),
    ("lotofacil", 15, 2, 3.50), ("lotofacil", 16, 2, 56.00),
    ("quina", 6, 2, 18.00), ("lotomania", 50, 2, 3.00), ("timemania", 10, 2, 3.50),
    ("diadesorte", 8, 2, 20.00), ("maismilionaria", 6, 2, 6.00),
    ("maismilionaria", 7, 3, 126.00), ("duplasena", 7, 2, 21.00),
])
def test_bet_cost(slug: str, n: int, trevos: int, expected: float) -> None:
    """O custo segue C(n, mínimo) × preço (× C(trevos, 2) na +Milionária)."""
    assert get_game(slug).bet_cost(n, trevos) == pytest.approx(expected)


def test_bet_cost_out_of_range() -> None:
    """Tamanhos fora do volante são recusados."""
    with pytest.raises(ValueError):
        get_game("megasena").bet_cost(21)
    with pytest.raises(ValueError):
        get_game("maismilionaria").bet_cost(6, 1)


def test_validate_numbers_messages() -> None:
    """Validação devolve mensagens amigáveis."""
    mega = get_game("megasena")
    assert mega.validate_numbers([6, 5, 4, 3, 2, 1]) == (1, 2, 3, 4, 5, 6)
    with pytest.raises(ValueError, match="repetidas"):
        mega.validate_numbers([1, 1, 2, 3, 4, 5])
    with pytest.raises(ValueError, match="fora da faixa"):
        mega.validate_numbers([0, 2, 3, 4, 5, 61])
    with pytest.raises(ValueError, match="marque de 6 a 20"):
        mega.validate_numbers([1, 2, 3])
    with pytest.raises(ValueError, match="exatamente 50"):
        get_game("lotomania").validate_numbers(range(10))


def test_lotomania_includes_zero() -> None:
    """Lotomania vai de 00 a 99."""
    spec = get_game("lotomania")
    assert spec.numbers[0] == 0 and spec.numbers[-1] == 99 and spec.pool_size == 100


def test_get_game_aliases() -> None:
    """Aceita variações de escrita."""
    assert get_game("Mega-Sena").slug == "megasena"
    assert get_game("+Milionária".replace("á", "a")).slug == "maismilionaria"
    with pytest.raises(KeyError):
        get_game("loteca")


def test_price_override() -> None:
    """Preço configurável pelo usuário substitui o padrão."""
    original = GAMES["quina"].price
    try:
        apply_price_overrides({"quina": 4.0, "inexistente": 1.0, "megasena": -1})
        assert GAMES["quina"].price == 4.0
        assert GAMES["megasena"].price == 6.0
    finally:
        apply_price_overrides({"quina": original})


def test_parse_numbers_and_bet_text() -> None:
    """Entrada livre de dezenas e representação textual."""
    assert parse_numbers("5, 12 23-34;45/56") == [5, 12, 23, 34, 45, 56]
    with pytest.raises(ValueError):
        parse_numbers("1 2 x")
    assert Bet((1, 2), (3, 5), "Maio").as_text() == "01 02 | trevos 3 5 | Maio"


def test_formatting() -> None:
    """Formatos brasileiros."""
    assert brl(1234.5) == "R$ 1.234,50"
    assert brl(None) == "—"
    assert brl_compact(185_000_000) == "R$ 185 mi"
    assert brl_compact(3_500_000) == "R$ 3,5 mi"
    assert thousands(3071) == "3.071"
