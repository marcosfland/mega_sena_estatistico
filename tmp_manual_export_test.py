import os, tempfile, threading, time
import mega_sena_app as app
import gui as G
import gui_db
from unittest.mock import patch

# Create temp DB and insert some draws
f = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
path = f.name
f.close()
app.init_db(path)
# Insert sample draws
with app.open_db(path) as conn:
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO megasena(concurso, data, dez1,dez2,dez3,dez4,dez5,dez6) VALUES (?,?,?,?,?,?,?,?)", (1, '2025-01-01',1,2,3,4,5,6))
    conn.commit()

# Dummy root to execute scheduled UI calls synchronously
class DummyRoot:
    def after(self, ms, func, *args):
        func(*args)
    def config(self, **kwargs):
        pass

G.root = DummyRoot()
G.status_bar = type('S', (), {'config': lambda self, **k: None})()
G.progress_bar = type('P', (), {'start': lambda self, x: None, 'stop': lambda self: None})()

# Patch dialogs
with patch('gui.simpledialog.askstring', return_value='frequencia'):
    with patch('gui.filedialog.asksaveasfilename', return_value=tempfile.mktemp(suffix='.csv')):
        # Call export_data_gui(advanced=True) and wait briefly
        G.export_data_gui(advanced=True)
        # wait for background thread to finish
        for _ in range(20):
            alive = any(t.is_alive() and t.name!='MainThread' for t in threading.enumerate())
            if not alive:
                break
            time.sleep(0.1)

print('Export advanced simulated; check temp folder for output')

# Cleanup
try:
    os.unlink(path)
except Exception:
    pass
