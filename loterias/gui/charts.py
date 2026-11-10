"""Gráficos matplotlib embutidos, com estilo minimalista e cores do tema."""

from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from loterias.games import GameSpec
from loterias.gui import theme as t
from loterias.stats import StatsSummary

CHARTS = ("Frequência", "Atraso", "Par / ímpar", "Soma")


class ChartView(ctk.CTkFrame):
    """Área de gráfico que acompanha o tema claro/escuro."""

    def __init__(self, master: ctk.CTkBaseClass) -> None:
        super().__init__(master, fg_color="transparent")
        self.figure = Figure(figsize=(6, 3.6), dpi=100)
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self._last: Optional[Callable[[], None]] = None

    def destroy(self) -> None:
        """Libera a figura ao fechar."""
        self.figure.clear()
        super().destroy()

    def _style(self) -> tuple[str, str, str]:
        """Aplica fundo, grade e textos do tema; devolve (texto, sutil, borda)."""
        bg, text = t.resolve(t.SURFACE), t.resolve(t.TEXT)
        muted, border = t.resolve(t.MUTED), t.resolve(t.BORDER)
        self.figure.set_facecolor(bg)
        self.canvas.get_tk_widget().configure(bg=bg)
        ax = self.axes
        ax.clear()
        ax.set_facecolor(bg)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(border)
        ax.tick_params(colors=muted, labelsize=8, length=0)
        ax.grid(axis="y", color=border, linewidth=0.8)
        ax.set_axisbelow(True)
        return text, muted, border

    def redraw(self) -> None:
        """Repete o último gráfico (ao trocar o tema)."""
        if self._last:
            self._last()

    def show(self, kind: str, spec: GameSpec, summary: StatsSummary) -> None:
        """Desenha o gráfico pedido."""
        def draw() -> None:
            text, muted, _ = self._style()
            strong = t.resolve(t.accent(spec.color))
            soft = t.resolve(t.accent_soft(spec.color))
            ax = self.axes
            if kind == "Frequência":
                numbers = list(summary.freq)
                hot = set(summary.hot)
                ax.bar(numbers, [summary.freq[n] for n in numbers], width=0.72,
                       color=[strong if n in hot else soft for n in numbers])
                ax.axhline(summary.expected, color=muted, linestyle=(0, (4, 3)), linewidth=1)
                ax.text(numbers[-1], summary.expected, "  esperado", color=muted, fontsize=8,
                        va="bottom", ha="right")
                ax.set_xlim(numbers[0] - 1, numbers[-1] + 1)
                title = "Frequência de cada dezena"
            elif kind == "Atraso":
                numbers = list(summary.delay)
                overdue = set(summary.overdue)
                ax.bar(numbers, [summary.delay[n] for n in numbers], width=0.72,
                       color=[strong if n in overdue else soft for n in numbers])
                ax.set_xlim(numbers[0] - 1, numbers[-1] + 1)
                title = "Atraso: concursos sem sair"
            elif kind == "Par / ímpar":
                keys = list(range(spec.draw_size + 1))
                total = sum(summary.parity.values()) or 1
                values = [100 * summary.parity.get(k, 0) / total for k in keys]
                best = max(range(len(values)), key=values.__getitem__)
                ax.bar(keys, values, width=0.6,
                       color=[strong if i == best else soft for i in keys])
                ax.set_xticks(keys, [f"{k} ímp." for k in keys])
                title = "% dos sorteios por nº de ímpares"
            else:
                ax.hist(summary.sum_values, bins=30, color=soft, edgecolor=t.resolve(t.SURFACE))
                low, high = summary.sum_band
                ax.axvspan(low, high, color=strong, alpha=0.12, linewidth=0)
                title = f"Soma das dezenas · 80% entre {low:.0f} e {high:.0f}"
            if spec.is_columns:  # Super Sete: barras agrupadas por coluna (dígitos 0–9)
                ax.set_xticks([c * 10 + 4.5 for c in range(spec.columns)],
                              [f"Coluna {c + 1}" for c in range(spec.columns)])
                for c in range(1, spec.columns):
                    ax.axvline(c * 10 - 0.5, color=t.resolve(t.BORDER), linewidth=1)
                title += " (dígitos 0–9 em cada coluna)"
            ax.set_title(title, color=text, fontsize=10, loc="left", pad=12)
            self.figure.tight_layout(pad=1.2)
            self.canvas.draw_idle()

        self._last = draw
        draw()

