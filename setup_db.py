import sqlite3
import hashlib

def create_database():
    # This creates the file 'edgeboard.db' if it doesn't exist
    conn = sqlite3.connect('edgeboard.db')
    c = conn.cursor()

    print("🛠️  Building Database Structure...")

    # 1. USERS TABLE (For your Login Page)
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        access_level TEXT DEFAULT 'user'
    )''')

    # 2. ACTIVE LINES TABLE (Current Odds from the Bookies)
    c.execute('''CREATE TABLE IF NOT EXISTS active_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_name TEXT NOT NULL,
        team TEXT,
        opponent TEXT,
        prop_type TEXT NOT NULL, 
        line_value REAL NOT NULL, 
        odds_over INTEGER, 
        game_time TEXT,
        merchant_name TEXT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # 3. PLAYER LOGS (Historical Stats for Simulations)
    c.execute('''CREATE TABLE IF NOT EXISTS player_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_name TEXT NOT NULL,
        game_date TEXT,
        pts INTEGER,
        reb INTEGER,
        ast INTEGER,
        threes_made INTEGER,
        minutes_played REAL
    )''')

    # 4. TEAM METRICS (Pace & Defense for Adjustments)
    c.execute('''CREATE TABLE IF NOT EXISTS team_metrics (
        team_abbrev TEXT PRIMARY KEY, 
        pace REAL, 
        defensive_rating REAL 
    )''')

    # 5. SIMULATION RESULTS (The Final Output for the Dashboard)
    c.execute('''CREATE TABLE IF NOT EXISTS sim_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_name TEXT,
        prop_type TEXT,
        projected_value REAL, 
        win_probability REAL, 
        ev_edge REAL,         
        FOREIGN KEY (player_name) REFERENCES active_lines(player_name)
    )''')

    # --- Create the Default Admin User ---
    # Username: admin | Password: winning
    default_pass = hashlib.sha256("winning".encode()).hexdigest()
    try:
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", ('admin', default_pass))
        print("👤 Admin user created (User: admin / Pass: winning)")
    except sqlite3.IntegrityError:
        print("👤 Admin user already exists.")

    conn.commit()
    conn.close()
    print("✅ SUCCESS: Database 'edgeboard.db' created with 5 tables.")

if __name__ == "__main__":
    create_database()