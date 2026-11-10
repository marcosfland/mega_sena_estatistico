"""Painel que exibe um bolão montado: cotas, pagamentos, jogos e conferência."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

import customtkinter as ctk

from loterias import bolao as bl
from loterias.formatting import brl
from loterias.gui import theme as t
from loterias.gui.widgets import BallStrip, Card, Notice, ghost_button, label, scrollable

if TYPE_CHECKING:
    from loterias.gui.app import App


class BolaoView(Card):
    """Exibe e opera sobre o bolão aberto.

    Args:
        master: Página do bolão.
        app: Controlador do app.
        notice: Linha de aviso compartilhada com o formulário.
        on_saved: Chamado após salvar (para atualizar a lista).
        on_export: Abre o diálogo de exportação.
    """

    def __init__(self, master: ctk.CTkBaseClass, app: "App", notice: Notice,
                 on_saved: Callable[[], None], on_export: Callable[[], None]) -> None:
        super().__init__(master)
        self.app = app
        self.notice = notice
        self._on_saved = on_saved
        self._on_export = on_export
        self.bolao: Optional[bl.Bolao] = None
        self._strips: list[BallStrip] = []
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 4))
        head.grid_columnconfigure(0, weight=1)
        self.title = label(head, "Monte um bolão ao lado", 15, "bold")
        self.title.grid(row=0, column=0, sticky="w")
        self.subtitle = label(head, "Os jogos são diversificados para cobrir o máximo de "
                                    "dezenas diferentes com o orçamento.", 12, color=t.MUTED,
                              wraplength=520)
        self.subtitle.grid(row=1, column=0, sticky="w")
        self.bind("<Configure>", lambda e: self.subtitle.configure(wraplength=e.width - 50))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=20, pady=(4, 8))
        bar.grid_columnconfigure((0, 1, 2), weight=1, uniform="actions")
        self.buttons = [ghost_button(bar, text, cmd, height=32, width=60) for text, cmd in (
            ("Salvar", self.save), ("Copiar texto", self.copy),
            ("Exportar CSV", on_export))]
        for col, button in enumerate(self.buttons):
            button.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 6, 0))
        check_row = ctk.CTkFrame(bar, fg_color="transparent")
        check_row.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))
        label(check_row, "Conferir com o concurso", 12, color=t.MUTED).pack(side="left")
        self.contest_entry = ctk.CTkEntry(check_row, width=84, height=32,
                                          placeholder_text="último", font=t.font(12),
                                          fg_color=t.SURFACE_ALT, border_color=t.BORDER,
                                          corner_radius=t.RADIUS_SM)
        self.contest_entry.pack(side="left", padx=8)
        self.check_btn = ghost_button(check_row, "Conferir", self.check, height=32, width=90)
        self.check_btn.pack(side="left")
        self.buttons.append(self.check_btn)
        self.body = scrollable(self)
        self.body.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 12))
        self.body.grid_columnconfigure(0, weight=1)
        self._set_enabled(False)

    def _set_enabled(self, enabled: bool) -> None:
        """Habilita as ações só quando há bolão aberto."""
        for button in self.buttons:
            button.configure(state="normal" if enabled else "disabled")
        self.contest_entry.configure(state="normal" if enabled else "disabled")

    def redraw(self) -> None:
        """Redesenha bolinhas (troca de tema)."""
        for strip in self._strips:
            if strip.winfo_exists():
                strip.redraw()

    def show(self, bolao: Optional[bl.Bolao]) -> None:
        """Renderiza o bolão (ou o estado vazio)."""
        self.bolao = bolao
        for child in self.body.winfo_children():
            child.destroy()
        self._strips = []
        self._set_enabled(bolao is not None)
        if bolao is None:
            self.title.configure(text="Monte um bolão ao lado")
            return
        spec = self.app.spec
        self.title.configure(text=f"Bolão {bolao.name}")
        target = f" · concurso {bolao.target_contest}" if bolao.target_contest else ""
        self.subtitle.configure(
            text=f"{len(bolao.bets)} jogo(s) de {bolao.n_numbers} dezenas · "
                 f"{brl(bolao.total_cost(spec))} · {bolao.total_cotas} cota(s) de "
                 f"{brl(bolao.cota_value(spec))}{target}")
        self.contest_entry.delete(0, "end")
        if bolao.target_contest:
            self.contest_entry.insert(0, str(bolao.target_contest))
        row = self._participants(0)
        label(self.body, "JOGOS", 10, "bold", t.SUBTLE, height=14).grid(
            row=row, column=0, sticky="w", padx=12, pady=(16, 4))
        for i, bet in enumerate(bolao.bets, start=row + 1):
            line = ctk.CTkFrame(self.body, fg_color="transparent")
            line.grid(row=i, column=0, sticky="ew", padx=12, pady=3)
            line.grid_columnconfigure(1, weight=1)
            label(line, f"{i - row:02d}", 12, "bold", t.SUBTLE, width=30).grid(row=0, column=0,
                                                                                sticky="nw")
            strip = BallStrip(line, bet.numbers, spec.color, size=28, square=bet.trevos,
                              fmt=spec.format_number)
            strip.grid(row=0, column=1, sticky="ew")
            self._strips.append(strip)

    def _participants(self, row: int) -> int:
        """Tabela de participantes com marcação de pagamento."""
        assert self.bolao is not None
        spec = self.app.spec
        label(self.body, "PARTICIPANTES", 10, "bold", t.SUBTLE, height=14).grid(
            row=row, column=0, sticky="w", padx=12, pady=(8, 4))
        for i, person in enumerate(self.bolao.participants, start=row + 1):
            line = ctk.CTkFrame(self.body, fg_color=t.SURFACE_ALT, corner_radius=t.RADIUS_SM)
            line.grid(row=i, column=0, sticky="ew", padx=12, pady=2)
            line.grid_columnconfigure(0, weight=1)
            label(line, person.name, 13).grid(row=0, column=0, sticky="w", padx=12, pady=6)
            label(line, f"{person.cotas} cota(s) · {brl(self.bolao.amount_due(spec, person))}",
                  12, color=t.MUTED).grid(row=0, column=1, padx=12)
            box = ctk.CTkCheckBox(line, text="pago", width=56, font=t.font(12),
                                  text_color=t.MUTED,
                                  checkbox_width=18, checkbox_height=18, corner_radius=5,
                                  fg_color=t.accent(spec.color), border_color=t.SUBTLE,
                                  command=lambda p=person: self._toggle_paid(p))
            if person.paid:
                box.select()
            box.grid(row=0, column=2, padx=(0, 12))
        paid = sum(self.bolao.amount_due(spec, p) for p in self.bolao.participants if p.paid)
        label(self.body, f"Arrecadado {brl(paid)} de {brl(self.bolao.total_cost(spec))}",
              12, color=t.MUTED).grid(row=row + len(self.bolao.participants) + 1, column=0,
                                      sticky="w", padx=12, pady=(4, 0))
        return row + len(self.bolao.participants) + 2

    def _toggle_paid(self, person: bl.Participant) -> None:
        """Marca/desmarca pagamento e atualiza o total (salva se já estiver salvo)."""
        person.paid = not person.paid
        if self.bolao and self.bolao.id is not None:
            self.save(quiet=True)
        self.show(self.bolao)

    def save(self, quiet: bool = False) -> None:
        """Salva (ou atualiza) o bolão no banco."""
        if not self.bolao:
            return
        bolao = self.bolao
        bolao.id = self.app.services.storage.save_bolao(bolao.game, bolao.name,
                                                        bolao.to_dict(), bolao.id)
        if not quiet:
            self.notice.show("Bolão salvo.", "ok")
            self._on_saved()

    def copy(self) -> None:
        """Copia o resumo formatado para o WhatsApp."""
        if not self.bolao:
            return
        self.clipboard_clear()
        self.clipboard_append(bl.share_text(self.app.spec, self.bolao))
        self.notice.show("Resumo copiado. É só colar no grupo.", "ok")

    def check(self) -> None:
        """Confere o bolão contra o concurso informado."""
        if not self.bolao:
            return
        raw = self.contest_entry.get().strip()
        storage, spec = self.app.services.storage, self.app.spec
        if raw and not raw.isdigit():
            self.notice.show("Concurso deve ser um número.", "error")
            return
        draw = storage.get_draw(spec.slug, int(raw)) if raw else storage.latest_draw(spec.slug)
        if draw is None:
            self.notice.show(f"O concurso {raw} ainda não está na base. Atualize depois do "
                             "sorteio.", "error")
            return
        result = bl.check_bolao(spec, self.bolao, draw)
        text = bl.result_text(spec, self.bolao, result).replace("*", "")
        self.show(self.bolao)
        box = ctk.CTkFrame(self.body, fg_color=t.accent_soft(spec.color),
                           corner_radius=t.RADIUS)
        box.grid(row=999, column=0, sticky="ew", padx=12, pady=(16, 8))
        label(box, text, 12, wraplength=560).pack(anchor="w", padx=16, pady=12)
        self.notice.show(f"Conferido com o concurso {draw.contest}.",
                         "ok" if result.winning_bets else "info")
