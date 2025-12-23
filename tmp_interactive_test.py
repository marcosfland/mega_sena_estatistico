import os, tempfile, time, threading
import tkinter as tk
from unittest.mock import patch

import mega_sena_app as app
import gui as G

# Setup temp DB with sample draws
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
    # Insert several sample draws
    for i in range(1, 8):
        d = f"0{i}/01/2025"
        nums = [(i % 60) + 1, ((i+1) % 60) + 1, ((i+2) % 60) + 1, ((i+3) % 60) + 1, ((i+4) % 60) + 1, ((i+5) % 60) + 1]
        cur.execute("INSERT OR IGNORE INTO megasena(concurso, data, dez1,dez2,dez3,dez4,dez5,dez6) VALUES (?,?,?,?,?,?,?,?)", (i, d, *nums))
    conn.commit()

# Create a real Tk root but keep it withdrawn (no visible windows)
root = tk.Tk()
root.withdraw()
G.root = root

# Minimal status bar and progress bar objects
class StatusBar:
    def __init__(self): self.text = ''
    def config(self, **k): self.text = k.get('text', self.text)

class ProgressBar:
    def __init__(self): self.running=False
    def start(self, *_): self.running=True
    def stop(self): self.running=False

G.status_bar = StatusBar()
G.progress_bar = ProgressBar()

# Dummy interactive button
class DummyButton:
    def __init__(self): self.state='normal'
    def config(self, **k): self.state = k.get('state', self.state)

btn = DummyButton()
G.interactive_buttons.clear()
G.interactive_buttons.append(btn)

# Ensure GUI uses our temp DB for draw loading
G.load_all_draws = lambda: app.load_all_draws(path)

# We'll schedule the test sequence using root.after so mainloop runs on the main thread.
# This avoids RuntimeError: main thread is not in main loop when worker threads call root.after.

def run_export_then_next():
    with patch('gui.simpledialog.askstring', return_value='frequencia'):
        with patch('gui.filedialog.asksaveasfilename', return_value=tempfile.mktemp(suffix='.csv')):
            G.export_data_gui(advanced=True)
    # wait for background threads to finish
    root.after(50, check_export_completion)

def check_export_completion():
    alive = any(t.is_alive() and t.name!='MainThread' for t in threading.enumerate())
    if alive:
        root.after(50, check_export_completion)
    else:
        print('Export advanced: status=', G.status_bar.text)
        root.after(0, run_backtest_then_next)

def run_backtest_then_next():
    G.run_backtest_gui(method='weighted')
    # run_backtest_gui schedules result display via root.after; give it time
    root.after(200, check_backtest_completion)

def check_backtest_completion():
    # backtest is generally synchronous but might have scheduled callbacks
    print('Backtest done; status=', G.status_bar.text)
    root.after(0, run_monte_then_finish)

def run_monte_then_finish():
    G.run_analysis_gui('montecarlo')
    root.after(50, check_monte_completion)

def check_monte_completion():
    alive = any(t.is_alive() and t.name!='MainThread' for t in threading.enumerate())
    if alive:
        root.after(50, check_monte_completion)
    else:
        print('Monte Carlo: status=', G.status_bar.text)
        # End of sequence
        root.quit()

# Start the sequence and enter mainloop so that root.after callbacks work.
root.after(0, run_export_then_next)
root.mainloop()

# Cleanup
try:
    root.destroy()
except Exception:
    pass
try:
    os.unlink(path)
except Exception:
    pass
