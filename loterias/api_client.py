"""Cliente HTTP para os resultados das loterias.

Fontes, em ordem de tentativa:

1. API oficial da Caixa (concursos novos);
2. API comunitária ``loteriascaixa-api``;
3. base versionada no GitHub (``dados/<loteria>.jsonl``, mantida pela rotina
   agendada do repositório). É também a primeira opção para baixar o
   histórico inteiro, por ser um único arquivo estático e rápido.

Toda falha de uma fonte é registrada em log e a próxima é tentada.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional

import requests

from loterias import dump
from loterias.games import GameSpec
from loterias.models import Draw
from loterias.parsers import ParseError, parse_community, parse_official

logger = logging.getLogger(__name__)

OFFICIAL_BASE = "https://servicebus2.caixa.gov.br/portaldeloterias/api"
COMMUNITY_BASE = "https://loteriascaixa-api.herokuapp.com/api"
REPO_DUMPS = os.getenv(
    "LOTERIAS_DADOS_URL",
    "https://raw.githubusercontent.com/marcosfland/mega_sena_estatistico/main/dados")
_DUMP_TTL = 600.0

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
        dumps_url: URL da pasta ``dados/`` no GitHub (``None`` desativa essa fonte).
    """

    def __init__(self, timeout: float = 20.0, retries: int = 1,
                 session: Optional[requests.Session] = None,
                 dumps_url: Optional[str] = REPO_DUMPS) -> None:
        self.timeout = timeout
        self.retries = retries
        self.dumps_url = dumps_url.rstrip("/") if dumps_url else None
        self._dumps: dict[str, tuple[float, list[Draw]]] = {}
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
        return self._get(url, as_json=True)

    def _get(self, url: str, as_json: bool) -> Any:
        """GET com novas tentativas; devolve JSON ou texto, ou levanta :class:`ApiError`."""
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self._session.get(url, timeout=self.timeout)
                if response.status_code == 404:
                    raise ApiError(f"404 em {url}")
                response.raise_for_status()
                return response.json() if as_json else response.text
            except ApiError:
                raise
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                logger.debug("Falha em %s (tentativa %d): %s", url, attempt + 1, exc)
                if attempt < self.retries:
                    time.sleep(0.8 * (attempt + 1))
        raise ApiError(f"{url}: {last_error}")

    def fetch_dump(self, spec: GameSpec) -> list[Draw]:
        """Histórico da base versionada no GitHub (com cache de 10 minutos).

        Raises:
            ApiError: Arquivo inexistente, vazio ou inacessível.
        """
        cached = self._dumps.get(spec.slug)
        if cached and time.monotonic() - cached[0] < _DUMP_TTL:
            return cached[1]
        if not self.dumps_url:
            raise ApiError("base do repositório desativada")
        url = f"{self.dumps_url}/{dump.dump_path(Path(), spec).name}"
        draws = dump.loads(spec, self._get(url, as_json=False))
        if not draws:
            raise ApiError(f"base vazia em {url}")
        self._dumps[spec.slug] = (time.monotonic(), draws)
        return draws

    def _dump_contest(self, spec: GameSpec, contest: Optional[int]) -> Draw:
        """Um concurso (ou o último, se ``contest`` for ``None``) da base do GitHub."""
        draws = self.fetch_dump(spec)
        if contest is None:
            return draws[-1]
        for draw in draws:
            if draw.contest == contest:
                return draw
        raise ApiError(f"concurso {contest} ainda não está na base do repositório")

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
            ("repositório", lambda: self._dump_contest(spec, None)),
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
            ("repositório", lambda: self._dump_contest(spec, contest)),
        ])

    def fetch_all(self, spec: GameSpec) -> list[Draw]:
        """Histórico completo numa única requisição.

        Tenta a base do GitHub (arquivo estático) e depois a API comunitária.
        Concursos com formato inválido são ignorados com aviso.

        Raises:
            ApiError: Se nenhuma das duas fontes responder.
        """
        try:
            return self.fetch_dump(spec)
        except (ApiError, ParseError) as exc:
            logger.info("%s: base do repositório indisponível (%s); usando a API comunitária",
                        spec.name, exc)
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
