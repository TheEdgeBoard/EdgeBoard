import sqlite3
import os

# Define the absolute path
path = '/home/TheEdgeBoard/EdgeBoard/edgeboard.db'
conn = sqlite3.connect(path)
c = conn.cursor()

print("Rebuilding users table to fix column mismatch...")

# 1. Drop the old table if it exists to clear the error
c.execute('DROP TABLE IF EXISTS users')

# 2. Create the table with the EXACT columns the app needs
c.execute('''CREATE TABLE users (
                username TEXT PRIMARY KEY, 
                password TEXT, 
                role TEXT, 
                full_name TEXT, 
                phone TEXT, 
                email TEXT)''')

# 3. Insert your Master Admin account
admin_data = ('admin', 'winning', 'admin', 'System Admin', '573-000-0000', 'admin@edgeboard.live')
c.execute('''INSERT INTO users (username, password, role, full_name, phone, email) 
             VALUES (?, ?, ?, ?, ?, ?)''', admin_data)

conn.commit()
conn.close()
print("✅ Table rebuilt. Admin 'admin' restored with password 'winning'.")