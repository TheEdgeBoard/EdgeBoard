import sqlite3
import os

def init_db():
    # Ensure the directory exists
    db_path = '/home/TheEdgeBoard/EdgeBoard/edgeboard.db'
    if not os.path.exists('/home/TheEdgeBoard/EdgeBoard/'):
        os.makedirs('/home/TheEdgeBoard/EdgeBoard/')
        print("Created directory.")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Configuring Database...")

    # --- 1. RESET DATA TABLES ---
    # We drop these to ensure they are rebuilt with the NEW columns (hits_last_6, etc.)
    cursor.execute('DROP TABLE IF EXISTS daily_prospects')
    cursor.execute('DROP TABLE IF EXISTS sim_results')
    print("Old data tables cleared.")

    # --- 2. CREATE TABLE: DAILY PROSPECTS (The Input) ---
    cursor.execute('''CREATE TABLE daily_prospects (
        player_id INTEGER,
        player_name TEXT,
        team_id TEXT,
        opponent_id TEXT,
        prop_type TEXT,
        market_line REAL,
        implied_prob_over REAL,
        implied_prob_under REAL,
        score_last_game REAL,       -- NEW: Momentum Check
        hits_last_6_over INTEGER,   -- NEW: Consistency Check
        hits_last_6_under INTEGER,  -- NEW: Consistency Check
        avg_last_6 REAL,
        avg_season REAL
    )''')

    # --- 3. CREATE TABLE: SIM RESULTS (The Output) ---
    cursor.execute('''CREATE TABLE sim_results (
        player_name TEXT,
        team TEXT,
        prop_type TEXT,
        line_value REAL,
        suggestion TEXT,            -- NEW: "OVER" or "UNDER"
        projected_value REAL,
        win_rate REAL,              -- NEW: 60% Confidence Threshold
        ev_edge REAL,
        context_tags TEXT
    )''')

    # --- 4. CREATE USER TABLES (Keep Existing Data) ---
    # We use IF NOT EXISTS here so we don't delete your current admin/users
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY, 
        password TEXT, 
        role TEXT, 
        full_name TEXT, 
        email TEXT, 
        phone TEXT
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS pending_users (
        username TEXT, 
        password TEXT, 
        role TEXT, 
        full_name TEXT, 
        email TEXT, 
        phone TEXT, 
        code TEXT
    )''')

    conn.commit()
    conn.close()
    print("SUCCESS: Database initialized with High-Conviction schema.")

if __name__ == "__main__":
    init_db()