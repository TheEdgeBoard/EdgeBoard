import sqlite3
import os

path = '/home/TheEdgeBoard/EdgeBoard/edgeboard.db'
conn = sqlite3.connect(path)
c = conn.cursor()

# This ensures the admin has all the required data for the new app.py
admin_data = ('admin', 'winning', 'admin', 'System Admin', '000-000-0000', 'your-email@gmail.com')

# Clear any old broken admin and insert the fresh one
c.execute('DELETE FROM users WHERE username = "admin"')
c.execute('''INSERT INTO users (username, password, role, full_name, phone, email) 
             VALUES (?, ?, ?, ?, ?, ?)''', admin_data)

conn.commit()
conn.close()
print("✅ Admin account restored with 'winning' password.")