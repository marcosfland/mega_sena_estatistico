"""Página "Bolão": monta, salva, compartilha e confere bolões."""

from __future__ import annotations

from tkinter import filedialog
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from loterias import bolao as bl
from loterias.export import export_bets_csv
from loterias.formatting import brl
from loterias.generator import StrategyContext, strategies_for
from loterias.gui import theme as t
from loterias.gui.bolao_view import BolaoView
from loterias.gui.page_base import Page
from loterias.gui.widgets import (Card, Notice, ghost_button, label, primary_button,
                                  recolor_primary, scrollable)

if TYPE_CHECKING:
    from loterias.gui.app import App


def parse_money(text: str) -> float:
    """Converte ``"R$ 1.250,50"`` ou ``"1250.5"`` em número.

    Raises:
        ValueError: Texto vazio, inválido ou valor não positivo.
    """
    clean = text.replace("R$", "").strip()
    if "," in clean:
        clean = clean.replace(".", "").replace(",", ".")
    try:
        value = float(clean)
    except ValueError as exc:
        raise ValueError("Orçamento inválido. Ex.: 150 ou 150,00") from exc
    if value <= 0 or value > 1_000_000:
        raise ValueError("O orçamento deve ficar entre R$ 0,01 e R$ 1.000.000.")
    return value


