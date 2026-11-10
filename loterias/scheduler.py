"""Agendamento da atualização diária no sistema operacional.

No Windows cria uma tarefa no Agendador de Tarefas (``schtasks``); em Linux e
macOS devolve a linha a ser adicionada ao ``crontab``. Assim as bases ficam em
dia mesmo com o aplicativo fechado.
"""

from __future__ import annotations

import logging
import platform
import re
import subprocess
import sys
from pathlib import Path

from loterias.settings import PROJECT_ROOT

logger = logging.getLogger(__name__)

TASK_NAME = "LoteriasEstatisticoAtualizacao"


def _python_executable() -> str:
    """Interpretador para a tarefa (``pythonw`` no Windows, para não abrir console)."""
    exe = Path(sys.executable)
    if platform.system() == "Windows":
        windowless = exe.with_name("pythonw.exe")
        if windowless.exists():
            return str(windowless)
    return str(exe)


def update_command() -> str:
    """Linha de comando que atualiza todas as loterias."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" atualizar'
    return f'"{_python_executable()}" "{PROJECT_ROOT / "main.py"}" atualizar'


def schedule_daily(time_hhmm: str = "21:30") -> tuple[bool, str]:
    """Agenda a atualização diária.

    Args:
        time_hhmm: Horário no formato ``HH:MM`` (padrão após os sorteios das 21h).

    Returns:
        ``(sucesso, mensagem para o usuário)``.
    """
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", time_hhmm):
        return False, "Horário inválido. Use HH:MM, por exemplo 21:30."
    if platform.system() != "Windows":
        hour, minute = time_hhmm.split(":")
        line = f"{int(minute)} {int(hour)} * * * {update_command()}"
        return True, f"Adicione esta linha com 'crontab -e':\n{line}"
    cmd = ["schtasks", "/Create", "/F", "/SC", "DAILY", "/ST", time_hhmm,
           "/TN", TASK_NAME, "/TR", update_command()]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.error("Falha ao executar schtasks: %s", exc)
        return False, f"Não foi possível agendar: {exc}"
    if proc.returncode != 0:
        logger.error("schtasks retornou %s: %s", proc.returncode, proc.stderr.strip())
        return False, f"Não foi possível agendar: {proc.stderr.strip() or proc.stdout.strip()}"
    logger.info("Atualização diária agendada às %s", time_hhmm)
    return True, f"Atualização diária agendada às {time_hhmm}."


def unschedule() -> tuple[bool, str]:
    """Remove a tarefa agendada (Windows) ou explica como remover do crontab."""
    if platform.system() != "Windows":
        return True, "Remova a linha correspondente com 'crontab -e'."
    try:
        proc = subprocess.run(["schtasks", "/Delete", "/F", "/TN", TASK_NAME],
                              capture_output=True, text=True, check=False, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.error("Falha ao executar schtasks: %s", exc)
        return False, f"Não foi possível remover: {exc}"
    if proc.returncode != 0:
        return False, proc.stderr.strip() or "Tarefa não encontrada."
    return True, "Agendamento removido."
