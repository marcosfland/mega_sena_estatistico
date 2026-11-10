"""Persistência em SQLite: sorteios de todas as loterias, "Meus jogos" e bolões.

Cada operação abre e fecha sua própria conexão (seguro para uso em threads) e o
banco roda em modo WAL para evitar o erro "database is locked".
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

from loterias.models import Bet, Draw, PrizeTier, SavedBet

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS draws (
    game TEXT NOT NULL,
    contest INTEGER NOT NULL,
    date TEXT NOT NULL,
    numbers TEXT NOT NULL,
    numbers2 TEXT NOT NULL DEFAULT '',
    trevos TEXT NOT NULL DEFAULT '',
    extra TEXT NOT NULL DEFAULT '',
    prizes TEXT NOT NULL DEFAULT '[]',
    accumulated INTEGER NOT NULL DEFAULT 0,
    next_date TEXT,
    next_estimate REAL,
    PRIMARY KEY (game, contest)
);
CREATE TABLE IF NOT EXISTS saved_bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game TEXT NOT NULL,
    label TEXT NOT NULL,
    numbers TEXT NOT NULL,
    trevos TEXT NOT NULL DEFAULT '',
    extra TEXT NOT NULL DEFAULT '',
    target_contest INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_saved_bets_game ON saved_bets(game);
CREATE TABLE IF NOT EXISTS boloes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game TEXT NOT NULL,
    name TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _join(values: Iterable[int]) -> str:
    """Serializa dezenas como texto ``"1,2,3"``."""
    return ",".join(str(v) for v in values)


def _split(text: str) -> tuple[int, ...]:
    """Desserializa ``"1,2,3"`` para tupla de inteiros."""
    return tuple(int(v) for v in text.split(",") if v)


class Storage:
    """Repositório SQLite do aplicativo.

    Args:
        db_path: Arquivo do banco. É criado (com as tabelas) se não existir.
    """

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, tuple[int, list[Draw]]] = {}
        self._versions: dict[str, int] = {}
        self._lock = threading.Lock()
        self.init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Abre uma conexão com commit automático e fechamento garantido."""
        conn = sqlite3.connect(self.db_path, timeout=20.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            yield conn
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        """Cria as tabelas que ainda não existem."""
        with self.connect() as conn:
            conn.executescript(_SCHEMA)

    # ------------------------------------------------------------------ sorteios
    def upsert_draws(self, draws: Iterable[Draw]) -> int:
        """Insere ou atualiza sorteios.

        Args:
            draws: Sorteios (de qualquer loteria).

        Returns:
            Quantidade de linhas gravadas.
        """
        rows = [
            (
                d.game, d.contest, d.date.isoformat(), _join(d.numbers), _join(d.numbers2),
                _join(d.trevos), d.extra,
                json.dumps([[p.faixa, p.description, p.winners, p.amount] for p in d.prizes],
                           ensure_ascii=False),
                int(d.accumulated), d.next_date.isoformat() if d.next_date else None,
                d.next_estimate,
            )
            for d in draws
        ]
        if not rows:
            return 0
        with self.connect() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO draws VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows
            )
        with self._lock:
            for game in {r[0] for r in rows}:
                self._versions[game] = self._versions.get(game, 0) + 1
        return len(rows)

    @staticmethod
    def _row_to_draw(row: sqlite3.Row | tuple[Any, ...]) -> Draw:
        """Converte uma linha da tabela ``draws`` em :class:`Draw`."""
        (game, contest, date, numbers, numbers2, trevos, extra, prizes,
         accumulated, next_date, next_estimate) = row
        return Draw(
            game=game,
            contest=int(contest),
            date=dt.date.fromisoformat(date),
            numbers=_split(numbers),
            numbers2=_split(numbers2),
            trevos=_split(trevos),
            extra=extra,
            prizes=tuple(PrizeTier(int(f), str(d), int(w), float(a))
                         for f, d, w, a in json.loads(prizes or "[]")),
            accumulated=bool(accumulated),
            next_date=dt.date.fromisoformat(next_date) if next_date else None,
            next_estimate=next_estimate,
        )

    def load_draws(self, game: str) -> list[Draw]:
        """Todos os sorteios de uma loteria em ordem crescente de concurso (com cache)."""
        with self._lock:
            version = self._versions.get(game, 0)
            cached = self._cache.get(game)
            if cached and cached[0] == version:
                return cached[1]
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM draws WHERE game = ? ORDER BY contest", (game,)
            ).fetchall()
        draws = [self._row_to_draw(r) for r in rows]
        with self._lock:
            self._cache[game] = (version, draws)
        return draws

    def get_draw(self, game: str, contest: int) -> Optional[Draw]:
        """Um concurso específico, ou ``None`` se não estiver na base."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM draws WHERE game = ? AND contest = ?", (game, contest)
            ).fetchone()
        return self._row_to_draw(row) if row else None

    def latest_draw(self, game: str) -> Optional[Draw]:
        """O concurso mais recente da base, ou ``None`` se estiver vazia."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM draws WHERE game = ? ORDER BY contest DESC LIMIT 1", (game,)
            ).fetchone()
        return self._row_to_draw(row) if row else None

    def latest_contest(self, game: str) -> int:
        """Número do último concurso salvo (0 se a base estiver vazia)."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT MAX(contest) FROM draws WHERE game = ?", (game,)
            ).fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    def missing_contests(self, game: str, up_to: int) -> list[int]:
        """Concursos de 1 até ``up_to`` que ainda não estão na base."""
        with self.connect() as conn:
            have = {r[0] for r in conn.execute(
                "SELECT contest FROM draws WHERE game = ? AND contest <= ?", (game, up_to))}
        return [n for n in range(1, up_to + 1) if n not in have]

    def count_draws(self, game: str) -> int:
        """Quantidade de concursos salvos."""
        with self.connect() as conn:
            return int(conn.execute(
                "SELECT COUNT(*) FROM draws WHERE game = ?", (game,)).fetchone()[0])

    # --------------------------------------------------------------- meus jogos
    def save_bet(self, game: str, bet: Bet, label: str,
                 target_contest: Optional[int] = None) -> int:
        """Salva uma aposta em "Meus jogos" e devolve o id."""
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO saved_bets (game, label, numbers, trevos, extra, target_contest,"
                " created_at) VALUES (?,?,?,?,?,?,?)",
                (game, label, _join(bet.numbers), _join(bet.trevos), bet.extra,
                 target_contest, dt.datetime.now().isoformat(timespec="seconds")),
            )
            return int(cur.lastrowid)

    def list_bets(self, game: str) -> list[SavedBet]:
        """Apostas salvas de uma loteria, mais recentes primeiro."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, game, label, numbers, trevos, extra, target_contest, created_at"
                " FROM saved_bets WHERE game = ? ORDER BY id DESC", (game,)
            ).fetchall()
        return [
            SavedBet(id=r[0], game=r[1], label=r[2],
                     bet=Bet(_split(r[3]), _split(r[4]), r[5]),
                     target_contest=r[6], created_at=r[7])
            for r in rows
        ]

    def delete_bet(self, bet_id: int) -> bool:
        """Remove uma aposta salva. Retorna ``True`` se algo foi apagado."""
        with self.connect() as conn:
            return conn.execute("DELETE FROM saved_bets WHERE id = ?", (bet_id,)).rowcount > 0

    # ------------------------------------------------------------------- bolões
    def save_bolao(self, game: str, name: str, payload: dict[str, Any],
                   bolao_id: Optional[int] = None) -> int:
        """Cria ou atualiza um bolão (payload em JSON) e devolve o id."""
        now = dt.datetime.now().isoformat(timespec="seconds")
        data = json.dumps(payload, ensure_ascii=False)
        with self.connect() as conn:
            if bolao_id is not None:
                updated = conn.execute(
                    "UPDATE boloes SET name = ?, payload = ?, updated_at = ? WHERE id = ?",
                    (name, data, now, bolao_id),
                ).rowcount
                if updated:
                    return bolao_id
            cur = conn.execute(
                "INSERT INTO boloes (game, name, payload, created_at, updated_at)"
                " VALUES (?,?,?,?,?)", (game, name, data, now, now))
            return int(cur.lastrowid)

    def list_boloes(self, game: str) -> list[tuple[int, str, str]]:
        """Bolões salvos de uma loteria: ``(id, nome, atualizado_em)``."""
        with self.connect() as conn:
            return [tuple(r) for r in conn.execute(
                "SELECT id, name, updated_at FROM boloes WHERE game = ? ORDER BY id DESC",
                (game,))]

    def load_bolao(self, bolao_id: int) -> Optional[dict[str, Any]]:
        """Payload de um bolão, ou ``None`` se não existir."""
        with self.connect() as conn:
            row = conn.execute("SELECT payload FROM boloes WHERE id = ?", (bolao_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def delete_bolao(self, bolao_id: int) -> bool:
        """Apaga um bolão. Retorna ``True`` se algo foi apagado."""
        with self.connect() as conn:
            return conn.execute("DELETE FROM boloes WHERE id = ?", (bolao_id,)).rowcount > 0

    # --------------------------------------------------------------------- meta
    def set_meta(self, key: str, value: str) -> None:
        """Grava um valor auxiliar (ex.: horário da última sincronização)."""
        with self.connect() as conn:
            conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))

    def get_meta(self, key: str, default: str = "") -> str:
        """Lê um valor auxiliar."""
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default
