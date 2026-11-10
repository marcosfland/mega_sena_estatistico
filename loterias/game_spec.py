"""Classe de regras de uma loteria (:class:`GameSpec`) e faixas de prêmio."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import comb
from typing import Optional

from loterias import columns


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
        extra_options: Opções válidas do extra (meses do Dia de Sorte).
        columns: Número de colunas (Super Sete); 0 para loterias de dezenas.
            Nesse caso as "dezenas" são códigos ``coluna*10 + dígito``
            (ver :mod:`loterias.columns`).
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
    columns: int = 0

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
    def is_columns(self) -> bool:
        """Indica loteria por colunas (Super Sete)."""
        return self.columns > 0

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
        if self.is_columns:
            return columns.combinations(columns.balanced_counts(self, n_numbers))
        total = comb(n_numbers, self.bet_min)
        if self.has_trevos:
            total *= comb(n_trevos, self.trevo_draw)
        return total

    def bet_cost(self, n_numbers: int, n_trevos: int = 2) -> float:
        """Custo de uma aposta, em reais (Super Sete: marcações bem distribuídas).

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
        if self.is_columns:
            return columns.validate(self, numbers)
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

    def cost_of(self, numbers: tuple[int, ...] | list[int], n_trevos: int = 2) -> float:
        """Custo exato de uma aposta concreta (considera a distribuição por coluna)."""
        if self.is_columns:
            return columns.cost(self, numbers)
        return self.bet_cost(len(numbers), n_trevos or 2)

    def format_number(self, number: int) -> str:
        """Dezena com dois dígitos (Super Sete: ``"coluna·dígito"``)."""
        return columns.format_code(number) if self.is_columns else f"{number:02d}"

    def format_bet(self, numbers: tuple[int, ...] | list[int]) -> str:
        """Texto das dezenas de uma aposta."""
        if self.is_columns:
            return columns.format_bet(self, numbers)
        return " ".join(f"{n:02d}" for n in numbers)

    def parse_input(self, text: str) -> list[int]:
        """Lê dezenas digitadas (Super Sete: coluna a coluna, ``"5 3/8 7 1 4 0 6"``)."""
        if self.is_columns:
            return columns.parse(self, text)
        from loterias.models import parse_numbers

        return parse_numbers(text)
