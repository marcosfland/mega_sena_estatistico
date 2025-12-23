import os, tempfile, threading, time
import mega_sena_app as app
import gui as G
from unittest.mock import patch

# Create temp DB and insert some draws
f = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
path = f.name
f.close()
app.init_db(path)
try:
    app.set_db_path(path)
except Exception:
    app.DB_PATH = path

with app.open_db(path) as conn:
    cur = conn.cursor()
    # Insert multiple draws
    for i in range(1, 11):
        cur.execute("INSERT OR IGNORE INTO megasena(concurso, data, dez1,dez2,dez3,dez4,dez5,dez6) VALUES (?,?,?,?,?,?,?,?)",
                    (i, f'0{i}/01/2025', i, (i+1)%60+1, (i+2)%60+1, (i+3)%60+1, (i+4)%60+1, (i+5)%60+1))
    conn.commit()

# Dummy root and widgets
class DummyRoot:
    def after(self, ms, func, *args):
        func(*args)
    def config(self, **kwargs):
        pass

G.root = DummyRoot()
G.status_bar = type('S', (), {'config': lambda self, **k: None})()
G.progress_bar = type('P', (), {'start': lambda self, x: print('progress start'), 'stop': lambda self: print('progress stop')})()
# dummy interactive button
class DummyButton:
    def __init__(self): self.state = 'normal'
    def config(self, **k): self.state = k.get('state', self.state)

btn = DummyButton()
G.interactive_buttons.clear()
G.interactive_buttons.append(btn)

# Ensure GUI functions use our temp DB
G.load_all_draws = lambda: app.load_all_draws(path)

# Run backtest GUI (synchronous)
print('Running backtest GUI...')
G.run_backtest_gui('weighted')
print('Backtest GUI done; button state:', btn.state)

# Run montecarlo analysis (asynchronous via run_in_thread)
print('Running Monte Carlo via run_analysis_gui...')
G.run_analysis_gui('montecarlo')
# wait for background thread to finish
for _ in range(100):
    alive = any(t.is_alive() and t.name!='MainThread' for t in threading.enumerate())
    if not alive:
        break
    time.sleep(0.1)
print('Monte Carlo simulated; button state:', btn.state)

# Cleanup
try:
    os.unlink(path)
except Exception:
    pass
