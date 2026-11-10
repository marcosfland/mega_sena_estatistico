"""Parsers dos dois formatos de API e cliente HTTP com fallback."""

from __future__ import annotations

from typing import Any

import pytest
import requests

from loterias.api_client import ApiError, LotteryApiClient
from loterias.games import get_game
from loterias.parsers import ParseError, normalize_extra, parse_community, parse_official

# Recortes reais (out/2026) das respostas das APIs.
OFFICIAL_MEGA = {
    "acumulado": True, "dataApuracao": "14/10/2026", "dataProximoConcurso": "18/10/2026",
    "dezenasSorteadasOrdemSorteio": ["54", "43", "60", "29", "19", "27"],
    "listaDezenas": ["19", "27", "29", "43", "54", "60"], "listaDezenasSegundoSorteio": None,
    "listaRateioPremio": [
        {"descricaoFaixa": "6 acertos", "faixa": 1, "numeroDeGanhadores": 0, "valorPremio": 0.0},
        {"descricaoFaixa": "5 acertos", "faixa": 2, "numeroDeGanhadores": 91,
         "valorPremio": 52767.96},
        {"descricaoFaixa": "4 acertos", "faixa": 3, "numeroDeGanhadores": 7384,
         "valorPremio": 1071.93}],
    "nomeTimeCoracaoMesSorte": "\u0000" * 17, "numero": 3070,
    "valorEstimadoProximoConcurso": 170000000.0,
}
COMMUNITY_DUPLA = {
    "loteria": "duplasena", "concurso": 3021, "data": "16/10/2026",
    "dezenasOrdemSorteio": ["35", "03", "50", "44", "04", "37",
                            "24", "49", "28", "02", "21", "05"],
    "dezenas": ["02", "03", "04", "05", "21", "24", "28", "35", "37", "44", "49", "50"],
    "trevos": [], "timeCoracao": None, "mesSorte": None,
    "premiacoes": [{"descricao": "6 acertos", "faixa": 1, "ganhadores": 0, "valorPremio": 0.0}],
    "acumulou": True, "dataProximoConcurso": "19/10/2026",
    "valorEstimadoProximoConcurso": 8500000.0,
}
OFFICIAL_MAIS = {"numero": 398, "dataApuracao": "14/10/2026",
                 "listaDezenas": ["03", "04", "05", "31", "38", "41"],
                 "trevosSorteados": ["4", "1"], "nomeTimeCoracaoMesSorte": None}
OFFICIAL_TIME = {"numero": 2455, "dataApuracao": "15/10/2026",
                 "listaDezenas": ["07", "28", "31", "32", "60", "61", "76"],
                 "nomeTimeCoracaoMesSorte": "LONDRINA         /PR"}


def test_parse_official_mega() -> None:
    """Formato oficial: dezenas, rateio e estimativa."""
    draw = parse_official(get_game("megasena"), OFFICIAL_MEGA)
    assert draw.contest == 3070 and draw.date.isoformat() == "2026-10-14"
    assert draw.numbers == (19, 27, 29, 43, 54, 60)
    assert draw.extra == "" and draw.accumulated
    assert draw.prize_amount(2) == pytest.approx(52767.96)
    assert draw.next_estimate == 170000000.0 and draw.next_date.day == 18


def test_parse_community_dupla_splits_draws() -> None:
    """Dupla Sena comunitária: os dois sorteios vêm misturados e são separados pela ordem."""
    draw = parse_community(get_game("duplasena"), COMMUNITY_DUPLA)
    assert draw.numbers == (3, 4, 35, 37, 44, 50)
    assert draw.numbers2 == (2, 5, 21, 24, 28, 49)


def test_parse_trevos_and_team() -> None:
    """Trevos da +Milionária e Time do Coração normalizado."""
    assert parse_official(get_game("maismilionaria"), OFFICIAL_MAIS).trevos == (1, 4)
    assert parse_official(get_game("timemania"), OFFICIAL_TIME).extra == "LONDRINA/PR"


def test_normalize_month() -> None:
    """Mês da Sorte vira o nome padronizado."""
    spec = get_game("diadesorte")
    assert normalize_extra(spec, "MARÇO") == "Março"
    assert normalize_extra(spec, "3") == "Março"
    assert normalize_extra(get_game("megasena"), "qualquer") == ""


@pytest.mark.parametrize("payload", [
    {"numero": 1},
    {"numero": 1, "dataApuracao": "31/02/2020", "listaDezenas": ["1"]},
    {"numero": 1, "dataApuracao": "01/02/2020", "listaDezenas": ["1", "2", "3", "4", "5", "99"]},
    {"numero": 1, "dataApuracao": "01/02/2020", "listaDezenas": ["a"]},
])
def test_parse_official_invalid(payload: dict[str, Any]) -> None:
    """Respostas incompletas ou inválidas levantam ParseError."""
    with pytest.raises(ParseError):
        parse_official(get_game("megasena"), payload)


class _Response:
    """Resposta HTTP mínima."""

    def __init__(self, status: int, payload: Any) -> None:
        self.status_code, self._payload = status, payload

    def raise_for_status(self) -> None:
        """Simula requests."""
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self) -> Any:
        """Corpo JSON."""
        return self._payload


class _Session(requests.Session):
    """Sessão que responde por prefixo de URL."""

    def __init__(self, routes: dict[str, _Response]) -> None:
        super().__init__()
        self.routes, self.urls = routes, []

    def get(self, url: str, **_kwargs: Any) -> _Response:  # type: ignore[override]
        """Devolve a rota cadastrada ou erro de conexão."""
        self.urls.append(url)
        for prefix, response in self.routes.items():
            if url.endswith(prefix):
                return response
        raise requests.ConnectionError("sem rota")


def test_client_falls_back_to_community() -> None:
    """Se a API oficial falhar, usa a comunitária."""
    session = _Session({"/duplasena/latest": _Response(200, COMMUNITY_DUPLA)})
    with LotteryApiClient(retries=0, session=session) as client:
        draw = client.fetch_latest(get_game("duplasena"))
    assert draw.contest == 3021
    assert "servicebus2.caixa.gov.br" in session.urls[0]


def test_client_official_first_and_bulk() -> None:
    """Oficial é a primeira fonte; histórico completo ignora itens inválidos."""
    session = _Session({"/megasena": _Response(200, [
        {"concurso": 1, "data": "11/03/1996", "dezenas": ["04", "05", "30", "33", "41", "52"]},
        {"concurso": 2, "data": "xx"}]),
        "/api/megasena/3070": _Response(200, OFFICIAL_MEGA),
        "/portaldeloterias/api/megasena/3070": _Response(200, OFFICIAL_MEGA)})
    client = LotteryApiClient(retries=0, session=session)
    assert client.fetch_contest(get_game("megasena"), 3070).contest == 3070
    assert [d.contest for d in client.fetch_all(get_game("megasena"))] == [1]


def test_client_all_sources_fail() -> None:
    """Sem nenhuma fonte, ApiError com o resumo das falhas."""
    client = LotteryApiClient(retries=1, session=_Session({"/megasena/9": _Response(404, {})}))
    with pytest.raises(ApiError, match="oficial"):
        client.fetch_contest(get_game("megasena"), 9)
