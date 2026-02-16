import sqlite3
import os

def init_db():
    db_path = '/home/TheEdgeBoard/EdgeBoard/edgeboard.db'
    if not os.path.exists('/home/TheEdgeBoard/EdgeBoard/'):
        os.makedirs('/home/TheEdgeBoard/EdgeBoard/')

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Configuring Database for Multi-Sim Engine...")

    # DROP TABLES to ensure new columns are added
    cursor.execute('DROP TABLE IF EXISTS daily_prospects')
    cursor.execute('DROP TABLE IF EXISTS sim_results')

    # 1. INPUTS: Raw Stats for all 4 Timeframes
    cursor.execute('''CREATE TABLE daily_prospects (
        player_id INTEGER, player_name TEXT, team_id TEXT, opponent_id TEXT, prop_type TEXT,
        market_line REAL, implied_prob_over REAL, implied_prob_under REAL,
        score_last_game REAL,
        
        -- Averages for Simulations
        avg_last_3 REAL, avg_last_5 REAL, avg_last_10 REAL, avg_last_14 REAL, avg_season REAL,
        
        -- Hit Counts for Display
        hits_last_3_over INTEGER, hits_last_3_under INTEGER,
        hits_last_5_over INTEGER, hits_last_5_under INTEGER,
        hits_last_10_over INTEGER, hits_last_10_under INTEGER,
        hits_last_14_over INTEGER, hits_last_14_under INTEGER
    )''')

    # 2. OUTPUTS: 4 Distinct Simulations per Player
    cursor.execute('''CREATE TABLE sim_results (
        player_name TEXT, team TEXT, prop_type TEXT, line_value REAL,
        
        -- SIM A: LAST 3 GAMES
        ev_3 REAL, win_rate_3 REAL, proj_3 REAL,
        
        -- SIM B: LAST 5 GAMES
        ev_5 REAL, win_rate_5 REAL, proj_5 REAL,
        
        -- SIM C: LAST 10 GAMES
        ev_10 REAL, win_rate_10 REAL, proj_10 REAL,
        
        -- SIM D: LAST 14 GAMES
        ev_14 REAL, win_rate_14 REAL, proj_14 REAL,
        
        -- HIT COUNTS (Passed through for frontend filtering)
        hits_3_over INTEGER, hits_3_under INTEGER,
        hits_5_over INTEGER, hits_5_under INTEGER,
        hits_10_over INTEGER, hits_10_under INTEGER,
        hits_14_over INTEGER, hits_14_under INTEGER,
        
        suggestion TEXT, -- "OVER" or "UNDER"
        context_tags TEXT
    )''')
    
    # User Tables (Preserved)
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, full_name TEXT, email TEXT, phone TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS pending_users (username TEXT, password TEXT, role TEXT, full_name TEXT, email TEXT, phone TEXT, code TEXT)''')

    conn.commit()
    conn.close()
    print("SUCCESS: Database initialized for Multi-Sim Engine.")

if __name__ == "__main__":
    init_db()