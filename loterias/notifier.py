"""Notificações do sistema operacional, sem dependências extras.

* Windows: notificação nativa (toast) via PowerShell e WinRT.
* macOS: ``osascript``.
* Linux: ``notify-send`` (libnotify), se instalado.

Título e mensagem são passados por variáveis de ambiente/argumentos, nunca
interpolados no script, para evitar injeção de comandos.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess

logger = logging.getLogger(__name__)

_POWERSHELL_TOAST = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$texts = $template.GetElementsByTagName('text')
$texts.Item(0).AppendChild($template.CreateTextNode($env:LOTERIAS_TITLE)) > $null
$texts.Item(1).AppendChild($template.CreateTextNode($env:LOTERIAS_MESSAGE)) > $null
$toast = [Windows.UI.Notifications.ToastNotification]::new($template)
$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show($toast)
"""  # noqa: E501 - script PowerShell, linhas longas por natureza

_OSASCRIPT = ("on run argv\n"
              "display notification (item 2 of argv) with title (item 1 of argv)\n"
              "end run")


def _command(title: str, message: str) -> tuple[list[str], dict[str, str]] | None:
    """Comando e ambiente para o sistema atual (``None`` se não houver suporte)."""
    system = platform.system()
    env = dict(os.environ)
    if system == "Windows":
        env.update(LOTERIAS_TITLE=title, LOTERIAS_MESSAGE=message)
        return ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-WindowStyle", "Hidden", "-Command", _POWERSHELL_TOAST], env
    if system == "Darwin":
        return ["osascript", "-e", _OSASCRIPT, title, message], env
    if shutil.which("notify-send"):
        return ["notify-send", "--app-name=Loterias", title, message], env
    return None


def notify(title: str, message: str) -> bool:
    """Mostra uma notificação do sistema.

    Args:
        title: Título (ex.: "Mega-Sena 3071: jogo premiado!").
        message: Detalhe.

    Returns:
        ``True`` se o comando de notificação rodou sem erro.
    """
    built = _command(title[:120], message[:300])
    if built is None:
        logger.info("Notificação do sistema indisponível: %s — %s", title, message)
        return False
    cmd, env = built
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=20,
                              check=False, creationflags=flags)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("Falha ao exibir notificação: %s", exc)
        return False
    if proc.returncode != 0:
        logger.warning("Notificação retornou %s: %s", proc.returncode, proc.stderr.strip())
        return False
    return True
