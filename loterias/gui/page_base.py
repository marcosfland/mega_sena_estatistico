"""Classe base das páginas da interface."""

from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from loterias.games import GameSpec

if TYPE_CHECKING:
    from loterias.gui.app import App


class Page(ctk.CTkFrame):
    """Página exibida na área principal.

    Subclasses sobrescrevem os ganchos ``on_*`` para reagir a eventos do app.
    """

    title = ""

    def __init__(self, master: ctk.CTkBaseClass, app: "App") -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app

    @property
    def spec(self) -> GameSpec:
        """Loteria ativa."""
        return self.app.spec

    def on_game_changed(self) -> None:
        """A loteria ativa mudou."""

    def on_data_changed(self) -> None:
        """A base da loteria ativa recebeu concursos novos."""

    def on_appearance_changed(self) -> None:
        """O tema claro/escuro mudou (redesenhar canvases e gráficos)."""

    def on_show(self) -> None:
        """A página acabou de ficar visível."""
