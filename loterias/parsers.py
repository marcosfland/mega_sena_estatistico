"""Conversão das respostas JSON das APIs para :class:`~loterias.models.Draw`.

Dois formatos são suportados:

* **Oficial** (``servicebus2.caixa.gov.br/portaldeloterias/api``): chaves
  ``numero``, ``dataApuracao``, ``listaDezenas``, ``listaDezenasSegundoSorteio``,
  ``trevosSorteados``, ``nomeTimeCoracaoMesSorte``, ``listaRateioPremio``.
* **Comunitário** (``loteriascaixa-api.herokuapp.com``): chaves ``concurso``,
  ``data``, ``dezenas``, ``dezenasOrdemSorteio``, ``trevos``, ``timeCoracao``,
  ``mesSorte``, ``premiacoes``.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any, Optional

from loterias import columns
from loterias.games import MONTHS, GameSpec
from loterias.models import Draw, PrizeTier


class ParseError(ValueError):
    """Resposta da API num formato inesperado."""


def _date(text: Optional[str]) -> Optional[dt.date]:
    """Converte ``dd/mm/aaaa`` em data (``None`` se vazio)."""
    if not text:
        return None
    try:
        return dt.datetime.strptime(text.strip(), "%d/%m/%Y").date()
    except ValueError as exc:
        raise ParseError(f"data inválida: {text!r}") from exc


def _ints(values: Optional[list[Any]]) -> tuple[int, ...]:
    """Converte uma lista de strings numéricas em tupla de inteiros."""
    if not values:
        return ()
    try:
        return tuple(int(str(v).strip()) for v in values if str(v).strip())
    except ValueError as exc:
        raise ParseError(f"dezenas inválidas: {values!r}") from exc


def normalize_extra(spec: GameSpec, text: Optional[str]) -> str:
    """Padroniza Mês da Sorte (``"Março"``) e Time do Coração (``"LONDRINA/PR"``)."""
    if not text or not spec.extra_name:
        return ""
    clean = re.sub(r"\s+", " ", str(text).replace("\x00", "")).strip()
    clean = re.sub(r"\s*/\s*", "/", clean)
    if not clean:
        return ""
    if spec.extra_options:
        for option in spec.extra_options:
            if option.casefold() == clean.casefold():
                return option
        if clean.isdigit() and 1 <= int(clean) <= 12:
            return MONTHS[int(clean) - 1]
    return clean.upper()


def _split_double(spec: GameSpec, ordered: tuple[int, ...],
                  first: tuple[int, ...], second: tuple[int, ...]) -> tuple[tuple[int, ...],
                                                                            tuple[int, ...]]:
    """Separa os dois sorteios da Dupla Sena quando vierem misturados."""
    if not spec.double_draw:
        return tuple(sorted(first)), ()
    if second:
        return tuple(sorted(first[: spec.draw_size])), tuple(sorted(second))
    source = ordered if len(ordered) == 2 * spec.draw_size else first
    if len(source) != 2 * spec.draw_size:
        raise ParseError("Dupla Sena sem as 12 dezenas dos dois sorteios")
    return tuple(sorted(source[: spec.draw_size])), tuple(sorted(source[spec.draw_size:]))


def _column_codes(spec: GameSpec, ordered: tuple[int, ...],
                  fallback: tuple[int, ...]) -> tuple[int, ...]:
    """Super Sete: dígitos na ordem das colunas viram códigos ``coluna*10 + dígito``."""
    digits = ordered or fallback
    if len(digits) != spec.columns or any(d < 0 or d > 9 for d in digits):
        raise ParseError(f"Super Sete: esperados {spec.columns} dígitos, veio {digits!r}")
    return tuple(columns.encode(i, d) for i, d in enumerate(digits))


def _check(spec: GameSpec, draw: Draw) -> Draw:
    """Valida tamanho e faixa das dezenas antes de aceitar o sorteio."""
    for numbers in draw.number_sets():
        if len(numbers) != spec.draw_size or len(set(numbers)) != len(numbers):
            raise ParseError(f"{spec.name} {draw.contest}: {len(numbers)} dezenas recebidas")
        if any(n < spec.min_number or n > spec.max_number for n in numbers):
            raise ParseError(f"{spec.name} {draw.contest}: dezena fora da faixa")
    return draw


def parse_official(spec: GameSpec, data: dict[str, Any]) -> Draw:
    """Interpreta a resposta da API oficial da Caixa.

    Raises:
        ParseError: Se faltar algum campo obrigatório.
    """
    try:
        contest = int(data["numero"])
        date = _date(data["dataApuracao"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ParseError(f"resposta oficial incompleta: {exc}") from exc
    if date is None:
        raise ParseError("resposta oficial sem data")
    first = _ints(data.get("listaDezenas"))
    ordered = _ints(data.get("dezenasSorteadasOrdemSorteio"))
    if spec.is_columns:
        numbers, numbers2 = _column_codes(spec, ordered, first), ()
    else:
        numbers, numbers2 = _split_double(
            spec, ordered, first, _ints(data.get("listaDezenasSegundoSorteio")))
    prizes = tuple(
        PrizeTier(int(p.get("faixa", i + 1)), str(p.get("descricaoFaixa", "")),
                  int(p.get("numeroDeGanhadores") or 0), float(p.get("valorPremio") or 0.0))
        for i, p in enumerate(data.get("listaRateioPremio") or [])
    )
    return _check(spec, Draw(
        game=spec.slug, contest=contest, date=date, numbers=numbers, numbers2=numbers2,
        trevos=tuple(sorted(_ints(data.get("trevosSorteados")))),
        extra=normalize_extra(spec, data.get("nomeTimeCoracaoMesSorte")),
        prizes=prizes, accumulated=bool(data.get("acumulado")),
        next_date=_date(data.get("dataProximoConcurso")),
        next_estimate=data.get("valorEstimadoProximoConcurso"),
    ))


def parse_community(spec: GameSpec, data: dict[str, Any]) -> Draw:
    """Interpreta a resposta da API comunitária (loteriascaixa-api).

    Raises:
        ParseError: Se faltar algum campo obrigatório.
    """
    try:
        contest = int(data["concurso"])
        date = _date(data["data"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ParseError(f"resposta comunitária incompleta: {exc}") from exc
    if date is None:
        raise ParseError("resposta comunitária sem data")
    ordered, plain = _ints(data.get("dezenasOrdemSorteio")), _ints(data.get("dezenas"))
    if spec.is_columns:
        numbers, numbers2 = _column_codes(spec, ordered, plain), ()
    else:
        numbers, numbers2 = _split_double(spec, ordered, plain, ())
    extra_raw = data.get("mesSorte") if spec.extra_options else data.get("timeCoracao")
    prizes = tuple(
        PrizeTier(int(p.get("faixa", i + 1)), str(p.get("descricao", "")),
                  int(p.get("ganhadores") or 0), float(p.get("valorPremio") or 0.0))
        for i, p in enumerate(data.get("premiacoes") or [])
    )
    return _check(spec, Draw(
        game=spec.slug, contest=contest, date=date, numbers=numbers, numbers2=numbers2,
        trevos=tuple(sorted(_ints(data.get("trevos")))),
        extra=normalize_extra(spec, extra_raw), prizes=prizes,
        accumulated=bool(data.get("acumulou")),
        next_date=_date(data.get("dataProximoConcurso")),
        next_estimate=data.get("valorEstimadoProximoConcurso"),
    ))
