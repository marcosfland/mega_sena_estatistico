import tempfile, os, time, traceback, sqlite3
from mega_sena_app import init_db

# Test direct sqlite use
f = tempfile.NamedTemporaryFile(delete=False)
path = f.name
f.close()
print('Temp (sqlite raw):', path)
conn = sqlite3.connect(path)
conn.execute('CREATE TABLE IF NOT EXISTS test (id INTEGER)')
conn.commit()
conn.close()
try:
    os.unlink(path)
    print('Removed OK (sqlite raw)')
except Exception as e:
    print('Remove failed (sqlite raw):', e)
    traceback.print_exc()

# Test using init_db
f = tempfile.NamedTemporaryFile(delete=False)
path2 = f.name
f.close()
print('Temp (init_db):', path2)
init_db(path2)
print('Init done')
print('Exists after init:', os.path.exists(path2))
try:
    os.unlink(path2)
    print('Removed OK (init_db)')
except Exception as e:
    print('Remove failed (init_db):', e)
    traceback.print_exc()