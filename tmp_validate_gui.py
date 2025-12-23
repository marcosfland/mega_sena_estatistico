import time
import threading
import gui as G

# Dummy widgets
class DummyBar:
    def __init__(self):
        self.started = False
        self.stopped = False
    def start(self, val=0):
        print('DummyBar.start called')
        self.started = True
    def stop(self):
        print('DummyBar.stop called')
        self.stopped = True

class DummyLabel:
    def __init__(self):
        self.text = ''
    def config(self, **kwargs):
        self.text = kwargs.get('text', self.text)
        print('DummyLabel.config text=', self.text)

class DummyButton:
    def __init__(self):
        self.state = 'normal'
    def config(self, **kwargs):
        if 'state' in kwargs:
            self.state = kwargs['state']
            print('DummyButton config state=', self.state)

class DummyRoot:
    def __init__(self):
        self.cursor = ''
    def after(self, ms, func, *args):
        # Call immediately for test determinism
        func(*args)
    def config(self, cursor=''):
        self.cursor = cursor
        print('DummyRoot.cursor=', self.cursor)

# Inject dummies into module
G.root = DummyRoot()
G.progress_bar = DummyBar()
G.status_bar = DummyLabel()
btns = [DummyButton() for _ in range(3)]
G.interactive_buttons[:] = btns

# Run an analysis that completes quickly
G.run_analysis_gui('alltime')

# Wait for worker thread to finish (simple wait)
for i in range(20):
    # check if any thread other than main is alive that is not the interpreter thread
    alive = any(t.is_alive() and t.name != 'MainThread' for t in threading.enumerate())
    if not alive:
        break
    time.sleep(0.1)

print('After run: progress started=', G.progress_bar.started, 'stopped=', G.progress_bar.stopped)
print('Status text:', G.status_bar.text)
print('Buttons states:', [b.state for b in G.interactive_buttons])
print('Root cursor:', G.root.cursor)
