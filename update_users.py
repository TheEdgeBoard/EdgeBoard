import sqlite3

def setup_multi_user():
    conn = sqlite3.connect('edgeboard.db')
    c = conn.cursor()
    
    # Create the users table
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT)''')
    
    # Add your Admin account (Full Access)
    c.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?)", 
              ('admin', 'winning', 'admin'))
    
    # Add a Viewer account (Read-Only)
    c.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?)", 
              ('guest', 'viewonly', 'viewer'))
    
    conn.commit()
    conn.close()
    print("✅ User system updated with Roles.")

if __name__ == "__main__":
    setup_multi_user()