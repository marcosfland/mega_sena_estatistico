"""Página "Estatísticas": gráficos e resumo do histórico."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from loterias.formatting import thousands
from loterias.gui import theme as t
from loterias.gui.charts import CHARTS, ChartView
from loterias.gui.page_base import Page
from loterias.gui.widgets import BallStrip, Card, Notice, label, scrollable
from loterias.stats import StatsSummary, last_n, summarize

if TYPE_CHECKING:
    from loterias.gui.app import App

WINDOWS = {"Todo o histórico": None, "Últimos 500": 500, "Últimos 100": 100,
           "Últimos 50": 50, "Últimos 20": 20}


class StatsPage(Page):
    """Gráfico interativo + painel de destaques."""

    title = "Estatísticas"

    def __init__(self, master: ctk.CTkBaseClass, app: "App") -> None:
        super().__init__(master, app)
        self._summary: Optional[StatsSummary] = None
        self._dirty = True
        self._strips: list[BallStrip] = []
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_controls()
        self._build_body()

    def _build_controls(self) -> None:
        """Seletores de período e de gráfico."""
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", pady=(0, t.GAP))
        bar.grid_columnconfigure(1, weight=1)
        style = dict(height=32, font=t.font(12), corner_radius=t.RADIUS_SM,
                     fg_color=t.SURFACE_ALT, unselected_color=t.SURFACE_ALT,
                     unselected_hover_color=t.BORDER, text_color=t.TEXT)
        self.window = ctk.CTkSegmentedButton(bar, values=list(WINDOWS),
                                             command=lambda _v: self.refresh(), **style)
        self.window.set("Todo o histórico")
        self.window.grid(row=0, column=0, sticky="w")
        self.chart_kind = ctk.CTkSegmentedButton(bar, values=list(CHARTS),
                                                 command=lambda _v: self._draw_chart(), **style)
        self.chart_kind.set(CHARTS[0])
        self.chart_kind.grid(row=0, column=2, sticky="e")
        self._segmented = (self.window, self.chart_kind)

    def _build_body(self) -> None:
        """Gráfico à esquerda e destaques à direita."""
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)
        chart_card = Card(body)
        chart_card.grid(row=0, column=0, sticky="nsew", padx=(0, t.GAP))
        chart_card.grid_columnconfigure(0, weight=1)
        chart_card.grid_rowconfigure(0, weight=1)
        self.chart = ChartView(chart_card)
        self.chart.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self.notice = Notice(chart_card)
        self.notice.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 12))
        side = Card(body, width=330)
        side.grid(row=0, column=1, sticky="nsew")
        side.grid_propagate(False)
        side.grid_columnconfigure(0, weight=1)
        side.grid_rowconfigure(0, weight=1)
        self.panel = scrollable(side)
        self.panel.grid(row=0, column=0, sticky="nsew", padx=6, pady=8)
        self.panel.grid_columnconfigure(0, weight=1)

    # ---------------------------------------------------------------- eventos
    def on_game_changed(self) -> None:
        """Marca para recalcular e recolore os seletores."""
        for seg in self._segmented:
            seg.configure(selected_color=t.accent_soft(self.spec.color),
                          selected_hover_color=t.accent_soft(self.spec.color))
        self._dirty = True
        if self.winfo_ismapped():
            self.refresh()

    def on_data_changed(self) -> None:
        """Novos concursos: recalcula."""
        self.on_game_changed()

    def on_show(self) -> None:
        """Calcula ao abrir a página, se necessário."""
        if self._dirty:
            self.refresh()

    def on_appearance_changed(self) -> None:
        """Redesenha gráfico e bolinhas no novo tema."""
        self.chart.redraw()
        for strip in self._strips:
            strip.redraw()

    # ---------------------------------------------------------------- cálculo
    def refresh(self) -> None:
        """Recalcula o resumo em segundo plano."""
        self._dirty = False
        draws = self.app.draws()
        if not draws:
            self.notice.show("Base vazia. Use Atualizar na barra lateral.", "error")
            self._summary = None
            self._fill_panel()
            return
        spec, window = self.spec, WINDOWS[self.window.get()]
        self.notice.show("Calculando…")
        self.app.runner.submit(lambda: summarize(spec, last_n(draws, window)),
                               on_success=lambda s: self._apply(spec.slug, s),
                               on_error=lambda e: self.notice.show(str(e), "error"))

    def _apply(self, slug: str, summary: StatsSummary) -> None:
        """Recebe o resumo (descarta se a loteria mudou no meio do cálculo)."""
        if slug != self.spec.slug:
            return
        self._summary = summary
        self.notice.show(f"{thousands(summary.contests)} concursos analisados")
        self._draw_chart()
        self._fill_panel()

    def _draw_chart(self) -> None:
        """Desenha o gráfico selecionado."""
        if self._summary:
            self.chart.show(self.chart_kind.get(), self.spec, self._summary)

    def _section(self, row: int, title: str, body: str = "") -> int:
        """Adiciona um bloco de texto ao painel e devolve a próxima linha."""
        label(self.panel, title.upper(), 10, "bold", t.SUBTLE, height=14).grid(
            row=row, column=0, sticky="w", padx=14, pady=(14, 4))
        if body:
            label(self.panel, body, 12, color=t.TEXT, wraplength=250).grid(
                row=row + 1, column=0, sticky="w", padx=14)
        return row + 2

    def _balls(self, row: int, title: str, numbers: list[int], caption: str) -> int:
        """Bloco com bolinhas e legenda."""
        row = self._section(row, title)
        strip = BallStrip(self.panel, numbers, self.spec.color, size=28)
        strip.grid(row=row - 1, column=0, sticky="ew", padx=14)
        self._strips.append(strip)
        if caption:
            label(self.panel, caption, 11, color=t.MUTED, wraplength=250).grid(
                row=row, column=0, sticky="w", padx=14, pady=(4, 0))
        return row + 1

    def _fill_panel(self) -> None:
        """Monta o painel de destaques."""
        for child in self.panel.winfo_children():
            child.destroy()
        self._strips = []
        s = self._summary
        if s is None:
            return
        spec = self.spec
        row = self._balls(0, "Mais sorteadas", s.hot[:8],
                          f"Esperado por dezena: {s.expected:.0f} vezes")
        row = self._balls(row, "Menos sorteadas", s.cold[:8], "")
        row = self._balls(row, "Mais atrasadas", s.overdue[:8],
                          "Maior atraso: " + f"{s.delay[s.overdue[0]]} concursos")
        common = max(s.parity, key=s.parity.get) if s.parity else 0
        row = self._section(row, "Par / ímpar",
                            f"O mais comum é {common} ímpares e {spec.draw_size - common} "
                            f"pares.")
        row = self._section(row, "Soma das dezenas",
                            f"Média {s.sum_mean:.0f}; 80% dos sorteios ficam entre "
                            f"{s.sum_band[0]:.0f} e {s.sum_band[1]:.0f}.")
        if s.repeats:
            usual = max(s.repeats, key=s.repeats.get)
            row = self._section(row, "Repetição", f"Normalmente {usual} dezena(s) repetem "
                                                  "do concurso anterior.")
        pairs = ", ".join(f"{spec.format_number(a)}-{spec.format_number(b)} ({c})"
                          for (a, b), c in s.pairs[:4])
        row = self._section(row, "Duplas frequentes", pairs)
        if s.trevos:
            row = self._section(row, "Trevos", "  ".join(
                f"{k}: {v}" for k, v in sorted(s.trevos.items(), key=lambda kv: -kv[1])))
        if s.extras:
            row = self._section(row, spec.extra_name or "Extra",
                                ", ".join(f"{k} ({v})" for k, v in s.extras[:5]))
        self._section(row, "Teste de uniformidade",
                      f"Qui-quadrado {s.chi.statistic:.1f}, p = {s.chi.p_value:.3f}: "
                      f"{s.chi.verdict()}.")