class BolaoPage(Page):
    """Formulário à esquerda e bolão montado à direita."""

    title = "Bolão"

    def __init__(self, master: ctk.CTkBaseClass, app: "App") -> None:
        super().__init__(master, app)
        self.bolao: Optional[bl.Bolao] = None
        self._saved: dict[str, int] = {}
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_form()
        self.view = BolaoView(self, app, self.notice, on_saved=self.refresh_saved,
                              on_export=self.export)
        self.view.grid(row=0, column=1, sticky="nsew")

    def _field(self, form: ctk.CTkFrame, row: int, text: str) -> int:
        """Rótulo de campo; devolve a linha do controle."""
        label(form, text, 11, "bold", t.MUTED, height=14).grid(
            row=row, column=0, sticky="w", padx=14, pady=(12, 4))
        return row + 1

    def _build_form(self) -> None:
        """Campos do bolão e bolões salvos."""
        card = Card(self, width=330)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, t.GAP))
        card.grid_propagate(False)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(0, weight=1)
        form = scrollable(card)
        form.grid(row=0, column=0, sticky="nsew", padx=2, pady=6)
        form.grid_columnconfigure(0, weight=1)
        label(form, "Novo bolão", 15, "bold").grid(row=0, column=0, sticky="w", padx=14,
                                                    pady=(16, 0))
        entry = dict(height=34, font=t.font(13), fg_color=t.SURFACE_ALT,
                     border_color=t.BORDER, corner_radius=t.RADIUS_SM)
        menu = dict(height=34, font=t.font(13), fg_color=t.SURFACE_ALT,
                    button_color=t.SURFACE_ALT, button_hover_color=t.BORDER, text_color=t.TEXT,
                    corner_radius=t.RADIUS_SM)
        row = self._field(form, 1, "Nome")
        self.name_entry = ctk.CTkEntry(form, placeholder_text="ex.: Firma", **entry)
        self.name_entry.grid(row=row, column=0, sticky="ew", padx=14)
        row = self._field(form, row + 1, "Orçamento total (R$)")
        self.budget_entry = ctk.CTkEntry(form, placeholder_text="ex.: 300", **entry)
        self.budget_entry.grid(row=row, column=0, sticky="ew", padx=14)
        self.budget_entry.bind("<KeyRelease>", lambda _e: self._preview())
        row = self._field(form, row + 1, "Dezenas por jogo  ·  Estratégia")
        pair = ctk.CTkFrame(form, fg_color="transparent")
        pair.grid(row=row, column=0, sticky="ew", padx=14)
        pair.grid_columnconfigure(1, weight=1)
        self.size_menu = ctk.CTkOptionMenu(pair, width=80, values=["6"],
                                           command=lambda _v: self._preview(), **menu)
        self.size_menu.grid(row=0, column=0, padx=(0, 8))
        self.strategy_menu = ctk.CTkOptionMenu(pair, values=["—"], **menu)
        self.strategy_menu.grid(row=0, column=1, sticky="ew")
        row = self._field(form, row + 1, "Participantes  (um por linha: Nome, cotas)")
        self.people = ctk.CTkTextbox(form, height=130, font=t.font(13), fg_color=t.SURFACE_ALT,
                                     border_color=t.BORDER, border_width=1,
                                     corner_radius=t.RADIUS_SM)
        self.people.insert("1.0", "Ana, 2\nBruno\nCarla, 1")
        self.people.grid(row=row, column=0, sticky="ew", padx=14)
        self.people.bind("<KeyRelease>", lambda _e: self._preview())
        self.plan_label = label(form, "", 12, color=t.MUTED, wraplength=270)
        self.plan_label.grid(row=row + 1, column=0, sticky="w", padx=14, pady=(10, 0))
        self.build_btn = primary_button(form, "Montar bolão", self.build, self.spec.color)
        self.build_btn.grid(row=row + 2, column=0, sticky="ew", padx=14, pady=(10, 4))
        self.notice = Notice(form, wraplength=270)
        self.notice.grid(row=row + 3, column=0, sticky="w", padx=14)
        label(form, "Bolões salvos", 11, "bold", t.MUTED, height=14).grid(
            row=row + 5, column=0, sticky="w", padx=14, pady=(8, 4))
        saved = ctk.CTkFrame(form, fg_color="transparent")
        saved.grid(row=row + 6, column=0, sticky="ew", padx=14, pady=(0, 18))
        saved.grid_columnconfigure(0, weight=1)
        self.saved_menu = ctk.CTkOptionMenu(saved, values=["—"], **menu)
        self.saved_menu.grid(row=0, column=0, sticky="ew")
        ghost_button(saved, "Abrir", self.open_saved, width=64, height=34).grid(
            row=0, column=1, padx=(6, 0))
        ghost_button(saved, "Excluir", self.delete_saved, width=64, height=34).grid(
            row=0, column=2, padx=(6, 0))

    # ---------------------------------------------------------------- eventos
    def on_game_changed(self) -> None:
        """Ajusta opções para a loteria e limpa o bolão aberto."""
        spec = self.spec
        self.size_menu.configure(values=[str(n) for n in spec.bet_sizes],
                                 state="disabled" if spec.bet_min == spec.bet_max else "normal")
        self.size_menu.set(str(spec.bet_min))
        options = strategies_for(spec)
        self._strategies = {s.label: s.key for s in options}
        self.strategy_menu.configure(values=list(self._strategies))
        self.strategy_menu.set(next((s.label for s in options if s.key == "equilibrado"),
                                    options[0].label))
        recolor_primary(self.build_btn, spec.color)
        self.bolao = None
        self.view.show(None)
        self.notice.clear()
        self._preview()
        self.refresh_saved()

    def on_appearance_changed(self) -> None:
        """Redesenha as bolinhas."""
        self.view.redraw()

    # ---------------------------------------------------------------- ações
    def _preview(self) -> None:
        """Mostra quantos jogos cabem enquanto o usuário digita."""
        try:
            plan = bl.plan_budget(self.spec, parse_money(self.budget_entry.get()),
                                  int(self.size_menu.get()))
            people = bl.parse_participants(self.people.get("1.0", "end"))
        except ValueError as exc:
            self.plan_label.configure(text=str(exc) if self.budget_entry.get().strip() else
                                      f"Cada jogo de {self.size_menu.get()} dezenas custa "
                                      f"{brl(self.spec.bet_cost(int(self.size_menu.get())))}.")
            return
        cotas = sum(p.cotas for p in people)
        self.plan_label.configure(
            text=f"{plan.n_bets} jogo(s) de {brl(plan.cost_per_bet)} = {brl(plan.total)}"
                 f" · sobra {brl(plan.leftover)}\n{cotas} cota(s) de "
                 f"{brl(plan.total / cotas)} cada")

    def build(self) -> None:
        """Valida o formulário e gera o bolão em segundo plano."""
        try:
            budget = parse_money(self.budget_entry.get())
            people = bl.parse_participants(self.people.get("1.0", "end"))
            name = self.name_entry.get().strip() or "dos Amigos"
            n_numbers = int(self.size_menu.get())
            bl.plan_budget(self.spec, budget, n_numbers)
        except ValueError as exc:
            self.notice.show(str(exc), "error")
            return
        draws = self.app.draws()
        if not draws:
            self.notice.show("Base vazia. Use Atualizar na barra lateral.", "error")
            return
        spec, strategy = self.spec, self._strategies[self.strategy_menu.get()]
        target = draws[-1].contest + 1
        self.build_btn.configure(state="disabled", text="Montando…")

        def work() -> bl.Bolao:
            ctx = StrategyContext.from_draws(spec, draws)
            return bl.create_bolao(spec, ctx, name, budget, n_numbers, people, strategy,
                                   target_contest=target)

        def ok(bolao: bl.Bolao) -> None:
            self.bolao = bolao
            self.view.show(bolao)
            self.notice.show("Bolão montado. Salve para conferir depois do sorteio.", "ok")

        self.app.runner.submit(work, on_success=ok,
                               on_error=lambda e: self.notice.show(str(e), "error"),
                               on_done=lambda: self.build_btn.configure(state="normal",
                                                                        text="Montar bolão"))

    def refresh_saved(self) -> None:
        """Recarrega a lista de bolões salvos."""
        items = self.app.services.storage.list_boloes(self.spec.slug)
        self._saved = {f"{name}  ·  {updated[:10]}": bid for bid, name, updated in items}
        values = list(self._saved) or ["Nenhum salvo"]
        self.saved_menu.configure(values=values)
        self.saved_menu.set(values[0])

    def open_saved(self) -> None:
        """Abre o bolão escolhido."""
        bid = self._saved.get(self.saved_menu.get())
        if bid is None:
            return
        data = self.app.services.storage.load_bolao(bid)
        if data is None:
            self.notice.show("Bolão não encontrado.", "error")
            self.refresh_saved()
            return
        self.bolao = bl.Bolao.from_dict(data, bid)
        self.view.show(self.bolao)
        self.notice.show(f"Bolão '{self.bolao.name}' aberto.", "ok")

    def delete_saved(self) -> None:
        """Exclui o bolão escolhido."""
        bid = self._saved.get(self.saved_menu.get())
        if bid is None:
            return
        self.app.services.storage.delete_bolao(bid)
        if self.bolao and self.bolao.id == bid:
            self.bolao = None
            self.view.show(None)
        self.notice.show("Bolão excluído.", "ok")
        self.refresh_saved()

    def export(self) -> None:
        """Exporta os jogos do bolão para CSV."""
        if not self.bolao:
            return
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile=f"bolao_{self.bolao.name}.csv")
        if path:
            self.app.runner.submit(export_bets_csv, self.spec, list(self.bolao.bets), path,
                                   on_success=lambda p: self.notice.show(f"Exportado: {p}", "ok"),
                                   on_error=lambda e: self.notice.show(str(e), "error"))
