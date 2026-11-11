"""Design system minimalista: cores neutras, uma cor de destaque por loteria.

Cores são pares ``(claro, escuro)``, o formato aceito pelo CustomTkinter.
"""

from __future__ import annotations

import tkinter
import tkinter.font as tkfont
from functools import lru_cache

import customtkinter as ctk

Color = tuple[str, str]

BG: Color = ("#F5F6F8", "#0E1014")
SURFACE: Color = ("#FFFFFF", "#16191F")
SURFACE_ALT: Color = ("#EEF0F3", "#1D2129")
BORDER: Color = ("#E3E6EB", "#262A33")
TEXT: Color = ("#111318", "#E9EBEE")
MUTED: Color = ("#6B7280", "#9198A1")
SUBTLE: Color = ("#9CA3AF", "#5F6670")
SUCCESS: Color = ("#16794C", "#4ADE80")
DANGER: Color = ("#B42318", "#F87171")

RADIUS = 12
RADIUS_SM = 8
PAD = 24
GAP = 12


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    """``"#209869" -> (32, 152, 105)``."""
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def mix(color: str, other: str, amount: float) -> str:
    """Mistura duas cores hex (``amount`` = peso de ``other``, 0–1)."""
    a, b = _hex_to_rgb(color), _hex_to_rgb(other)
    return "#" + "".join(f"{round(x + (y - x) * amount):02X}" for x, y in zip(a, b, strict=True))


def accent(color: str) -> Color:
    """Cor de destaque legível nos dois modos (clareia no modo escuro)."""
    return color, mix(color, "#FFFFFF", 0.35)


def accent_soft(color: str) -> Color:
    """Fundo suave da cor de destaque (bolinhas, seleção)."""
    return mix(color, "#FFFFFF", 0.86), mix(color, "#16191F", 0.72)


def accent_hover(color: str) -> Color:
    """Variação de hover para botões de destaque."""
    return mix(color, "#000000", 0.12), mix(color, "#FFFFFF", 0.45)


def resolve(color: Color | str) -> str:
    """Escolhe a variante do par conforme o modo atual (para widgets Tk puros)."""
    if isinstance(color, str):
        return color
    return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]


@lru_cache(maxsize=1)
def font_family() -> str:
    """Primeira fonte moderna disponível no sistema."""
    available = set(tkfont.families())
    for family in ("Segoe UI Variable Text", "Segoe UI", "Inter", "SF Pro Text",
                   "Helvetica Neue", "Cantarell", "DejaVu Sans"):
        if family in available:
            return family
    return "TkDefaultFont"


@lru_cache(maxsize=1)
def mono_family() -> str:
    """Fonte monoespaçada para tabelas."""
    available = set(tkfont.families())
    for family in ("Cascadia Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono"):
        if family in available:
            return family
    return "TkFixedFont"


_FONTS: dict[tuple[int, str, int, str], ctk.CTkFont] = {}


def _cached_font(family: str, size: int, weight: str) -> ctk.CTkFont:
    """Reaproveita fontes em vez de criar uma por widget.

    Além de economizar memória, isso evita um travamento: fontes descartadas
    viram lixo, e o coletor do Python pode destruí-las dentro de uma thread de
    trabalho, cujo ``__del__`` chama o Tcl fora da thread principal. Mantidas
    no cache, elas só são liberadas junto com a janela.
    """
    root = tkinter._default_root  # fontes pertencem ao interpretador Tcl da janela
    key = (id(root), size, weight, family)
    if key not in _FONTS:
        _FONTS[key] = ctk.CTkFont(family=family, size=size, weight=weight)
    return _FONTS[key]


def release_fonts() -> None:
    """Descarta o cache (chamar na thread principal ao fechar a janela)."""
    _FONTS.clear()


def font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    """Fonte da interface no tamanho pedido."""
    return _cached_font(font_family(), size, weight)


def mono(size: int = 12) -> ctk.CTkFont:
    """Fonte monoespaçada."""
    return _cached_font(mono_family(), size, "normal")
