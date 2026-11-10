"""Banco SQLite, migração da versão antiga e sincronização incremental."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from conftest import FakeSource, make_draws

from loterias.games import get_game
from loterias.migration import run_migrations
from loterias.models import Bet
from loterias.storage import Storage
from loterias.updater import BULK_THRESHOLD, Updater


def test_roundtrip_all_fields(storage: Storage) -> None:
    """Todos os campos sobrevivem à gravação, inclusive Dupla Sena e trevos."""
    for slug in ("duplasena", "maismilionaria", "diadesorte"):
        original = make_draws(get_game(slug), 3)
        storage.upsert_draws(original)
        assert storage.load_draws(slug) == original


def test_upsert_is_idempotent_and_cache_refreshes(storage: Storage, mega_draws: list) -> None:
    """Regravar não duplica e o cache enxerga dados novos."""
    storage.upsert_draws(mega_draws[:10])
    assert len(storage.load_draws("megasena")) == 10
    storage.upsert_draws(mega_draws[:20])
    assert len(storage.load_draws("megasena")) == 20
    assert storage.latest_contest("megasena") == 20
    assert storage.missing_contests("megasena", 22) == [21, 22]
    assert storage.latest_contest("quina") == 0 and storage.latest_draw("quina") is None


def test_saved_bets_boloes_meta(storage: Storage) -> None:
    """CRUD de "Meus jogos", bolões e metadados."""
    bet_id = storage.save_bet("maismilionaria", Bet((1, 2, 3, 4, 5, 6), (1, 2)), "teste", 10)
    [saved] = storage.list_bets("maismilionaria")
    assert saved.id == bet_id and saved.bet.trevos == (1, 2) and saved.target_contest == 10
    assert storage.delete_bet(bet_id) and not storage.list_bets("maismilionaria")
    bid = storage.save_bolao("megasena", "Firma", {"a": 1})
    assert storage.save_bolao("megasena", "Firma 2", {"a": 2}, bid) == bid
    assert storage.load_bolao(bid) == {"a": 2}
    assert storage.list_boloes("megasena")[0][1] == "Firma 2"
    assert storage.delete_bolao(bid) and storage.load_bolao(bid) is None
    storage.set_meta("k", "v")
    assert storage.get_meta("k") == "v" and storage.get_meta("x", "d") == "d"


def test_concurrent_writes(storage: Storage, mega_draws: list) -> None:
    """Várias threads gravando ao mesmo tempo não corrompem nem travam o banco."""
    chunks = [mega_draws[i::4] for i in range(4)]
    threads = [threading.Thread(target=storage.upsert_draws, args=(c,)) for c in chunks]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert storage.count_draws("megasena") == len(mega_draws)


def test_migration_from_legacy(tmp_path: Path, storage: Storage) -> None:
    """Importa megasena.db (datas dd/mm/aaaa) e user_sets.db uma única vez."""
    legacy = tmp_path / "megasena.db"
    with sqlite3.connect(legacy) as conn:
        conn.execute("CREATE TABLE megasena (concurso INTEGER PRIMARY KEY, data TEXT, dez1 INT,"
                     " dez2 INT, dez3 INT, dez4 INT, dez5 INT, dez6 INT)")
        conn.execute("INSERT INTO megasena VALUES (1, '11/03/1996', 41, 5, 4, 52, 30, 33)")
        conn.execute("INSERT INTO megasena VALUES (2, 'lixo', 1, 2, 3, 4, 5, 6)")
    with sqlite3.connect(tmp_path / "user_sets.db") as conn:
        conn.execute("CREATE TABLE user_sets (id INTEGER PRIMARY KEY, name TEXT, date_generated"
                     " TEXT, dez1 INT, dez2 INT, dez3 INT, dez4 INT, dez5 INT, dez6 INT)")
        conn.execute("INSERT INTO user_sets VALUES (1, 'meu', '2024-01-01', 6, 5, 4, 3, 2, 1)")
    run_migrations(storage, tmp_path)
    run_migrations(storage, tmp_path)
    [draw] = storage.load_draws("megasena")
    assert draw.numbers == (4, 5, 30, 33, 41, 52) and draw.date.year == 1996
    assert [b.bet.numbers for b in storage.list_bets("megasena")] == [(1, 2, 3, 4, 5, 6)]


def test_sync_bulk_then_incremental(storage: Storage) -> None:
    """Base vazia baixa tudo de uma vez; depois só o que falta."""
    spec = get_game("quina")
    history = make_draws(spec, 120)
    source = FakeSource({"quina": history[:100]})
    updater = Updater(storage, source, request_delay=0)
    first = updater.sync_game("quina")
    assert first.ok and first.added == 100 and first.up_to_date
    assert ("all", "quina", None) in source.calls
    source.data["quina"].update({d.contest: d for d in history[100:]})
    source.calls.clear()
    progress: list[tuple[int, int]] = []
    second = updater.sync_game("quina", progress=lambda _s, d, t: progress.append((d, t)))
    assert second.added == 20 and storage.latest_contest("quina") == 120
    assert all(kind != "all" for kind, *_ in source.calls)
    assert progress[-1] == (19, 19)
    assert updater.last_sync("quina") is not None
    assert updater.sync_game("quina").message().endswith("concurso 120)")


def test_sync_falls_back_to_individual(storage: Storage) -> None:
    """Se o histórico completo falhar, baixa concurso a concurso."""
    spec = get_game("diadesorte")
    source = FakeSource({"diadesorte": make_draws(spec, BULK_THRESHOLD + 5)}, fail_all=True)
    result = Updater(storage, source, request_delay=0).sync_game("diadesorte")
    assert result.ok and storage.count_draws("diadesorte") == BULK_THRESHOLD + 5


def test_sync_offline_and_cancel(storage: Storage) -> None:
    """Sem internet: erro amigável. Cancelamento interrompe o download."""
    offline = Updater(storage, FakeSource({}, fail_latest=True)).sync_game("megasena")
    assert not offline.ok and "internet" in offline.message()
    spec = get_game("timemania")
    source = FakeSource({"timemania": make_draws(spec, 10)})
    cancel = threading.Event()
    cancel.set()
    updater = Updater(storage, source, request_delay=0)
    result = updater.sync_all(["timemania"], cancel=cancel)
    assert result == []
    assert updater.sync_game("timemania", cancel=cancel).added == 1  # só o último
