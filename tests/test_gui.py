"""Teste de fumaça da interface (precisa de display; pulado em ambientes sem tela)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from conftest import FakeSource, make_draws

from loterias.games import GAMES, get_game

tk = pytest.importorskip("tkinter")
pytest.importorskip("customtkinter")


def _has_display() -> bool:
    """Verifica se dá para abrir uma janela.

    No Windows sempre há área de trabalho; não criamos um Tk descartável porque
    reinicializar o Tcl no mesmo processo falha no Python 3.10 dos runners do GitHub.
    """
    if os.name == "nt":
        return True
    if not os.environ.get("DISPLAY"):
        return False
    try:
        root = tk.Tk()
        root.destroy()
        return True
    except tk.TclError:
        return False


pytestmark = pytest.mark.skipif(not _has_display(), reason="sem display gráfico")


def _pump(app: "tk.Misc", ms: int = 400) -> None:
    """Processa eventos (inclusive callbacks de threads) por ``ms`` milissegundos."""
    import time
    end = time.time() + ms / 1000
    while time.time() < end:
        app.update()
        time.sleep(0.02)


def test_gui_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Abre o app, troca de loteria, gera jogos, confere, monta bolão e fecha."""
    monkeypatch.setenv("LOTERIAS_DATA_DIR", str(tmp_path))
    (tmp_path / "settings.json").write_text('{"auto_update": false}', encoding="utf-8")
    from loterias.gui.app import App
    from loterias.services import build_services

    source = FakeSource({"megasena": make_draws(get_game("megasena"), 200)})
    services = build_services(tmp_path / "gui.db", source=source, migrate=False)
    services.updater.request_delay = 0
    app = App(services)
    try:
        app.start_sync(["megasena"])
        _pump(app, 1500)
        assert services.storage.count_draws("megasena") == 200
        for slug in GAMES:
            app.set_game(slug)
            _pump(app, 50)
        app.set_game("megasena")
        gen = app.pages["Gerador"]
        gen.count_entry.delete(0, "end")
        gen.count_entry.insert(0, "abc")
        gen.generate()
        assert "1 a 100" in gen.notice.cget("text")
        gen.count_entry.delete(0, "end")
        gen.count_entry.insert(0, "4")
        gen.generate()
        _pump(app, 1000)
        assert len(gen._bets) == 4
        gen.save()
        _pump(app, 300)
        checker = app.pages["Conferir"]
        assert len(services.storage.list_bets("megasena")) == 4
        checker.picker.set_selected(services.storage.latest_draw("megasena").numbers)
        checker.check()
        import customtkinter as ctk
        texts = [w.cget("text") for w in checker.result_box.winfo_children()
                 if isinstance(w, ctk.CTkLabel)]
        assert any("Sena" in text for text in texts)
        bolao = app.pages["Bolão"]
        bolao.budget_entry.insert(0, "60")
        bolao.build()
        _pump(app, 1000)
        assert bolao.bolao is not None and len(bolao.bolao.bets) == 10
        bolao.view.save()
        assert services.storage.list_boloes("megasena")
        app.show_page("Estatísticas")
        _pump(app, 800)
        assert app.pages["Estatísticas"]._summary is not None
        from loterias.alerts import PrizeAlert
        from loterias.gui.toast import Toast
        from loterias.updater import SyncResult
        services.settings.notifications = False
        alert = PrizeAlert("megasena", 200, "jogo", "Teste", "6 acertos", 1000.0)
        app._game_synced(SyncResult("megasena"), [alert])
        assert len(Toast._stack) == 1
        Toast._stack[0].dismiss()
        assert Toast._stack == []
        app.set_game("supersete")
        _pump(app, 100)
        assert app.pages["Conferir"].picker._fixed
        app.set_appearance("dark")
        _pump(app, 200)
    finally:
        app.close()
