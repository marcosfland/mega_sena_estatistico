import time
import gui
from mega_sena_app import load_all_draws
import tempfile, os

# Prepare fake draws
import datetime

def fake_draws():
    return [(datetime.date(2025,1,1), [1,2,3,4,5,6]), (datetime.date(2025,1,8), [1,2,7,8,9,10])]

# Monkeypatch load_all_draws
gui.load_all_draws = lambda: fake_draws()

# Create temp file for output
temp = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
path = temp.name
temp.close()
print('Temp file path:', path)

# Patch ask_on_main_thread to return our choices

def ask_override(func, *args, **kwargs):
    name = getattr(func, '__name__', '')
    if 'askstring' in name:
        return 'frequencia'
    if 'asksaveasfilename' in name:
        return path
    return func(*args, **kwargs)

# Replace helper
gui.ask_on_main_thread = ask_override

# Trigger advanced export
gui.export_data_gui(advanced=True)

# Wait for background thread to finish
for _ in range(50):
    import threading
    alive = any(t.is_alive() and t.name != 'MainThread' for t in threading.enumerate())
    if not alive:
        break
    time.sleep(0.1)

print('Done, exists:', os.path.exists(path))
if os.path.exists(path):
    with open(path, 'r', encoding='utf-8') as f:
        print(f.read()[:500])
else:
    print('File not created')
