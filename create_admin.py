import sqlite3
import os
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'edgeboard.db')

def create_admin():
    print("🔐 EdgeBoard Admin Creation Tool")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    username = input("Enter new admin username: ")
    password = input("Enter new admin password: ")
    
    hashed_password = generate_password_hash(password)

    try:
        cursor.execute('''
            INSERT INTO users (username, password_hash, access_level) 
            VALUES (?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                password_hash=excluded.password_hash,
                access_level=excluded.access_level
        ''', (username, hashed_password, 'admin'))
        
        conn.commit()
        print(f"✅ Admin '{username}' successfully added or updated!")
    except Exception as e:
        print(f"❌ Error inserting user: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    create_admin()