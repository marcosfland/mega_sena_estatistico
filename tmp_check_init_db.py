import tempfile, os, sqlite3
import mega_sena_app as app
f=tempfile.NamedTemporaryFile(delete=False,suffix='.db')
path=f.name
f.close()
print('path',path,'exists_before',os.path.exists(path),'size_before',os.path.getsize(path))
app.init_db(path)
print('after init exists',os.path.exists(path),'size',os.path.getsize(path))
try:
    with sqlite3.connect(path) as conn:
        cur=conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        print('tables',cur.fetchall())
except Exception as e:
    print('error listing tables',e)
# cleanup
try:
    os.unlink(path)
except Exception:
    pass
