"""Aviso flutuante discreto no canto inferior direito da janela."""

from __future__ import annotations

from typing import Optional

import customtkinter as ctk

from loterias.gui import theme as t
from loterias.gui.widgets import label


class Toast(ctk.CTkFrame):
    """Cartão temporário com título, mensagem e botão de fechar.

    Args:
        master: Janela principal.
        title: Linha em destaque.
        message: Detalhe.
        color: Cor da loteria (barra lateral do cartão).
        duration_ms: Tempo até sumir sozinho (0 = só fecha no X).
    """

    _stack: list["Toast"] = []

    def __init__(self, master: ctk.CTk, title: str, message: str, color: str,
                 duration_ms: int = 12000) -> None:
        super().__init__(master, fg_color=t.SURFACE, corner_radius=t.RADIUS, border_width=1,
                         border_color=t.accent(color), width=340, height=10)
        self.grid_columnconfigure(1, weight=1)
        bar = ctk.CTkFrame(self, width=4, height=10, fg_color=t.accent(color), corner_radius=2)
        bar.grid(row=0, column=0, rowspan=2, sticky="ns", padx=(10, 8), pady=12)
        label(self, title, 13, "bold", wraplength=260).grid(row=0, column=1, sticky="w",
                                                             pady=(12, 0))
        label(self, message, 12, color=t.MUTED, wraplength=260).grid(row=1, column=1,
                                                                     sticky="w", pady=(0, 12))
        ctk.CTkButton(self, text="✕", width=26, height=24, fg_color="transparent",
                      hover_color=t.SURFACE_ALT, text_color=t.MUTED, font=t.font(12),
                      command=self.dismiss).grid(row=0, column=2, sticky="ne", padx=6, pady=6)
        self._job: Optional[str] = self.after(duration_ms, self.dismiss) if duration_ms else None
        Toast._stack.append(self)
        self._restack()

    @classmethod
    def _restack(cls) -> None:
        """Empilha os avisos abertos de baixo para cima."""
        y = -20
        for toast in reversed(cls._stack):
            toast.update_idletasks()
            toast.place(relx=1.0, rely=1.0, x=-20, y=y, anchor="se")
            toast.lift()
            y -= toast.winfo_reqheight() + 10

    def dismiss(self) -> None:
        """Fecha o aviso."""
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        if self in Toast._stack:
            Toast._stack.remove(self)
        if self.winfo_exists():
            self.destroy()
        Toast._restack()
