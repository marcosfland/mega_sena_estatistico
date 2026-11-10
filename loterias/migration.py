"""Importa a base da versão anterior (``megasena.db`` e ``user_sets.db``).

Executado automaticamente na inicialização: se a nova base ainda não tiver
sorteios da Mega-Sena e o arquivo antigo existir, os concursos são copiados para
evitar baixar tudo de novo. A operação é idempotente.
"""

from __future__ import annotations

import datetime as dt
import logging
import sqlite3
from pathlib import Path

from loterias.models import Bet, Draw
from loterias.storage import Storage

logger = logging.getLogger(__name__)


def _parse_legacy_date(text: str) -> dt.date:
    """Aceita ``dd/mm/aaaa`` (formato antigo) ou ISO."""
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"data inválida: {text!r}")


def migrate_legacy_megasena(storage: Storage, legacy_db: Path) -> int:
    """Copia os concursos de ``megasena.db`` (tabela ``megasena``) para a nova base.

    Args:
        storage: Base nova.
        legacy_db: Caminho do banco antigo.

    Returns:
        Quantidade de concursos importados (0 se nada a fazer).
    """
    if not legacy_db.exists() or storage.count_draws("megasena") > 0:
        return 0
    draws: list[Draw] = []
    try:
        with sqlite3.connect(legacy_db, timeout=10.0) as conn:
            rows = conn.execute(
                "SELECT concurso, data, dez1, dez2, dez3, dez4, dez5, dez6 FROM megasena"
            ).fetchall()
    except sqlite3.Error as exc:
        logger.warning("Base antiga %s não pôde ser lida: %s", legacy_db, exc)
        return 0
    for row in rows:
        try:
            draws.append(Draw("megasena", int(row[0]), _parse_legacy_date(row[1]),
                              tuple(sorted(int(n) for n in row[2:8]))))
        except (TypeError, ValueError) as exc:
            logger.warning("Concurso antigo ignorado (%s): %s", row[:2], exc)
    imported = storage.upsert_draws(draws)
    logger.info("Migração: %d concursos da Mega-Sena importados de %s", imported, legacy_db)
    return imported


def migrate_legacy_user_sets(storage: Storage, legacy_db: Path) -> int:
    """Copia os conjuntos salvos de ``user_sets.db`` para "Meus jogos".

    Returns:
        Quantidade de apostas importadas.
    """
    if not legacy_db.exists() or storage.get_meta("migrated_user_sets") == "1":
        return 0
    imported = 0
    try:
        with sqlite3.connect(legacy_db, timeout=10.0) as conn:
            rows = conn.execute(
                "SELECT name, dez1, dez2, dez3, dez4, dez5, dez6 FROM user_sets"
            ).fetchall()
    except sqlite3.Error as exc:
        logger.warning("user_sets.db não pôde ser lido: %s", exc)
        rows = []
    for name, *nums in rows:
        try:
            storage.save_bet("megasena", Bet(tuple(sorted(int(n) for n in nums))), str(name))
            imported += 1
        except (TypeError, ValueError) as exc:
            logger.warning("Conjunto antigo '%s' ignorado: %s", name, exc)
    storage.set_meta("migrated_user_sets", "1")
    if imported:
        logger.info("Migração: %d apostas importadas de %s", imported, legacy_db)
    return imported


def run_migrations(storage: Storage, project_root: Path) -> None:
    """Executa todas as migrações conhecidas a partir da raiz do projeto."""
    for folder in (project_root, project_root / "_legado"):
        migrate_legacy_megasena(storage, folder / "megasena.db")
        migrate_legacy_user_sets(storage, folder / "user_sets.db")
