"""Página "Conferir": confere uma aposta e lista os jogos salvos."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from loterias.checker import CheckResult, check_bet
from loterias.formatting import brl, date_br
from loterias.gui import theme as t
from loterias.gui.page_base import Page
from loterias.gui.widgets import (BallStrip, Card, Notice, NumberPicker, ghost_button, label,
                                  primary_button, recolor_primary, scrollable)
from loterias.models import Bet, Draw, SavedBet

if TYPE_CHECKING:
    from loterias.gui.app import App

NO_EXTRA = "(sem escolha)"


def prize_text(result: CheckResult) -> str:
    """Frase do prêmio para exibição."""
    if not result.won:
        return "Sem prêmio neste concurso."
    if result.prize_pending and not result.total_prize:
        return "Premiado! O valor do rateio não está disponível para este concurso."
    return f"Premiado: {brl(result.total_prize)}"


class CheckerPage(Page):
    """Conferência manual e "Meus jogos"."""

    title = "Conferir"

    def __init__(self, master: ctk.CTkBaseClass, app: "App") -> None:
        super().__init__(master, app)
        self._strips: list[BallStrip] = []
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)
        self._build_bet_card()
        self._build_saved_card()

    def _build_bet_card(self) -> None:
        """Cartão de entrada da aposta e do resultado."""
        card = Card(self)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, t.GAP))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(0, weight=1)
        body = scrollable(card)
        body.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        body.grid_columnconfigure(0, weight=1)
        head = ctk.CTkFrame(body, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 4))
        head.grid_columnconfigure(0, weight=1)
        label(head, "Sua aposta", 15, "bold").grid(row=0, column=0, sticky="w")
        self.counter = label(head, "", 12, color=t.MUTED)
        self.counter.grid(row=1, column=0, sticky="w")
        ghost_button(head, "Limpar", self._clear, width=72, height=30).grid(
            row=0, column=1, rowspan=2, padx=(6, 0))
        ghost_button(head, "Salvar", self._save, width=72, height=30).grid(
            row=0, column=2, rowspan=2, padx=(6, 0))
        body.bind("<Configure>", lambda e: self.picker.reflow(e.width - 40))
        self.picker = NumberPicker(body, on_change=self._on_pick)
        self.picker.grid(row=1, column=0, sticky="w", padx=10, pady=4)
        self.trevo_title = label(body, "Trevos", 12, "bold", t.MUTED)
        self.trevo_picker = NumberPicker(body, on_change=lambda _s: self._on_pick(None))
        self.extra_menu = ctk.CTkOptionMenu(body, values=[NO_EXTRA], height=32, width=200,
                                            font=t.font(12), fg_color=t.SURFACE_ALT,
                                            button_color=t.SURFACE_ALT, text_color=t.TEXT,
                                            button_hover_color=t.BORDER)
        self.extra_entry = ctk.CTkEntry(body, height=32, width=260, font=t.font(12),
                                        placeholder_text="Time do Coração (opcional)",
                                        fg_color=t.SURFACE_ALT, border_color=t.BORDER)
        controls = ctk.CTkFrame(body, fg_color="transparent")
        controls.grid(row=5, column=0, sticky="ew", padx=12, pady=(10, 4))
        label(controls, "Concurso", 12, color=t.MUTED).pack(side="left")
        self.contest_entry = ctk.CTkEntry(controls, width=90, height=34, font=t.font(13),
                                          placeholder_text="último", fg_color=t.SURFACE_ALT,
                                          border_color=t.BORDER, corner_radius=t.RADIUS_SM)
        self.contest_entry.pack(side="left", padx=(8, 16))
        self.contest_entry.bind("<Return>", lambda _e: self.check())
        self.check_btn = primary_button(controls, "Conferir", self.check, self.spec.color,
                                        width=120)
        self.check_btn.pack(side="left")
        self.notice = Notice(body)
        self.notice.grid(row=6, column=0, sticky="w", padx=12, pady=(4, 0))
        self.result_box = ctk.CTkFrame(body, fg_color=t.SURFACE_ALT, corner_radius=t.RADIUS)
        self.result_box.grid_columnconfigure(0, weight=1)

    def _build_saved_card(self) -> None:
        """Cartão "Meus jogos"."""
        card = Card(self, width=320)
        card.grid(row=0, column=1, sticky="nsew")
        card.grid_propagate(False)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(2, weight=1)
        label(card, "Meus jogos", 15, "bold").grid(row=0, column=0, sticky="w", padx=20,
                                                    pady=(16, 0))
        self.saved_caption = label(card, "", 12, color=t.MUTED, wraplength=280)
        self.saved_caption.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 8))
        self.saved_list = scrollable(card)
        self.saved_list.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 12))
        self.saved_list.grid_columnconfigure(0, weight=1)

    # ---------------------------------------------------------------- eventos
    def on_game_changed(self) -> None:
        """Recria a grade de dezenas e a lista salva para a loteria."""
        spec = self.spec
        if spec.is_columns:
            self.picker.configure_numbers(
                spec.numbers, spec.bet_max, spec.color, columns=10,
                labeler=lambda code: str(code % 10), fixed=True,
                row_labels=[f"Col {i}" for i in range(1, spec.columns + 1)])
        else:
            self.picker.configure_numbers(spec.numbers, spec.bet_max, spec.color)
        for widget in (self.trevo_title, self.trevo_picker, self.extra_menu, self.extra_entry):
            widget.grid_forget()
        if spec.has_trevos:
            self.trevo_title.grid(row=2, column=0, sticky="w", padx=12, pady=(8, 0))
            self.trevo_picker.configure_numbers(range(1, spec.trevo_max + 1),
                                                spec.trevo_bet_max, spec.color, columns=6)
            self.trevo_picker.grid(row=3, column=0, sticky="w", padx=10)
        if spec.extra_options:
            self.extra_menu.configure(values=[NO_EXTRA, *spec.extra_options])
            self.extra_menu.set(NO_EXTRA)
            self.extra_menu.grid(row=4, column=0, sticky="w", padx=12, pady=(8, 0))
        elif spec.extra_name:
            self.extra_entry.delete(0, "end")
            self.extra_entry.grid(row=4, column=0, sticky="w", padx=12, pady=(8, 0))
        recolor_primary(self.check_btn, spec.color)
        self.contest_entry.delete(0, "end")
        self.result_box.grid_forget()
        self.notice.clear()
        self._on_pick(None)
        self.refresh_saved()

    def on_data_changed(self) -> None:
        """Novo concurso: reconfere os jogos salvos."""
        self.refresh_saved()

    def on_appearance_changed(self) -> None:
        """Redesenha bolinhas."""
        for strip in self._strips:
            if strip.winfo_exists():
                strip.redraw()

    def _on_pick(self, _selected: Optional[list[int]]) -> None:
        """Atualiza o contador e o custo da aposta marcada."""
        spec, n = self.spec, len(self.picker.selected)
        if spec.is_columns:
            try:
                numbers = spec.validate_numbers(self.picker.selected)
                text = f"{n} números · {brl(spec.cost_of(numbers))}"
            except ValueError:
                text = f"{n} marcados · 1 a 3 números em cada uma das 7 colunas"
            self.counter.configure(text=text)
            return
        text = f"{n} de {spec.bet_min}" + (f"–{spec.bet_max}" if spec.bet_max != spec.bet_min
                                            else "") + " dezenas"
        if spec.bet_min <= n <= spec.bet_max:
            trevos = len(self.trevo_picker.selected) if spec.has_trevos else 2
            try:
                text += f" · {brl(spec.bet_cost(n, trevos))}"
            except ValueError:
                text += f" · marque de {spec.trevo_draw} a {spec.trevo_bet_max} trevos"
        self.counter.configure(text=text)

    # ----------------------------------------------------------------- ações
    def _read_bet(self) -> Bet:
        """Monta a aposta a partir das seleções (validando)."""
        spec = self.spec
        numbers = spec.validate_numbers(self.picker.selected)
        trevos = spec.validate_trevos(self.trevo_picker.selected) if spec.has_trevos else ()
        extra = ""
        if spec.extra_options and self.extra_menu.get() != NO_EXTRA:
            extra = self.extra_menu.get()
        elif spec.extra_name and not spec.extra_options:
            extra = self.extra_entry.get().strip().upper()
        return Bet(numbers, trevos, extra)

    def _read_draw(self) -> Draw:
        """Concurso escolhido (ou o último).

        Raises:
            ValueError: Número inválido ou concurso ausente da base.
        """
        raw = self.contest_entry.get().strip()
        storage = self.app.services.storage
        if not raw:
            draw = storage.latest_draw(self.spec.slug)
            if draw is None:
                raise ValueError("Base vazia. Use Atualizar na barra lateral.")
            return draw
        if not raw.isdigit():
            raise ValueError("Concurso deve ser um número.")
        draw = storage.get_draw(self.spec.slug, int(raw))
        if draw is None:
            raise ValueError(f"Concurso {raw} não está na base. Atualize ou confira o número.")
        return draw

    def check(self) -> None:
        """Confere a aposta marcada."""
        try:
            bet, draw = self._read_bet(), self._read_draw()
        except ValueError as exc:
            self.notice.show(str(exc), "error")
            return
        self.notice.clear()
        self._show_result(bet, draw, check_bet(self.spec, bet, draw))

    def _show_result(self, bet: Bet, draw: Draw, result: CheckResult) -> None:
        """Mostra o resultado oficial com os acertos destacados."""
        box = self.result_box
        for child in box.winfo_children():
            child.destroy()
        box.grid(row=7, column=0, sticky="ew", padx=12, pady=(12, 8))
        label(box, f"Concurso {draw.contest} · {date_br(draw.date)}", 12, "bold",
              t.MUTED).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 6))
        row = 1
        for numbers in draw.number_sets():
            strip = BallStrip(box, numbers, self.spec.color, highlight=bet.numbers,
                              bg=t.SURFACE_ALT, square=draw.trevos if row == 1 else (),
                              fmt=self.spec.format_number)
            strip.grid(row=row, column=0, sticky="ew", padx=16, pady=2)
            self._strips.append(strip)
            row += 1
        if draw.extra:
            label(box, f"{self.spec.extra_name}: {draw.extra}", 12, color=t.MUTED).grid(
                row=row, column=0, sticky="w", padx=16)
            row += 1
        label(box, result.summary(), 14, "bold",
              t.accent(self.spec.color) if result.won else t.TEXT, wraplength=520).grid(
            row=row, column=0, sticky="w", padx=16, pady=(8, 0))
        label(box, prize_text(result), 12, color=t.MUTED).grid(
            row=row + 1, column=0, sticky="w", padx=16, pady=(0, 14))

    def _clear(self) -> None:
        """Limpa as seleções."""
        self.picker.clear()
        self.trevo_picker.clear()
        self.result_box.grid_forget()
        self.notice.clear()

    def _save(self) -> None:
        """Salva a aposta marcada em "Meus jogos"."""
        try:
            bet = self._read_bet()
        except ValueError as exc:
            self.notice.show(str(exc), "error")
            return
        storage = self.app.services.storage
        storage.save_bet(self.spec.slug, bet, "Manual", storage.latest_contest(self.spec.slug) + 1)
        self.notice.show("Aposta salva em Meus jogos.", "ok")
        self.refresh_saved()

    def refresh_saved(self) -> None:
        """Lista os jogos salvos conferidos contra o último concurso."""
        for child in self.saved_list.winfo_children():
            child.destroy()
        self._strips = [s for s in self._strips if s.winfo_exists()]
        storage = self.app.services.storage
        saved = storage.list_bets(self.spec.slug)
        latest = storage.latest_draw(self.spec.slug)
        if not saved:
            self.saved_caption.configure(text="Salve jogos aqui ou na aba Gerador para "
                                              "conferi-los a cada concurso.")
            return
        self.saved_caption.configure(
            text=f"{len(saved)} jogo(s) · conferidos com o concurso {latest.contest}"
            if latest else f"{len(saved)} jogo(s)")
        for row, item in enumerate(saved):
            self._saved_row(row, item, latest)

    def _saved_row(self, row: int, item: SavedBet, latest: Optional[Draw]) -> None:
        """Uma linha de "Meus jogos"."""
        box = ctk.CTkFrame(self.saved_list, fg_color=t.SURFACE_ALT, corner_radius=t.RADIUS_SM)
        box.grid(row=row, column=0, sticky="ew", padx=4, pady=4)
        box.grid_columnconfigure(0, weight=1)
        result = check_bet(self.spec, item.bet, latest) if latest else None
        hits = {n for numbers in (result.matched if result else []) for n in numbers}
        label(box, item.label, 12, "bold").grid(row=0, column=0, sticky="w", padx=12,
                                                pady=(8, 2))
        ctk.CTkButton(box, text="✕", width=28, height=24, fg_color="transparent",
                      hover_color=t.BORDER, text_color=t.MUTED, font=t.font(12),
                      command=lambda i=item.id: self._delete(i)).grid(row=0, column=1, padx=6)
        strip = BallStrip(box, item.bet.numbers, self.spec.color, highlight=hits, size=26,
                          bg=t.SURFACE_ALT, square=item.bet.trevos,
                          fmt=self.spec.format_number)
        strip.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12)
        self._strips.append(strip)
        if result:
            label(box, result.summary(), 11,
                  color=t.accent(self.spec.color) if result.won else t.MUTED,
                  wraplength=260).grid(row=2, column=0, columnspan=2, sticky="w", padx=12,
                                       pady=(2, 8))

    def _delete(self, bet_id: int) -> None:
        """Remove um jogo salvo."""
        self.app.services.storage.delete_bet(bet_id)
        self.refresh_saved()
