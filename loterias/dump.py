"""Base de sorteios em texto, versionada no repositório (``dados/<loteria>.jsonl``).

Um concurso por linha, em JSON, ordenado por número do concurso. O formato é
pensado para o git: cada atualização só acrescenta linhas no fim do arquivo.

Usos:

* a rotina agendada do GitHub Actions (``scripts/atualizar_base.py``) mantém
  esses arquivos em dia;
* o app usa os arquivos locais (repositório ou instalador) para começar com a
  base pronta e, pela internet, como fonte de reserva quando as APIs falham.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path
from typing import Any, Iterable

from loterias.games import GAMES, GameSpec
from loterias.models import Draw, PrizeTier
from loterias.storage import Storage

logger = logging.getLogger(__name__)


def draw_to_dict(draw: Draw) -> dict[str, Any]:
    """Serializa um sorteio (campos vazios são omitidos para economizar espaço)."""
    data: dict[str, Any] = {"c": draw.contest, "d": draw.date.isoformat(),
                            "n": list(draw.numbers)}
    if draw.numbers2:
        data["n2"] = list(draw.numbers2)
    if draw.trevos:
        data["t"] = list(draw.trevos)
    if draw.extra:
        data["x"] = draw.extra
    if draw.prizes:
        data["p"] = [[p.faixa, p.description, p.winners, p.amount] for p in draw.prizes]
    if draw.accumulated:
        data["a"] = 1
    if draw.next_date:
        data["nd"] = draw.next_date.isoformat()
    if draw.next_estimate:
        data["ne"] = draw.next_estimate
    return data


def draw_from_dict(spec: GameSpec, data: dict[str, Any]) -> Draw:
    """Reconstrói um sorteio a partir de :func:`draw_to_dict`.

    Raises:
        KeyError, ValueError, TypeError: Linha malformada.
    """
    return Draw(
        game=spec.slug, contest=int(data["c"]), date=dt.date.fromisoformat(data["d"]),
        numbers=tuple(int(n) for n in data["n"]),
        numbers2=tuple(int(n) for n in data.get("n2", ())),
        trevos=tuple(int(n) for n in data.get("t", ())), extra=str(data.get("x", "")),
        prizes=tuple(PrizeTier(int(f), str(d), int(w), float(a))
                     for f, d, w, a in data.get("p", ())),
        accumulated=bool(data.get("a")),
        next_date=dt.date.fromisoformat(data["nd"]) if data.get("nd") else None,
        next_estimate=data.get("ne"),
    )


def dumps(draws: Iterable[Draw]) -> str:
    """Texto JSONL de uma lista de sorteios, ordenado por concurso."""
    ordered = sorted(draws, key=lambda d: d.contest)
    return "".join(json.dumps(draw_to_dict(d), ensure_ascii=False, separators=(",", ":"))
                   + "\n" for d in ordered)


def loads(spec: GameSpec, text: str) -> list[Draw]:
    """Lê JSONL; linhas inválidas são ignoradas com aviso."""
    draws: list[Draw] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            draws.append(draw_from_dict(spec, json.loads(line)))
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("%s, linha %d ignorada: %s", spec.name, line_no, exc)
    return draws


def dump_path(folder: Path, spec: GameSpec) -> Path:
    """Arquivo da loteria dentro da pasta de dados."""
    return folder / f"{spec.slug}.jsonl"


def export_storage(storage: Storage, folder: Path) -> list[str]:
    """Grava os arquivos JSONL de todas as loterias.

    Returns:
        Slugs cujos arquivos mudaram (os idênticos não são reescritos).
    """
    folder.mkdir(parents=True, exist_ok=True)
    changed: list[str] = []
    for spec in GAMES.values():
        draws = storage.load_draws(spec.slug)
        if not draws:
            continue
        path = dump_path(folder, spec)
        text = dumps(draws)
        if path.exists() and path.read_text(encoding="utf-8") == text:
            continue
        path.write_text(text, encoding="utf-8", newline="\n")
        changed.append(spec.slug)
    return changed


def seed_storage(storage: Storage, folder: Path, only_empty: bool = True) -> dict[str, int]:
    """Importa os arquivos JSONL de ``folder`` para a base.

    Args:
        storage: Base local.
        folder: Pasta com ``<loteria>.jsonl``.
        only_empty: Importa só loterias ainda sem concursos (evita trabalho a cada início).

    Returns:
        Concursos importados por loteria.
    """
    imported: dict[str, int] = {}
    if not folder.is_dir():
        return imported
    for spec in GAMES.values():
        path = dump_path(folder, spec)
        if not path.exists() or (only_empty and storage.count_draws(spec.slug)):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Não foi possível ler %s: %s", path, exc)
            continue
        count = storage.upsert_draws(loads(spec, text))
        if count:
            imported[spec.slug] = count
            logger.info("%s: %d concursos importados de %s", spec.name, count, path)
    return imported
