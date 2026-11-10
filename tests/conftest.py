"""Fixtures compartilhadas: bases temporárias, sorteios sintéticos e API falsa."""

from __future__ import annotations

import datetime as dt
import random
import sys
from pathlib import Path
from typing import Optional

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loterias.games import MONTHS, GameSpec, get_game  # noqa: E402
from loterias.models import Draw, PrizeTier  # noqa: E402
from loterias.storage import Storage  # noqa: E402


def make_draws(spec: GameSpec, n: int, seed: int = 1, start: int = 1) -> list[Draw]:
    """Gera ``n`` concursos aleatórios válidos para a loteria."""
    rng = random.Random(seed)
    day = dt.date(2020, 1, 1)
    draws = []
    for contest in range(start, start + n):
        pool = list(spec.numbers)
        if spec.is_columns:  # Super Sete: um dígito por coluna, como no sorteio real
            numbers = tuple(c * 10 + rng.randrange(10) for c in range(spec.columns))
        else:
            numbers = tuple(sorted(rng.sample(pool, spec.draw_size)))
        numbers2 = tuple(sorted(rng.sample(pool, spec.draw_size))) if spec.double_draw else ()
        trevos = tuple(sorted(rng.sample(range(1, spec.trevo_max + 1), spec.trevo_draw))) \
            if spec.has_trevos else ()
        extra = rng.choice(MONTHS) if spec.extra_options else (
            "FLAMENGO/RJ" if spec.extra_name else "")
        prizes = tuple(PrizeTier(r.faixa, r.name, 1, 1000.0 / r.faixa) for r in spec.prizes)
        draws.append(Draw(spec.slug, contest, day + dt.timedelta(days=3 * contest), numbers,
                          numbers2, trevos, extra, prizes))
    return draws


class FakeSource:
    """Dublê da API: serve concursos de uma lista em memória."""

    def __init__(self, draws_by_game: dict[str, list[Draw]], fail_latest: bool = False,
                 fail_all: bool = False) -> None:
        self.data = {g: {d.contest: d for d in ds} for g, ds in draws_by_game.items()}
        self.fail_latest = fail_latest
        self.fail_all = fail_all
        self.calls: list[tuple[str, str, Optional[int]]] = []

    def fetch_latest(self, spec: GameSpec) -> Draw:
        """Último concurso conhecido."""
        self.calls.append(("latest", spec.slug, None))
        if self.fail_latest or not self.data.get(spec.slug):
            raise ConnectionError("offline")
        return self.data[spec.slug][max(self.data[spec.slug])]

    def fetch_contest(self, spec: GameSpec, contest: int) -> Draw:
        """Concurso específico."""
        self.calls.append(("contest", spec.slug, contest))
        return self.data[spec.slug][contest]

    def fetch_all(self, spec: GameSpec) -> list[Draw]:
        """Histórico completo."""
        self.calls.append(("all", spec.slug, None))
        if self.fail_all:
            raise ConnectionError("bulk offline")
        return list(self.data[spec.slug].values())


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    """Banco vazio num diretório temporário."""
    return Storage(tmp_path / "test.db")


@pytest.fixture
def mega() -> GameSpec:
    """Regras da Mega-Sena."""
    return get_game("megasena")


@pytest.fixture
def mega_draws(mega: GameSpec) -> list[Draw]:
    """400 concursos sintéticos da Mega-Sena."""
    return make_draws(mega, 400)
