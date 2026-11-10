"""Barra lateral: escolha da loteria, estado da base e atualização."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import customtkinter as ctk
from PIL import Image, ImageDraw

from loterias.formatting import brl_compact, date_br, thousands
from loterias.games import GAMES, GameSpec
from loterias.gui import theme as t
from loterias.gui.widgets import label
from loterias.models import Draw

if TYPE_CHECKING:
    from loterias.gui.app import App

WIDTH = 236


def _dot(color: str, size: int = 20) -> ctk.CTkImage:
    """Bolinha colorida que identifica cada loteria na lista."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse((2, 2, size - 2, size - 2), fill=color)
    dark = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(dark).ellipse((2, 2, size - 2, size - 2), fill=t.accent(color)[1])
    return ctk.CTkImage(light_image=image, dark_image=dark, size=(9, 9))


class Sidebar(ctk.CTkFrame):
    """Navegação entre loterias e painel de sincronização.

    Args:
        master: Janela principal.
        app: Controlador do aplicativo.
        on_select: Chamado com o slug quando o usuário troca de loteria.
    """

    def __init__(self, master: ctk.CTkBaseClass, app: "App",
                 on_select: Callable[[str], None]) -> None:
        super().__init__(master, width=WIDTH, corner_radius=0, fg_color=t.SURFACE,
                         border_width=0)
        self.app = app
        self._on_select = on_select
        self._buttons: dict[str, ctk.CTkButton] = {}
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build_brand()
        self._build_games()
        self._build_status()

    def _build_brand(self) -> None:
        """Título do app."""
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.grid(row=0, column=0, sticky="ew", padx=20, pady=(24, 18))
        label(box, "Loterias", 20, "bold").pack(anchor="w")
        label(box, "estatística & bolões", 12, color=t.MUTED, height=16).pack(anchor="w")

    def _build_games(self) -> None:
        """Lista de loterias."""
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.grid(row=1, column=0, sticky="ew", padx=12)
        for spec in GAMES.values():
            button = ctk.CTkButton(
                box, text=f"  {spec.name}", image=_dot(spec.color), compound="left",
                anchor="w", height=36, corner_radius=t.RADIUS_SM,
                font=t.font(13), fg_color="transparent", hover_color=t.SURFACE_ALT,
                text_color=t.TEXT, command=lambda s=spec.slug: self._on_select(s))
            button.pack(fill="x", pady=1)
            self._buttons[spec.slug] = button

    def _build_status(self) -> None:
        """Cartão com o estado da base e os controles de atualização."""
        box = ctk.CTkFrame(self, fg_color=t.SURFACE_ALT, corner_radius=t.RADIUS)
        box.grid(row=3, column=0, sticky="ew", padx=12, pady=(8, 12))
        box.grid_columnconfigure(0, weight=1)
        label(box, "BASE DE DADOS", 10, "bold", t.SUBTLE, height=14).grid(
            row=0, column=0, sticky="w", padx=14, pady=(12, 2))
        self.status_title = label(box, "—", 13, "bold")
        self.status_title.grid(row=1, column=0, sticky="w", padx=14)
        self.status_body = label(box, "", 12, color=t.MUTED, wraplength=WIDTH - 60)
        self.status_body.grid(row=2, column=0, sticky="w", padx=14)
        self.progress = ctk.CTkProgressBar(box, height=4, corner_radius=2,
                                           fg_color=t.BORDER, progress_color=t.MUTED)
        self.progress.set(0)
        self.progress.grid(row=3, column=0, sticky="ew", padx=14, pady=(8, 4))
        self.sync_label = label(box, "", 11, color=t.MUTED, wraplength=WIDTH - 60)
        self.sync_label.grid(row=4, column=0, sticky="w", padx=14)
        row = ctk.CTkFrame(box, fg_color="transparent")
        row.grid(row=5, column=0, sticky="ew", padx=10, pady=(6, 4))
        row.grid_columnconfigure((0, 1), weight=1)
        self.btn_update = ctk.CTkButton(
            row, text="Atualizar", height=32, corner_radius=t.RADIUS_SM, font=t.font(12, "bold"),
            command=lambda: self.app.start_sync([self.app.spec.slug]))
        self.btn_update.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        self.btn_update_all = ctk.CTkButton(
            row, text="Todas", height=32, corner_radius=t.RADIUS_SM, font=t.font(12),
            fg_color="transparent", border_width=1, border_color=t.BORDER, text_color=t.TEXT,
            hover_color=t.SURFACE, command=lambda: self.app.start_sync(None))
        self.btn_update_all.grid(row=0, column=1, sticky="ew", padx=(3, 0))
        self.auto_switch = ctk.CTkSwitch(
            box, text="Atualização automática", font=t.font(12), text_color=t.MUTED,
            switch_width=32, switch_height=16, command=self._toggle_auto)
        self.auto_switch.grid(row=6, column=0, sticky="w", padx=14, pady=(6, 4))
        if self.app.services.settings.auto_update:
            self.auto_switch.select()
        self.appearance = ctk.CTkSegmentedButton(
            box, values=["Sistema", "Claro", "Escuro"], font=t.font(11), height=26,
            fg_color=t.BORDER, unselected_color=t.BORDER, unselected_hover_color=t.SURFACE,
            text_color=t.TEXT, corner_radius=t.RADIUS_SM,
            command=self._change_appearance)
        mode = {"system": "Sistema", "light": "Claro", "dark": "Escuro"}
        self.appearance.set(mode.get(self.app.services.settings.appearance, "Sistema"))
        self.appearance.grid(row=7, column=0, sticky="ew", padx=14, pady=(4, 14))

    def _toggle_auto(self) -> None:
        """Liga/desliga a atualização automática e salva a preferência."""
        settings = self.app.services.settings
        settings.auto_update = bool(self.auto_switch.get())
        settings.save()
        self.app.schedule_auto_sync()

    def _change_appearance(self, value: str) -> None:
        """Alterna claro/escuro."""
        mode = {"Sistema": "system", "Claro": "light", "Escuro": "dark"}[value]
        self.app.set_appearance(mode)

    def select(self, spec: GameSpec) -> None:
        """Destaca a loteria ativa e aplica sua cor aos controles."""
        for slug, button in self._buttons.items():
            active = slug == spec.slug
            game_color = t.accent(GAMES[slug].color)
            button.configure(
                fg_color=t.accent_soft(spec.color) if active else "transparent",
                text_color=game_color if active else t.TEXT,
                font=t.font(13, "bold" if active else "normal"))
        self.btn_update.configure(fg_color=t.accent(spec.color),
                                  hover_color=t.accent_hover(spec.color),
                                  text_color=("#FFFFFF", "#0E1014"))
        self.progress.configure(progress_color=t.accent(spec.color))
        self.auto_switch.configure(progress_color=t.accent(spec.color))
        self.appearance.configure(selected_color=t.accent_soft(spec.color),
                                  selected_hover_color=t.accent_soft(spec.color))

    def show_base(self, spec: GameSpec, latest: Draw | None, total: int) -> None:
        """Mostra o último concurso e a estimativa do próximo."""
        if latest is None:
            self.status_title.configure(text="Base vazia")
            self.status_body.configure(text=f"Clique em Atualizar para baixar o histórico "
                                            f"da {spec.name}.")
            return
        self.status_title.configure(text=f"Concurso {latest.contest}")
        lines = [f"{date_br(latest.date)} · {thousands(total)} concursos"]
        if latest.next_estimate:
            lines.append(f"Próximo: {brl_compact(latest.next_estimate)}"
                         + (f" em {date_br(latest.next_date)}" if latest.next_date else ""))
        self.status_body.configure(text="\n".join(lines))

    def set_busy(self, busy: bool, message: str = "") -> None:
        """Estado visual durante a sincronização."""
        state = "disabled" if busy else "normal"
        self.btn_update.configure(state=state)
        self.btn_update_all.configure(state=state)
        if busy:
            self.progress.configure(mode="indeterminate")
            self.progress.start()
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate")
            self.progress.set(0)
        self.sync_label.configure(text=message, text_color=t.MUTED)

    def set_progress(self, fraction: float, message: str) -> None:
        """Progresso determinado (download concurso a concurso)."""
        if str(self.progress.cget("mode")) != "determinate":
            self.progress.stop()
            self.progress.configure(mode="determinate")
        self.progress.set(max(0.0, min(1.0, fraction)))
        self.sync_label.configure(text=message)

    def set_sync_message(self, message: str, error: bool = False) -> None:
        """Mensagem final da sincronização."""
        self.sync_label.configure(text=message, text_color=t.DANGER if error else t.MUTED)
