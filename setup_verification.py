import sqlite3
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(base_dir, 'edgeboard.db')

conn = sqlite3.connect(db_path)
c = conn.cursor()

# Create table for users who haven't entered their code yet
c.execute('''CREATE TABLE IF NOT EXISTS pending_users 
             (username TEXT PRIMARY KEY, password TEXT, role TEXT, 
              full_name TEXT, phone TEXT, email TEXT, code TEXT)''')

conn.commit()
conn.close()
print("✅ Verification table created.")