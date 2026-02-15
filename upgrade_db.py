import sqlite3
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(base_dir, 'edgeboard.db')

conn = sqlite3.connect(db_path)
c = conn.cursor()

# Adding new columns to existing table
try:
    c.execute('ALTER TABLE users ADD COLUMN full_name TEXT')
    c.execute('ALTER TABLE users ADD COLUMN phone TEXT')
    c.execute('ALTER TABLE users ADD COLUMN email TEXT')
    conn.commit()
    print("✅ Database columns added.")
except sqlite3.OperationalError:
    print("ℹ️ Columns already exist.")

conn.close()