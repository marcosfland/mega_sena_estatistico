"""Execução de tarefas em segundo plano sem travar a interface.

O Tkinter não é thread-safe: widgets só podem ser tocados na thread principal.
O :class:`TaskRunner` roda a função numa thread e devolve resultado, erro e
progresso por uma fila, que é lida periodicamente na thread da interface.
"""

from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

Callback = Callable[[Any], None]


@dataclass
class _Message:
    """Mensagem trocada entre a thread de trabalho e a interface."""

    kind: str
    callback: Optional[Callable[..., None]]
    payload: tuple[Any, ...]


class TaskRunner:
    """Agenda funções em threads e despacha callbacks na thread da interface.

    Args:
        widget: Qualquer widget Tk (usado para ``after``).
        poll_ms: Intervalo de leitura da fila.
    """

    def __init__(self, widget: Any, poll_ms: int = 60) -> None:
        self._widget = widget
        self._poll_ms = poll_ms
        self._queue: "queue.Queue[_Message]" = queue.Queue()
        self._closed = False
        self._after_id: Optional[str] = None
        self._poll()

    def submit(self, fn: Callable[..., Any], *args: Any,
               on_success: Optional[Callback] = None,
               on_error: Optional[Callable[[BaseException], None]] = None,
               on_progress: Optional[Callable[..., None]] = None,
               on_done: Optional[Callable[[], None]] = None,
               with_progress: bool = False) -> threading.Thread:
        """Executa ``fn(*args)`` numa thread daemon.

        Args:
            fn: Função a executar.
            *args: Argumentos posicionais.
            on_success: Recebe o retorno (thread da interface).
            on_error: Recebe a exceção (thread da interface).
            on_progress: Recebe os argumentos passados a ``progress(...)``.
            on_done: Sempre chamado ao final (sucesso ou erro).
            with_progress: Passa ``progress=`` para ``fn``, que repassa à interface.
        """
        def report(*values: Any) -> None:
            self._queue.put(_Message("progress", on_progress, values))

        def work() -> None:
            try:
                kwargs = {"progress": report} if with_progress else {}
                result = fn(*args, **kwargs)
            except ValueError as exc:  # validação: mensagem para o usuário, sem traceback
                logger.warning("Tarefa recusou os parâmetros: %s", exc)
                self._queue.put(_Message("error", on_error, (exc,)))
            except Exception as exc:  # noqa: BLE001 - repassado à interface e logado
                logger.exception("Tarefa em segundo plano falhou: %s", getattr(fn, "__name__", fn))
                self._queue.put(_Message("error", on_error, (exc,)))
            else:
                self._queue.put(_Message("success", on_success, (result,)))
            finally:
                self._queue.put(_Message("done", on_done, ()))

        thread = threading.Thread(target=work, daemon=True,
                                  name=f"task-{getattr(fn, '__name__', 'fn')}")
        thread.start()
        return thread

    def _poll(self) -> None:
        """Despacha as mensagens pendentes e reagenda a leitura."""
        while True:
            try:
                message = self._queue.get_nowait()
            except queue.Empty:
                break
            if message.callback is None:
                continue
            try:
                message.callback(*message.payload)
            except Exception:  # noqa: BLE001 - um callback com erro não derruba os demais
                logger.exception("Callback da interface falhou (%s)", message.kind)
        if not self._closed:
            self._after_id = self._widget.after(self._poll_ms, self._poll)

    def close(self) -> None:
        """Para a leitura da fila (chamar ao fechar a janela)."""
        self._closed = True
        if self._after_id is not None:
            try:
                self._widget.after_cancel(self._after_id)
            except Exception as exc:  # noqa: BLE001 - janela já destruída
                logger.debug("after_cancel ignorado: %s", exc)
