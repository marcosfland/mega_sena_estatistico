"""Página "Backtest": compara as estratégias nos concursos passados."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from loterias.backtest import BacktestResult, expected_hits, run_backtest
from loterias.formatting import brl
from loterias.generator import strategies_for
from loterias.gui import theme as t
from loterias.gui.page_base import Page
from loterias.gui.widgets import (Card, Notice, ghost_button, label, primary_button,
                                  recolor_primary, scrollable)

if TYPE_CHECKING:
    from loterias.gui.app import App

COLUMNS = ("Estratégia", "Média de acertos", "vs. acaso", "Premiado em", "Gasto", "Retorno")


class BacktestPage(Page):
    """Executa o backtest walk-forward com progresso e cancelamento."""

    title = "Backtest"

    def __init__(self, master: ctk.CTkBaseClass, app: "App") -> None:
        super().__init__(master, app)
        self._cancel: Optional[threading.Event] = None
        self._checks: dict[str, ctk.CTkCheckBox] = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_controls()
        self._build_results()

    def _build_controls(self) -> None:
        """Parâmetros, estratégias e botões."""
        card = Card(self)
        card.grid(row=0, column=0, sticky="ew", pady=(0, t.GAP))
        card.grid_columnconfigure(3, weight=1)
        label(card, "Concursos testados", 11, "bold", t.MUTED, height=14).grid(
            row=0, column=0, sticky="w", padx=(20, 12), pady=(16, 4))
        label(card, "Dezenas por jogo", 11, "bold", t.MUTED, height=14).grid(
            row=0, column=1, sticky="w", padx=(0, 12), pady=(16, 4))
        self.contests = ctk.CTkEntry(card, width=110, height=36, font=t.font(13),
                                     fg_color=t.SURFACE_ALT, border_color=t.BORDER,
                                     corner_radius=t.RADIUS_SM)
        self.contests.insert(0, "300")
        self.contests.grid(row=1, column=0, sticky="w", padx=(20, 12))
        self.size_menu = ctk.CTkOptionMenu(card, width=100, height=36, values=["6"],
                                           font=t.font(13), fg_color=t.SURFACE_ALT,
                                           button_color=t.SURFACE_ALT, text_color=t.TEXT,
                                           button_hover_color=t.BORDER,
                                           corner_radius=t.RADIUS_SM)
        self.size_menu.grid(row=1, column=1, sticky="w", padx=(0, 12))
        self.run_btn = primary_button(card, "Executar", self.run, self.spec.color, width=120)
        self.run_btn.grid(row=1, column=4, padx=(0, 8))
        self.cancel_btn = ghost_button(card, "Cancelar", self.cancel, width=100)
        self.cancel_btn.grid(row=1, column=5, padx=(0, 20))
        self.cancel_btn.configure(state="disabled")
        self.checks_box = ctk.CTkFrame(card, fg_color="transparent")
        self.checks_box.grid(row=2, column=0, columnspan=6, sticky="w", padx=16, pady=(12, 4))
        self.progress = ctk.CTkProgressBar(card, height=4, corner_radius=2, fg_color=t.BORDER)
        self.progress.set(0)
        self.progress.grid(row=3, column=0, columnspan=6, sticky="ew", padx=20, pady=(8, 4))
        self.notice = Notice(card)
        self.notice.grid(row=4, column=0, columnspan=6, sticky="w", padx=20, pady=(0, 14))

    def _build_results(self) -> None:
        """Tabela de resultados."""
        card = Card(self)
        card.grid(row=1, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)
        self.explain = label(card, "Cada estratégia joga os concursos passados usando só o "
                                   "histórico anterior a cada sorteio, como se fosse ao vivo.",
                             12, color=t.MUTED, wraplength=760)
        self.explain.grid(row=0, column=0, sticky="w", padx=20, pady=(16, 8))
        card.bind("<Configure>", lambda e: self.explain.configure(wraplength=e.width - 60))
        self.table = scrollable(card)
        self.table.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 12))
        for col in range(len(COLUMNS)):
            self.table.grid_columnconfigure(col, weight=2 if col == 0 else 1)

    # ---------------------------------------------------------------- eventos
    def on_game_changed(self) -> None:
        """Recria a lista de estratégias e as opções de tamanho."""
        spec = self.spec
        for box in self._checks.values():
            box.destroy()
        self._checks.clear()
        for strategy in strategies_for(spec):
            box = ctk.CTkCheckBox(self.checks_box, text=strategy.label, font=t.font(12),
                                  checkbox_width=18, checkbox_height=18, corner_radius=5,
                                  fg_color=t.accent(spec.color), border_color=t.SUBTLE,
                                  text_color=t.TEXT)
            box.select()
            box.pack(side="left", padx=(4, 14))
            self._checks[strategy.key] = box
        self.size_menu.configure(values=[str(n) for n in spec.bet_sizes],
                                 state="disabled" if spec.bet_min == spec.bet_max else "normal")
        self.size_menu.set(str(spec.bet_min))
        recolor_primary(self.run_btn, spec.color)
        self.progress.configure(progress_color=t.accent(spec.color))
        self._render([], 0.0)
        self.notice.clear()

    # ----------------------------------------------------------------- ações
    def run(self) -> None:
        """Valida e executa em segundo plano."""
        raw = self.contests.get().strip()
        if not raw.isdigit() or not 10 <= int(raw) <= 2000:
            self.notice.show("Informe entre 10 e 2000 concursos.", "error")
            return
        chosen = [key for key, box in self._checks.items() if box.get()]
        if not chosen:
            self.notice.show("Marque ao menos uma estratégia.", "error")
            return
        spec, draws = self.spec, self.app.draws()
        n_contests, n_numbers = int(raw), int(self.size_menu.get())
        if len(draws) < n_contests + 30:
            self.notice.show(f"Histórico insuficiente: há {len(draws)} concursos na base; "
                             f"reduza para no máximo {max(len(draws) - 30, 0)} ou atualize.",
                             "error")
            return
        self._cancel = threading.Event()
        cancel = self._cancel
        self.run_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.progress.set(0)
        self.notice.show("Executando…")

        def work(progress: object) -> list[BacktestResult]:
            return run_backtest(spec, draws, chosen, n_contests, n_numbers,
                                progress=progress, cancel=cancel)

        def on_progress(done: int, total: int) -> None:
            self.progress.set(done / total)
            self.notice.show(f"Concurso {done} de {total}…")

        def done() -> None:
            self.run_btn.configure(state="normal")
            self.cancel_btn.configure(state="disabled")

        self.app.runner.submit(
            work, with_progress=True, on_progress=on_progress, on_done=done,
            on_success=lambda r: self._finish(r, expected_hits(spec, n_numbers)),
            on_error=lambda e: self.notice.show(str(e), "error"))

    def cancel(self) -> None:
        """Interrompe o backtest em andamento."""
        if self._cancel:
            self._cancel.set()
            self.notice.show("Cancelando…")

    def _finish(self, results: list[BacktestResult], expected: float) -> None:
        """Exibe os resultados finais."""
        self._render(results, expected)
        if results:
            n = results[0].contests
            self.notice.show(f"{n} concursos testados. Média esperada por puro acaso: "
                             f"{expected:.3f} acertos por jogo.", "ok")

    def _render(self, results: list[BacktestResult], expected: float) -> None:
        """Desenha a tabela."""
        for child in self.table.winfo_children():
            child.destroy()
        if not results:
            return
        for col, title in enumerate(COLUMNS):
            label(self.table, title.upper(), 10, "bold", t.SUBTLE,
                  anchor="w" if col == 0 else "e").grid(row=0, column=col, sticky="ew",
                                                        padx=12, pady=(4, 8))
        best = max(results, key=lambda r: r.mean_hits)
        for row, r in enumerate(results, start=1):
            delta = (r.mean_hits / expected - 1) * 100 if expected else 0.0
            values = (r.label, f"{r.mean_hits:.3f}", f"{delta:+.1f}%",
                      f"{r.wins} ({r.win_rate:.1%})", brl(r.spent),
                      brl(r.won) + (" *" if r.unknown_prizes else ""))
            for col, value in enumerate(values):
                strong = col == 1 and r is best
                label(self.table, value, 13, "bold" if strong or col == 0 else "normal",
                      t.accent(self.spec.color) if strong else t.TEXT,
                      anchor="w" if col == 0 else "e").grid(row=row, column=col, sticky="ew",
                                                            padx=12, pady=6)
        footer = ("Diferenças de poucos % entre estratégias são normais em amostras desse "
                  "tamanho e mudam a cada execução; o acaso explica todas elas.")
        if any(r.unknown_prizes for r in results):
            footer += "  * Há prêmios sem valor de rateio na base (concursos antigos)."
        label(self.table, footer, 11, color=t.MUTED, wraplength=700).grid(
            row=len(results) + 1, column=0, columnspan=len(COLUMNS), sticky="w", padx=12,
            pady=(12, 4))
