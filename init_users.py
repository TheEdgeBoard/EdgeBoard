import sqlite3
import os

# This ensures the script works whether you are on Windows or Linux
base_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(base_dir, 'edgeboard.db')

def initialize():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Create the table if it doesn't exist
    c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT)')
    
    # Define your accounts
    users = [
        ('admin', 'winning', 'admin'),
        ('viewer', 'nba2026', 'viewer')
    ]
    
    c.executemany('INSERT OR REPLACE INTO users VALUES (?, ?, ?)', users)
    conn.commit()
    conn.close()
    print("✅ Local User Database Initialized.")

if __name__ == "__main__":
    initialize()