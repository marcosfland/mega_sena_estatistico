"""Helper module for GUI-related DB selection (keeps gui.py smaller)."""
from typing import Optional
import logging
from tkinter import filedialog
from config import get_config
import mega_sena_app as app


def select_db_gui(label_widget: Optional[object] = None, parent=None):
    """Abre um diálogo para selecionar/criar uma base de dados SQLite e persiste a escolha."""
    try:
        file_path = filedialog.asksaveasfilename(defaultextension='.db', filetypes=[('SQLite DB','*.db'),('All files','*.*')], parent=parent)
        if not file_path:
            return None

        cfg = get_config()
        cfg.set('DATABASE', 'path', file_path)
        cfg.save_config()

        # Atualizar caminho global na aplicação
        try:
            app.set_db_path(file_path)
        except Exception as e:
            logging.warning(f"Não foi possível atualizar DB_PATH em runtime: {e}")

        if label_widget:
            try:
                label_widget.config(text=f"Base de Dados: {file_path}")
            except Exception:
                pass

        return file_path
    except Exception as e:
        logging.error(f"Erro no seletor de DB: {e}")
        return None
