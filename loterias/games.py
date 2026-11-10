"""Catálogo das loterias suportadas e suas regras.

Cada loteria é descrita por um :class:`GameSpec` imutável com faixa de números,
quantidade sorteada, limites de aposta, preço da aposta simples e faixas de
premiação. Todo o restante do projeto (gerador, conferência, bolão, API) lê as
regras daqui, então adicionar uma loteria nova é só registrar um ``GameSpec``.

Os preços são os vigentes em out/2026 (último reajuste da Caixa: 09/07/2025) e
podem ser sobrescritos em ``data/settings.json`` (chave ``"precos"``).
"""

from __future__ import annotations

import dataclasses
import logging

from loterias.game_spec import GameSpec, PrizeRule

__all__ = ["GAMES", "DEFAULT_GAME", "MONTHS", "GameSpec", "PrizeRule", "get_game",
           "apply_price_overrides"]


def _simple(faixas: list[tuple[int, str]]) -> tuple[PrizeRule, ...]:
    """Cria faixas sequenciais (faixa 1, 2, ...) a partir de (acertos, nome)."""
    return tuple(PrizeRule(i + 1, hits, name) for i, (hits, name) in enumerate(faixas))


MONTHS = (
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
)

GAMES: dict[str, GameSpec] = {
    spec.slug: spec
    for spec in (
        GameSpec(
            "megasena", "Mega-Sena", "#209869", 1, 60, 6, 6, 20, 6.00,
            _simple([(6, "Sena"), (5, "Quina"), (4, "Quadra")]),
        ),
        GameSpec(
            "lotofacil", "Lotofácil", "#930089", 1, 25, 15, 15, 20, 3.50,
            _simple([(15, "15 acertos"), (14, "14 acertos"), (13, "13 acertos"),
                     (12, "12 acertos"), (11, "11 acertos")]),
        ),
        GameSpec(
            "quina", "Quina", "#260085", 1, 80, 5, 5, 15, 3.00,
            _simple([(5, "Quina"), (4, "Quadra"), (3, "Terno"), (2, "Duque")]),
        ),
        GameSpec(
            "lotomania", "Lotomania", "#F78100", 0, 99, 20, 50, 50, 3.00,
            _simple([(20, "20 acertos"), (19, "19 acertos"), (18, "18 acertos"),
                     (17, "17 acertos"), (16, "16 acertos"), (15, "15 acertos"),
                     (0, "0 acertos")]),
        ),
        GameSpec(
            "duplasena", "Dupla Sena", "#A61324", 1, 50, 6, 6, 15, 3.00,
            _simple([(6, "Sena"), (5, "Quina"), (4, "Quadra"), (3, "Terno")]),
            double_draw=True,
        ),
        GameSpec(
            "timemania", "Timemania", "#00A65E", 1, 80, 7, 10, 10, 3.50,
            _simple([(7, "7 acertos"), (6, "6 acertos"), (5, "5 acertos"),
                     (4, "4 acertos"), (3, "3 acertos")]),
            extra_name="Time do Coração", extra_faixa=6,
        ),
        GameSpec(
            "diadesorte", "Dia de Sorte", "#CB8E37", 1, 31, 7, 7, 15, 2.50,
            _simple([(7, "7 acertos"), (6, "6 acertos"), (5, "5 acertos"),
                     (4, "4 acertos")]),
            extra_name="Mês da Sorte", extra_faixa=5, extra_options=MONTHS,
        ),
        GameSpec(
            "maismilionaria", "+Milionária", "#2E3192", 1, 50, 6, 6, 12, 6.00,
            (
                PrizeRule(1, 6, "6 + 2 trevos", (2,)),
                PrizeRule(2, 6, "6 + 0/1 trevo", (0, 1)),
                PrizeRule(3, 5, "5 + 2 trevos", (2,)),
                PrizeRule(4, 5, "5 + 0/1 trevo", (0, 1)),
                PrizeRule(5, 4, "4 + 2 trevos", (2,)),
                PrizeRule(6, 4, "4 + 0/1 trevo", (0, 1)),
                PrizeRule(7, 3, "3 + 2 trevos", (2,)),
                PrizeRule(8, 3, "3 + 1 trevo", (1,)),
                PrizeRule(9, 2, "2 + 2 trevos", (2,)),
                PrizeRule(10, 2, "2 + 1 trevo", (1,)),
            ),
            trevo_max=6, trevo_draw=2, trevo_bet_max=6,
        ),
        GameSpec(
            "supersete", "Super Sete", "#6E9A1E", 0, 69, 7, 7, 21, 3.00,
            _simple([(7, "7 colunas"), (6, "6 colunas"), (5, "5 colunas"),
                     (4, "4 colunas"), (3, "3 colunas")]),
            columns=7,
        ),
    )
}

DEFAULT_GAME = "megasena"


def get_game(slug: str) -> GameSpec:
    """Retorna as regras de uma loteria.

    Args:
        slug: Identificador (ex.: ``"lotofacil"``). Aceita maiúsculas e hífens.

    Raises:
        KeyError: Se a loteria não existir, com a lista das válidas.
    """
    key = slug.lower().replace("-", "").replace("+", "mais").replace(" ", "")
    if key not in GAMES:
        raise KeyError(f"Loteria '{slug}' desconhecida. Opções: {', '.join(GAMES)}")
    return GAMES[key]


def apply_price_overrides(prices: dict[str, float]) -> None:
    """Atualiza preços a partir das configurações do usuário.

    Args:
        prices: Mapa ``slug -> preço``. Entradas inválidas são ignoradas com log.
    """
    for slug, value in prices.items():
        try:
            spec = get_game(slug)
            price = float(value)
            if price <= 0:
                raise ValueError("preço deve ser positivo")
        except (KeyError, TypeError, ValueError) as exc:
            logging.getLogger(__name__).warning("Preço ignorado para %s: %s", slug, exc)
            continue
        GAMES[spec.slug] = dataclasses.replace(spec, price=price)
