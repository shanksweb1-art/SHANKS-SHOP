import sqlite3

conn = sqlite3.connect('danzona_pos.db')
cols = [
    ('wholesale_price', 'REAL DEFAULT 0'),
    ('min_stock', 'REAL DEFAULT 0'),
    ('max_stock', 'REAL DEFAULT 0'),
    ('batch_number', 'TEXT'),
    ('status', "TEXT DEFAULT 'active'"),
    ('supplier_id', 'INTEGER'),
    ('tax_type', "TEXT DEFAULT 'vat'"),
    ('tax_rate', 'REAL DEFAULT 7.5'),
    ('tax_inclusive', 'INTEGER DEFAULT 0'),
    ('tax_group', "TEXT DEFAULT 'pharmaceuticals'"),
    ('image', 'TEXT'),
    ('images', 'TEXT'),
]

for col_name, col_type in cols:
    try:
        conn.execute(f'ALTER TABLE products ADD COLUMN {col_name} {col_type}')
        print(f'OK: {col_name}')
    except Exception as e:
        print(f'SKIP: {col_name} - {e}')

conn.commit()
conn.close()
print('Done')
