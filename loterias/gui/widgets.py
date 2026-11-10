"""Componentes visuais reutilizáveis (cartões, bolinhas, seletor de dezenas, avisos)."""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Iterable, Optional, Sequence

import customtkinter as ctk

from loterias.gui import theme as t


class Card(ctk.CTkFrame):
    """Superfície branca (ou grafite) com borda fina e cantos arredondados."""

    def __init__(self, master: ctk.CTkBaseClass, **kwargs: object) -> None:
        kwargs.setdefault("fg_color", t.SURFACE)
        kwargs.setdefault("corner_radius", t.RADIUS)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", t.BORDER)
        super().__init__(master, **kwargs)


def label(master: ctk.CTkBaseClass, text: str = "", size: int = 13, weight: str = "normal",
          color: t.Color = t.TEXT, **kwargs: object) -> ctk.CTkLabel:
    """Rótulo com a tipografia do app, alinhado à esquerda."""
    kwargs.setdefault("anchor", "w")
    kwargs.setdefault("justify", "left")
    return ctk.CTkLabel(master, text=text, font=t.font(size, weight), text_color=color,
                        **kwargs)


def primary_button(master: ctk.CTkBaseClass, text: str, command: Callable[[], None],
                   color: str, **kwargs: object) -> ctk.CTkButton:
    """Botão principal preenchido com a cor da loteria."""
    kwargs.setdefault("height", 38)
    return ctk.CTkButton(master, text=text, command=command, font=t.font(13, "bold"),
                         corner_radius=t.RADIUS_SM, fg_color=t.accent(color),
                         hover_color=t.accent_hover(color), text_color=("#FFFFFF", "#0E1014"),
                         **kwargs)


def ghost_button(master: ctk.CTkBaseClass, text: str, command: Callable[[], None],
                 **kwargs: object) -> ctk.CTkButton:
    """Botão secundário discreto (só contorno)."""
    kwargs.setdefault("height", 38)
    return ctk.CTkButton(master, text=text, command=command, font=t.font(13),
                         corner_radius=t.RADIUS_SM, fg_color="transparent",
                         hover_color=t.SURFACE_ALT, border_width=1, border_color=t.BORDER,
                         text_color=t.TEXT, **kwargs)


def recolor_primary(button: ctk.CTkButton, color: str) -> None:
    """Troca a cor de um botão principal quando a loteria muda."""
    button.configure(fg_color=t.accent(color), hover_color=t.accent_hover(color))


class Notice(ctk.CTkLabel):
    """Linha de aviso inline (informação, sucesso ou erro)."""

    _COLORS = {"info": t.MUTED, "ok": t.SUCCESS, "error": t.DANGER}

    def __init__(self, master: ctk.CTkBaseClass, **kwargs: object) -> None:
        super().__init__(master, text="", anchor="w", justify="left", font=t.font(12),
                         text_color=t.MUTED, **kwargs)

    def show(self, text: str, kind: str = "info") -> None:
        """Exibe a mensagem com a cor do tipo."""
        self.configure(text=text, text_color=self._COLORS.get(kind, t.MUTED))

    def clear(self) -> None:
        """Apaga a mensagem."""
        self.configure(text="")


