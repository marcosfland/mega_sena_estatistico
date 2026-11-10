"""Página "Gerador": cria jogos a partir das estratégias estatísticas."""

from __future__ import annotations

from tkinter import filedialog
from typing import TYPE_CHECKING

import customtkinter as ctk

from loterias.export import export_bets_csv
from loterias.formatting import brl
from loterias.generator import STRATEGIES, StrategyContext, generate_games, strategies_for
from loterias.gui import theme as t
from loterias.gui.page_base import Page
from loterias.gui.widgets import (BallStrip, Card, Notice, ghost_button, label, primary_button,
                                  recolor_primary, scrollable)
from loterias.models import Bet

if TYPE_CHECKING:
    from loterias.gui.app import App

MAX_GAMES_GUI = 100


class GeneratorPage(Page):
    """Gera, exibe, salva e exporta jogos."""

    title = "Gerador"

    def __init__(self, master: ctk.CTkBaseClass, app: "App") -> None:
        super().__init__(master, app)
        self._bets: list[Bet] = []
        self._strips: list[BallStrip] = []
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_controls()
        self._build_results()

    def _build_controls(self) -> None:
        """Cartão de parâmetros."""
        card = Card(self)
        card.grid(row=0, column=0, sticky="ew", pady=(0, t.GAP))
        card.grid_columnconfigure(3, weight=1)
        for col, text in enumerate(("Estratégia", "Dezenas por jogo", "Jogos")):
            label(card, text, 11, "bold", t.MUTED, height=14).grid(
                row=0, column=col, sticky="w", padx=(20 if col == 0 else 0, 12), pady=(16, 4))
        common = dict(height=36, corner_radius=t.RADIUS_SM, font=t.font(13),
                      fg_color=t.SURFACE_ALT, button_color=t.SURFACE_ALT,
                      button_hover_color=t.BORDER, text_color=t.TEXT,
                      dropdown_font=t.font(13))
        self.strategy_menu = ctk.CTkOptionMenu(card, width=210, values=["—"],
                                               command=lambda _v: self._describe(), **common)
        self.strategy_menu.grid(row=1, column=0, sticky="w", padx=(20, 12), pady=(0, 6))
        self.size_menu = ctk.CTkOptionMenu(card, width=120, values=["6"],
                                           command=lambda _v: self._update_cost_hint(), **common)
        self.size_menu.grid(row=1, column=1, sticky="w", padx=(0, 12), pady=(0, 6))
        self.count_entry = ctk.CTkEntry(card, width=80, height=36, corner_radius=t.RADIUS_SM,
                                        font=t.font(13), border_color=t.BORDER,
                                        fg_color=t.SURFACE_ALT, text_color=t.TEXT)
        self.count_entry.insert(0, "5")
        self.count_entry.grid(row=1, column=2, sticky="w", padx=(0, 12), pady=(0, 6))
        self.count_entry.bind("<KeyRelease>", lambda _e: self._update_cost_hint())
        self.count_entry.bind("<Return>", lambda _e: self.generate())
        self.generate_btn = primary_button(card, "Gerar jogos", self.generate, self.spec.color,
                                           width=140)
        self.generate_btn.grid(row=1, column=4, sticky="e", padx=20, pady=(0, 6))
        self.description = label(card, "", 12, color=t.MUTED, wraplength=640)
        self.description.grid(row=2, column=0, columnspan=4, sticky="w", padx=20, pady=(2, 16))
        self.cost_hint = label(card, "", 12, color=t.MUTED, anchor="e")
        self.cost_hint.grid(row=2, column=4, sticky="e", padx=20, pady=(2, 16))
        card.bind("<Configure>", lambda e: self.description.configure(
            wraplength=max(300, e.width - 260)))

    def _build_results(self) -> None:
        """Cartão com a lista de jogos e as ações."""
        card = Card(self)
        card.grid(row=1, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))
        head.grid_columnconfigure(0, weight=1)
        self.summary = label(head, "Nenhum jogo gerado ainda", 15, "bold")
        self.summary.grid(row=0, column=0, sticky="w")
        self.notice = Notice(head)
        self.notice.grid(row=1, column=0, columnspan=4, sticky="w", pady=(4, 0))
        self.actions = []
        for col, (text, cmd) in enumerate((("Salvar em Meus jogos", self.save),
                                           ("Copiar", self.copy), ("Exportar CSV", self.export)),
                                          start=1):
            button = ghost_button(head, text, cmd, height=32)
            button.grid(row=0, column=col, padx=(8, 0))
            self.actions.append(button)
        self.list_frame = scrollable(card)
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 12))
        self.list_frame.grid_columnconfigure(1, weight=1)
        self._set_actions_state("disabled")

    # ---------------------------------------------------------------- eventos
    def on_game_changed(self) -> None:
        """Ajusta estratégias, tamanhos e cores para a loteria."""
        spec = self.spec
        options = strategies_for(spec)
        self._labels = {s.label: s.key for s in options}
        current = self.strategy_menu.get()
        self.strategy_menu.configure(values=list(self._labels))
        self.strategy_menu.set(current if current in self._labels else options[0].label)
        self.size_menu.configure(values=[str(n) for n in spec.bet_sizes])
        self.size_menu.set(str(spec.bet_min))
        self.size_menu.configure(state="disabled" if spec.bet_min == spec.bet_max else "normal")
        recolor_primary(self.generate_btn, spec.color)
        self._describe()
        self._show([])
        self.notice.clear()

    def on_appearance_changed(self) -> None:
        """Redesenha as bolinhas com as cores do tema."""
        for strip in self._strips:
            strip.redraw()

    def _describe(self) -> None:
        """Mostra a explicação da estratégia escolhida."""
        key = self._labels.get(self.strategy_menu.get(), "aleatorio")
        self.description.configure(text=STRATEGIES[key].description)
        self._update_cost_hint()

    def _parse_count(self) -> int:
        """Lê e valida a quantidade de jogos.

        Raises:
            ValueError: Valor não numérico ou fora de 1–100.
        """
        raw = self.count_entry.get().strip()
        if not raw.isdigit() or not 1 <= int(raw) <= MAX_GAMES_GUI:
            raise ValueError(f"Informe de 1 a {MAX_GAMES_GUI} jogos.")
        return int(raw)

    def _update_cost_hint(self) -> None:
        """Prévia do custo total enquanto o usuário digita."""
        try:
            count = self._parse_count()
        except ValueError:
            self.cost_hint.configure(text="")
            return
        cost = self.spec.bet_cost(int(self.size_menu.get())) * count
        self.cost_hint.configure(text=f"Custo estimado {brl(cost)}")

    # ----------------------------------------------------------------- ações
    def generate(self) -> None:
        """Valida as entradas e gera os jogos em segundo plano."""
        try:
            count = self._parse_count()
        except ValueError as exc:
            self.notice.show(str(exc), "error")
            return
        draws = self.app.draws()
        if not draws:
            self.notice.show("A base está vazia. Clique em Atualizar na barra lateral.", "error")
            return
        spec, n_numbers = self.spec, int(self.size_menu.get())
        strategy = self._labels[self.strategy_menu.get()]
        self.generate_btn.configure(state="disabled", text="Gerando…")
        self.notice.show("Calculando estatísticas e gerando jogos…")

        def work() -> list[Bet]:
            ctx = StrategyContext.from_draws(spec, draws)
            return generate_games(spec, ctx, strategy, n_numbers, count)

        def done() -> None:
            self.generate_btn.configure(state="normal", text="Gerar jogos")

        self.app.runner.submit(work, on_success=self._show_generated, on_done=done,
                               on_error=lambda e: self.notice.show(str(e), "error"))

    def _show_generated(self, bets: list[Bet]) -> None:
        """Recebe os jogos da thread de trabalho."""
        self._show(bets)
        self.notice.show("Lembre: nenhuma estratégia aumenta a chance de acerto; "
                         "são formas diferentes de escolher.", "info")

    def _show(self, bets: list[Bet]) -> None:
        """Renderiza a lista de jogos."""
        for child in self.list_frame.winfo_children():
            child.destroy()
        self._bets, self._strips = bets, []
        if not bets:
            self.summary.configure(text="Nenhum jogo gerado ainda")
            self._set_actions_state("disabled")
            return
        spec = self.spec
        total = sum(spec.bet_cost(len(b.numbers), len(b.trevos) or 2) for b in bets)
        self.summary.configure(text=f"{len(bets)} jogo(s) · {brl(total)}")
        for row, bet in enumerate(bets):
            label(self.list_frame, f"{row + 1:02d}", 12, "bold", t.SUBTLE, width=34).grid(
                row=row, column=0, sticky="nw", padx=(12, 6), pady=8)
            strip = BallStrip(self.list_frame, bet.numbers, spec.color, square=bet.trevos)
            strip.grid(row=row, column=1, sticky="ew", pady=6)
            self._strips.append(strip)
            extra = f"{bet.extra}   " if bet.extra else ""
            label(self.list_frame, extra + brl(spec.bet_cost(len(bet.numbers),
                                                             len(bet.trevos) or 2)),
                  12, color=t.MUTED, anchor="e").grid(row=row, column=2, sticky="ne",
                                                      padx=(8, 12), pady=8)
        self._set_actions_state("normal")

    def _set_actions_state(self, state: str) -> None:
        """Habilita/desabilita os botões que dependem de jogos gerados."""
        for button in self.actions:
            button.configure(state=state)

    def save(self) -> None:
        """Salva os jogos em "Meus jogos" (aba Conferir)."""
        latest = self.app.services.storage.latest_contest(self.spec.slug)
        label_text = self.strategy_menu.get()
        storage, slug, bets = self.app.services.storage, self.spec.slug, list(self._bets)

        def work() -> int:
            for i, bet in enumerate(bets, start=1):
                storage.save_bet(slug, bet, f"{label_text} #{i}", latest + 1 if latest else None)
            return len(bets)

        self.app.runner.submit(work, on_success=lambda n: self.notice.show(
            f"{n} jogo(s) salvos. Confira na aba Conferir.", "ok"),
            on_error=lambda e: self.notice.show(f"Não foi possível salvar: {e}", "error"))

    def copy(self) -> None:
        """Copia os jogos como texto."""
        text = "\n".join(f"{i:02d}) {b.as_text()}" for i, b in enumerate(self._bets, start=1))
        self.clipboard_clear()
        self.clipboard_append(f"{self.spec.name}\n{text}")
        self.notice.show("Jogos copiados para a área de transferência.", "ok")

    def export(self) -> None:
        """Exporta os jogos para CSV."""
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile=f"jogos_{self.spec.slug}.csv")
        if not path:
            return
        spec, bets = self.spec, list(self._bets)
        self.app.runner.submit(export_bets_csv, spec, bets, path,
                               on_success=lambda p: self.notice.show(f"Exportado: {p}", "ok"),
                               on_error=lambda e: self.notice.show(
                                   f"Falha ao exportar: {e}", "error"))
