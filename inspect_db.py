import sqlite3, json, os

db_path = os.path.join(os.path.dirname(__file__), 'danzona_pos.db')
out_path = os.path.join(os.path.dirname(__file__), 'db_export.json')

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
out = {}
for t in tables:
    cols = [d[0] for d in c.execute('PRAGMA table_info(' + t + ')').fetchall()]
    rows = [dict(zip(cols, r)) for r in c.execute('SELECT * FROM ' + t).fetchall()]
    out[t] = rows

with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=2, default=str)

print('Exported to', out_path)
