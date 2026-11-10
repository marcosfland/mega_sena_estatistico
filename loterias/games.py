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
from dataclasses import dataclass, field
from math import comb
from typing import Optional


@dataclass(frozen=True)
class PrizeRule:
    """Uma faixa de premiação.

    Attributes:
        faixa: Número da faixa na API da Caixa (1 = prêmio principal).
        hits: Acertos de dezenas necessários.
        name: Nome exibido ao usuário (ex.: "Sena").
        trevos: Acertos de trevos aceitos (só +Milionária); ``None`` = não se aplica.
    """

    faixa: int
    hits: int
    name: str
    trevos: Optional[tuple[int, ...]] = None


@dataclass(frozen=True)
class GameSpec:
    """Regras de uma loteria.

    Attributes:
        slug: Identificador usado nas APIs (ex.: ``"megasena"``).
        name: Nome de exibição.
        color: Cor de destaque (hex) usada na interface.
        min_number: Menor dezena possível.
        max_number: Maior dezena possível.
        draw_size: Dezenas sorteadas por concurso.
        bet_min: Mínimo de dezenas por aposta.
        bet_max: Máximo de dezenas por aposta.
        price: Preço da aposta mínima, em reais.
        prizes: Faixas de premiação.
        double_draw: ``True`` quando há dois sorteios por concurso (Dupla Sena).
        trevo_max: Maior trevo (só +Milionária); 0 quando não existe.
        trevo_draw: Trevos sorteados.
        trevo_bet_max: Máximo de trevos por aposta.
        extra_name: Nome do sorteio extra textual (Mês da Sorte / Time do Coração).
        extra_faixa: Faixa da API que premia o acerto do extra.
    """

    slug: str
    name: str
    color: str
    min_number: int
    max_number: int
    draw_size: int
    bet_min: int
    bet_max: int
    price: float
    prizes: tuple[PrizeRule, ...]
    double_draw: bool = False
    trevo_max: int = 0
    trevo_draw: int = 0
    trevo_bet_max: int = 0
    extra_name: Optional[str] = None
    extra_faixa: Optional[int] = None
    extra_options: tuple[str, ...] = field(default=())

    @property
    def numbers(self) -> range:
        """Todas as dezenas válidas, em ordem."""
        return range(self.min_number, self.max_number + 1)

    @property
    def pool_size(self) -> int:
        """Quantidade de dezenas disponíveis."""
        return self.max_number - self.min_number + 1

    @property
    def has_trevos(self) -> bool:
        """Indica se a loteria usa trevos (+Milionária)."""
        return self.trevo_max > 0

    @property
    def bet_sizes(self) -> list[int]:
        """Tamanhos de aposta permitidos."""
        return list(range(self.bet_min, self.bet_max + 1))

    @property
    def min_prize_hits(self) -> int:
        """Menor quantidade de acertos premiada (ignorando a faixa de 0 acertos)."""
        return min(rule.hits for rule in self.prizes if rule.hits > 0)

    def combinations_in_bet(self, n_numbers: int, n_trevos: int = 2) -> int:
        """Quantas apostas simples estão contidas numa aposta com ``n_numbers`` dezenas.

        Args:
            n_numbers: Dezenas marcadas.
            n_trevos: Trevos marcados (só +Milionária).

        Returns:
            Número de apostas simples equivalentes.
        """
        total = comb(n_numbers, self.bet_min)
        if self.has_trevos:
            total *= comb(n_trevos, self.trevo_draw)
        return total

    def bet_cost(self, n_numbers: int, n_trevos: int = 2) -> float:
        """Custo de uma aposta, em reais.

        Args:
            n_numbers: Dezenas marcadas.
            n_trevos: Trevos marcados (só +Milionária).

        Returns:
            Valor da aposta arredondado em centavos.

        Raises:
            ValueError: Se a quantidade estiver fora dos limites da loteria.
        """
        if not self.bet_min <= n_numbers <= self.bet_max:
            raise ValueError(
                f"{self.name}: aposte entre {self.bet_min} e {self.bet_max} dezenas."
            )
        if self.has_trevos and not self.trevo_draw <= n_trevos <= self.trevo_bet_max:
            raise ValueError(
                f"{self.name}: marque entre {self.trevo_draw} e {self.trevo_bet_max} trevos."
            )
        return round(self.price * self.combinations_in_bet(n_numbers, n_trevos), 2)

    def validate_numbers(self, numbers: tuple[int, ...] | list[int]) -> tuple[int, ...]:
        """Valida e normaliza as dezenas de uma aposta.

        Args:
            numbers: Dezenas informadas.

        Returns:
            Dezenas únicas e ordenadas.

        Raises:
            ValueError: Mensagem pronta para o usuário quando algo é inválido.
        """
        unique = sorted(set(int(n) for n in numbers))
        if len(unique) != len(list(numbers)):
            raise ValueError("Há dezenas repetidas na aposta.")
        out_of_range = [n for n in unique if n < self.min_number or n > self.max_number]
        if out_of_range:
            raise ValueError(
                f"Dezenas fora da faixa {self.min_number}–{self.max_number}: "
                + ", ".join(str(n) for n in out_of_range)
            )
        if not self.bet_min <= len(unique) <= self.bet_max:
            if self.bet_min == self.bet_max:
                raise ValueError(f"{self.name}: marque exatamente {self.bet_min} dezenas.")
            raise ValueError(
                f"{self.name}: marque de {self.bet_min} a {self.bet_max} dezenas "
                f"(você marcou {len(unique)})."
            )
        return tuple(unique)

    def validate_trevos(self, trevos: tuple[int, ...] | list[int]) -> tuple[int, ...]:
        """Valida os trevos de uma aposta da +Milionária.

        Args:
            trevos: Trevos informados.

        Returns:
            Trevos únicos e ordenados (vazio para loterias sem trevo).

        Raises:
            ValueError: Quando a quantidade ou a faixa forem inválidas.
        """
        if not self.has_trevos:
            return ()
        unique = sorted(set(int(t) for t in trevos))
        if any(t < 1 or t > self.trevo_max for t in unique):
            raise ValueError(f"Trevos devem estar entre 1 e {self.trevo_max}.")
        if not self.trevo_draw <= len(unique) <= self.trevo_bet_max:
            raise ValueError(
                f"Marque de {self.trevo_draw} a {self.trevo_bet_max} trevos."
            )
        return tuple(unique)

    def format_number(self, number: int) -> str:
        """Formata a dezena com dois dígitos (padrão dos volantes)."""
        return f"{number:02d}"


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
