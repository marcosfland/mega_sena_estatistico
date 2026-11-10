"""Suporte a loterias por colunas (Super Sete).

Na Super Sete são sorteados 7 dígitos (0–9), um por coluna, e o apostador marca
de 1 a 3 dígitos em cada coluna. Para reaproveitar todo o resto do projeto (que
trabalha com conjuntos de inteiros), cada marcação vira um **código**
``coluna * 10 + dígito``: o dígito 8 na 3ª coluna é o código 28. Assim:

* um sorteio são 7 códigos (um por coluna);
* acertos = interseção entre os códigos da aposta e do sorteio = colunas acertadas;
* frequência e atraso por código = estatística de cada dígito em cada coluna.
"""

from __future__ import annotations

import re
from math import prod
from typing import TYPE_CHECKING, Iterable, Sequence

if TYPE_CHECKING:
    from loterias.games import GameSpec

DIGITS = 10
MAX_PER_COLUMN = 3


def encode(column: int, digit: int) -> int:
    """Código de um dígito numa coluna (coluna começando em 0)."""
    return column * DIGITS + digit


def decode(code: int) -> tuple[int, int]:
    """``(coluna, dígito)`` de um código."""
    return divmod(code, DIGITS)


def by_column(spec: "GameSpec", codes: Iterable[int]) -> list[list[int]]:
    """Dígitos marcados em cada coluna."""
    columns: list[list[int]] = [[] for _ in range(spec.columns)]
    for code in sorted(codes):
        column, digit = decode(code)
        columns[column].append(digit)
    return columns


def balanced_counts(spec: "GameSpec", n_numbers: int) -> list[int]:
    """Distribui ``n_numbers`` marcações pelas colunas o mais igual possível."""
    base, extra = divmod(n_numbers, spec.columns)
    return [base + (1 if i < extra else 0) for i in range(spec.columns)]


def combinations(counts: Sequence[int]) -> int:
    """Apostas simples contidas numa aposta (produto das marcações por coluna)."""
    return prod(counts)


def validate(spec: "GameSpec", numbers: Iterable[int]) -> tuple[int, ...]:
    """Valida códigos de uma aposta por colunas.

    Raises:
        ValueError: Código inválido, coluna vazia ou com mais de 3 dígitos.
    """
    values = [int(n) for n in numbers]
    unique = sorted(set(values))
    if len(unique) != len(values):
        raise ValueError("Há dígitos repetidos na mesma coluna.")
    if any(n < 0 or n >= spec.columns * DIGITS for n in unique):
        raise ValueError("Marcação fora das 7 colunas.")
    for index, digits in enumerate(by_column(spec, unique), start=1):
        if not 1 <= len(digits) <= MAX_PER_COLUMN:
            raise ValueError(f"Coluna {index}: marque de 1 a {MAX_PER_COLUMN} números.")
    return tuple(unique)


def cost(spec: "GameSpec", numbers: Iterable[int]) -> float:
    """Custo exato de uma aposta por colunas."""
    counts = [len(d) for d in by_column(spec, numbers)]
    return round(spec.price * combinations(counts), 2)


def parse(spec: "GameSpec", text: str) -> list[int]:
    """Lê uma aposta digitada coluna a coluna: ``"5 3/8 7 1 4 0 6"``.

    Cada grupo separado por espaço é uma coluna; vários dígitos na mesma coluna
    são separados por ``/`` ou ``,``.

    Raises:
        ValueError: Quantidade de colunas errada ou caractere inválido.
    """
    groups = text.split()
    if len(groups) != spec.columns:
        raise ValueError(f"Informe as {spec.columns} colunas separadas por espaço "
                         "(ex.: 5 3/8 7 1 4 0 6).")
    codes: list[int] = []
    for column, group in enumerate(groups):
        for token in filter(None, re.split(r"[/,;]", group)):
            if not token.isdigit() or int(token) >= DIGITS:
                raise ValueError(f"Coluna {column + 1}: '{token}' não é um dígito de 0 a 9.")
            codes.append(encode(column, int(token)))
    return codes


def format_code(code: int) -> str:
    """Rótulo curto e sem ambiguidade: ``28 -> "3·8"`` (coluna 3, dígito 8)."""
    column, digit = decode(code)
    return f"{column + 1}·{digit}"


def format_bet(spec: "GameSpec", numbers: Iterable[int]) -> str:
    """Texto da aposta por coluna: ``"5 | 3/8 | 7 | 1 | 4 | 0 | 6"``."""
    return " | ".join("/".join(str(d) for d in digits) for digits in by_column(spec, numbers))


def digits_of(numbers: Sequence[int]) -> list[int]:
    """Dígitos de um sorteio na ordem das colunas."""
    return [decode(code)[1] for code in sorted(numbers)]
