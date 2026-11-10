"""Cliente HTTP para os resultados das loterias.

Usa a API oficial da Caixa como fonte principal e a API comunitária
``loteriascaixa-api`` como alternativa (e para baixar o histórico inteiro de
uma vez). Toda falha de uma fonte é registrada em log e a outra é tentada.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional

import requests

from loterias.games import GameSpec
from loterias.models import Draw
from loterias.parsers import ParseError, parse_community, parse_official

logger = logging.getLogger(__name__)

OFFICIAL_BASE = "https://servicebus2.caixa.gov.br/portaldeloterias/api"
COMMUNITY_BASE = "https://loteriascaixa-api.herokuapp.com/api"

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


class ApiError(RuntimeError):
    """Nenhuma fonte conseguiu responder."""


class LotteryApiClient:
    """Busca resultados nas APIs públicas.

    Args:
        timeout: Tempo limite por requisição, em segundos.
        retries: Tentativas extras por fonte em falhas de rede.
        session: Sessão ``requests`` (injetável em testes).
    """

    def __init__(self, timeout: float = 20.0, retries: int = 1,
                 session: Optional[requests.Session] = None) -> None:
        self.timeout = timeout
        self.retries = retries
        self._session = session or requests.Session()
        self._session.headers.update(_HEADERS)

    def close(self) -> None:
        """Fecha as conexões HTTP abertas."""
        self._session.close()

    def __enter__(self) -> "LotteryApiClient":
        """Permite ``with LotteryApiClient() as client:``."""
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Fecha a sessão ao sair do bloco ``with``."""
        self.close()

    def _get_json(self, url: str) -> Any:
        """GET com novas tentativas; devolve o JSON ou levanta :class:`ApiError`."""
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self._session.get(url, timeout=self.timeout)
                if response.status_code == 404:
                    raise ApiError(f"404 em {url}")
                response.raise_for_status()
                return response.json()
            except ApiError:
                raise
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                logger.debug("Falha em %s (tentativa %d): %s", url, attempt + 1, exc)
                if attempt < self.retries:
                    time.sleep(0.8 * (attempt + 1))
        raise ApiError(f"{url}: {last_error}")

    def _first_ok(self, attempts: list[tuple[str, Callable[[], Draw]]]) -> Draw:
        """Executa as fontes em ordem e devolve o primeiro resultado válido."""
        errors: list[str] = []
        for source, fetch in attempts:
            try:
                return fetch()
            except (ApiError, ParseError) as exc:
                logger.warning("Fonte %s falhou: %s", source, exc)
                errors.append(f"{source}: {exc}")
        raise ApiError("; ".join(errors))

    def fetch_latest(self, spec: GameSpec) -> Draw:
        """Último concurso disponível.

        Raises:
            ApiError: Se nenhuma fonte responder.
        """
        return self._first_ok([
            ("oficial", lambda: parse_official(
                spec, self._get_json(f"{OFFICIAL_BASE}/{spec.slug}"))),
            ("comunitária", lambda: parse_community(
                spec, self._get_json(f"{COMMUNITY_BASE}/{spec.slug}/latest"))),
        ])

    def fetch_contest(self, spec: GameSpec, contest: int) -> Draw:
        """Um concurso específico.

        Raises:
            ApiError: Se nenhuma fonte responder.
        """
        return self._first_ok([
            ("oficial", lambda: parse_official(
                spec, self._get_json(f"{OFFICIAL_BASE}/{spec.slug}/{contest}"))),
            ("comunitária", lambda: parse_community(
                spec, self._get_json(f"{COMMUNITY_BASE}/{spec.slug}/{contest}"))),
        ])

    def fetch_all(self, spec: GameSpec) -> list[Draw]:
        """Histórico completo numa única requisição (API comunitária).

        Concursos com formato inválido são ignorados com aviso.

        Raises:
            ApiError: Se a requisição falhar ou não vier uma lista.
        """
        payload = self._get_json(f"{COMMUNITY_BASE}/{spec.slug}")
        if not isinstance(payload, list):
            raise ApiError("histórico completo não veio como lista")
        draws: list[Draw] = []
        for item in payload:
            try:
                draws.append(parse_community(spec, item))
            except ParseError as exc:
                logger.warning("%s: concurso ignorado no histórico (%s)", spec.name, exc)
        return draws