class BallStrip(tk.Canvas):
    """Fileira de dezenas desenhada num único canvas (rápido mesmo com 50 dezenas).

    Quebra a linha automaticamente conforme a largura disponível.
    """

    def __init__(self, master: tk.Misc, numbers: Sequence[int] = (), color: str = "#209869",
                 highlight: Iterable[int] = (), size: int = 30, bg: t.Color = t.SURFACE,
                 square: Sequence[int] = ()) -> None:
        super().__init__(master, height=size, highlightthickness=0, bd=0,
                         bg=t.resolve(bg))
        self._numbers = list(numbers)
        self._square = list(square)
        self._color = color
        self._highlight = set(highlight)
        self._size = size
        self._bg = bg
        self.bind("<Configure>", lambda _e: self.redraw())

    def set(self, numbers: Sequence[int], color: Optional[str] = None,
            highlight: Iterable[int] = (), square: Sequence[int] = ()) -> None:
        """Troca as dezenas exibidas."""
        self._numbers = list(numbers)
        self._square = list(square)
        self._highlight = set(highlight)
        if color:
            self._color = color
        self.redraw()

    def redraw(self) -> None:
        """Redesenha (também usado ao trocar claro/escuro)."""
        self.delete("all")
        self.configure(bg=t.resolve(self._bg))
        items = [(n, False) for n in self._numbers] + [(n, True) for n in self._square]
        if not items:
            self.configure(height=1)
            return
        size, gap = self._size, 6
        width = max(self.winfo_width(), size)
        per_row = max(1, (width + gap) // (size + gap))
        rows = (len(items) + per_row - 1) // per_row
        height = rows * (size + gap) - gap
        if int(float(self.cget("height"))) != height:
            self.configure(height=height)
        strong = t.resolve(t.accent(self._color))
        soft = t.resolve(t.accent_soft(self._color))
        on_strong = "#FFFFFF" if strong == self._color else "#0E1014"
        typeface = (t.font_family(), max(9, size // 3), "bold")
        for i, (number, is_square) in enumerate(items):
            row, col = divmod(i, per_row)
            x, y = col * (size + gap), row * (size + gap)
            hot = number in self._highlight and not is_square
            fill = strong if hot or is_square else soft
            if is_square:
                self.create_rectangle(x + 2, y + 2, x + size - 2, y + size - 2,
                                      fill=fill, outline="")
            else:
                self.create_oval(x, y, x + size, y + size, fill=fill, outline="")
            self.create_text(x + size / 2, y + size / 2, text=f"{number:02d}",
                             fill=on_strong if hot or is_square else strong, font=typeface)


class NumberPicker(ctk.CTkFrame):
    """Grade clicável de dezenas, com limite de seleção.

    Args:
        master: Widget pai.
        on_change: Chamado com a lista ordenada de selecionadas.
    """

    def __init__(self, master: ctk.CTkBaseClass,
                 on_change: Optional[Callable[[list[int]], None]] = None) -> None:
        super().__init__(master, fg_color="transparent")
        self._on_change = on_change
        self._buttons: dict[int, ctk.CTkButton] = {}
        self._selected: set[int] = set()
        self._limit = 0
        self._color = "#209869"
        self._columns = 10
        self._max_columns = 10

    def configure_numbers(self, numbers: range, limit: int, color: str,
                          columns: int = 10) -> None:
        """Recria a grade para uma nova faixa de dezenas."""
        for button in self._buttons.values():
            button.destroy()
        self._buttons.clear()
        self._selected.clear()
        self._limit, self._color = limit, color
        self._max_columns = self._columns = columns
        for number in numbers:
            button = ctk.CTkButton(
                self, text=f"{number:02d}", width=36, height=32, corner_radius=t.RADIUS_SM,
                font=t.font(12), border_width=0, command=lambda n=number: self.toggle(n))
            self._buttons[number] = button
            self._paint(number)
        self._layout()

    def _layout(self) -> None:
        """Posiciona os botões na quantidade atual de colunas."""
        for i, button in enumerate(self._buttons.values()):
            button.grid(row=i // self._columns, column=i % self._columns, padx=2, pady=2)

    def reflow(self, width: int) -> None:
        """Ajusta as colunas à largura disponível (mínimo 5, máximo o configurado)."""
        columns = max(5, min(self._max_columns, width // 40))
        if columns != self._columns:
            self._columns = columns
            self._layout()

    def _paint(self, number: int) -> None:
        """Aplica o visual de selecionada/não selecionada."""
        button = self._buttons[number]
        if number in self._selected:
            button.configure(fg_color=t.accent(self._color),
                             hover_color=t.accent_hover(self._color),
                             text_color=("#FFFFFF", "#0E1014"))
        else:
            button.configure(fg_color=t.SURFACE_ALT, hover_color=t.accent_soft(self._color),
                             text_color=t.TEXT)

    def toggle(self, number: int) -> None:
        """Marca/desmarca uma dezena (respeitando o limite)."""
        if number in self._selected:
            self._selected.remove(number)
        elif len(self._selected) < self._limit:
            self._selected.add(number)
        else:
            return
        self._paint(number)
        if self._on_change:
            self._on_change(self.selected)

    @property
    def selected(self) -> list[int]:
        """Dezenas marcadas, ordenadas."""
        return sorted(self._selected)

    def set_selected(self, numbers: Iterable[int]) -> None:
        """Marca exatamente as dezenas informadas."""
        self._selected = {n for n in numbers if n in self._buttons}
        for number in self._buttons:
            self._paint(number)
        if self._on_change:
            self._on_change(self.selected)

    def clear(self) -> None:
        """Desmarca tudo."""
        self.set_selected(())


def scrollable(master: ctk.CTkBaseClass, **kwargs: object) -> ctk.CTkScrollableFrame:
    """Área rolável sem fundo próprio (herda do cartão)."""
    kwargs.setdefault("fg_color", "transparent")
    return ctk.CTkScrollableFrame(master, scrollbar_button_color=t.BORDER,
                                  scrollbar_button_hover_color=t.SUBTLE, **kwargs)
