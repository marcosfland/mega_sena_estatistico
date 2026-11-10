"""Formatação de valores no padrão brasileiro."""

from __future__ import annotations

import datetime as dt
from typing import Optional


def brl(value: Optional[float]) -> str:
    """Formata reais: ``1234.5 -> "R$ 1.234,50"`` (``"—"`` para ``None``)."""
    if value is None:
        return "—"
    text = f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {text}"


def brl_compact(value: Optional[float]) -> str:
    """Valores grandes abreviados: ``185000000 -> "R$ 185 mi"``."""
    if value is None:
        return "—"
    if value >= 1_000_000_000:
        return f"R$ {value / 1_000_000_000:.1f} bi".replace(".", ",")
    if value >= 1_000_000:
        number = value / 1_000_000
        text = f"{number:.0f}" if number >= 100 else f"{number:.1f}".replace(".", ",")
        return f"R$ {text} mi"
    return brl(value)


def date_br(value: Optional[dt.date]) -> str:
    """``2026-10-18 -> "18/10/2026"`` (``"—"`` para ``None``)."""
    return value.strftime("%d/%m/%Y") if value else "—"


def thousands(value: int) -> str:
    """``3071 -> "3.071"``."""
    return f"{value:,}".replace(",", ".")
