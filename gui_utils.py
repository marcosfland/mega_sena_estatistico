"""
Funções utilitárias para a interface gráfica do Mega-Sena Estatístico.
Inclui helpers de thread, mensagens, tooltips, etc.
"""
# Funções como show_message, ask_on_main_thread, Tooltip, open_file_location, run_in_thread, start_processing, etc, serão movidas para cá.

import tkinter as tk
from tkinter import messagebox
import threading
import logging
import os
import subprocess

root = None
status_bar = None
progress_bar = None
interactive_buttons = []

def show_message(title, message, is_error=False):
    try:
        is_main = threading.current_thread() is threading.main_thread()
    except Exception:
        is_main = True
    def _show():
        if status_bar:
            status_bar.config(text=message)
        if is_error:
            logging.error(f"{title}: {message}")
            messagebox.showerror(title, message)
        else:
            logging.info(f"{title}: {message}")
            messagebox.showinfo(title, message)
        if root and status_bar:
            root.after(5000, lambda: status_bar.config(text="Pronto") if status_bar else None)
    if is_main or root is None:
        _show()
    else:
        root.after(0, _show)

def ask_on_main_thread(func, *args, **kwargs):
    try:
        if threading.current_thread() is threading.main_thread() or root is None:
            return func(*args, **kwargs)
    except Exception:
        return func(*args, **kwargs)
    result = {}
    evt = threading.Event()
    def _call():
        try:
            result['value'] = func(*args, **kwargs)
        except Exception as e:
            result['exc'] = e
        finally:
            evt.set()
    root.after(0, _call)
    evt.wait()
    if 'exc' in result:
        raise result['exc']
    return result.get('value')

class Tooltip:
    def __init__(self, widget, text=""):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self._on_enter)
        widget.bind("<Leave>", self._on_leave)
    def _on_enter(self, event=None):
        self.showtip()
    def _on_leave(self, event=None):
        self.hidetip()
    def showtip(self):
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 10
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT, background="#ffffe0", relief=tk.SOLID, borderwidth=1, font=("tahoma", 8, "normal"))
        label.pack(ipadx=4, ipady=2)
    def hidetip(self):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None
    def set_text(self, text):
        self.text = text

def open_file_location(filepath):
    try:
        folder = os.path.dirname(os.path.abspath(filepath))
        if os.name == 'nt':
            os.startfile(folder)
        elif os.name == 'posix':
            subprocess.Popen(['xdg-open', folder])
        show_message("Local Aberto", f"A pasta de '{filepath}' foi aberta.", False)
    except Exception as e:
        show_message("Erro", f"Não foi possível abrir o local do arquivo: {e}", True)

def run_in_thread(func, *args, **kwargs):
    if status_bar:
        status_bar.config(text="Processando... Por favor, aguarde.")
    thread = threading.Thread(target=lambda: func(*args, **kwargs))
    thread.start()

def start_processing():
    try:
        if status_bar:
            status_bar.config(text="Processando... Por favor, aguarde.")
        if progress_bar:
            progress_bar.start(10)
        if root:
            try:
                root.config(cursor='watch')
            except Exception:
                root.config(cursor='')
        for b in interactive_buttons:
            try:
                b.config(state=tk.DISABLED)
            except Exception:
                pass
    except Exception as e:
        logging.warning(f"Erro ao iniciar indicador de processamento: {e}")
