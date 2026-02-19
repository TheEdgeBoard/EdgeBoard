import requests
import sqlite3
import os
import sys
from datetime import datetime

# ... your API Keys and config ...

# --- DYNAMIC DB PATH ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'edgeboard.db')

def sync_box_scores():
    print("Starting Box Score Sync...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT,
            game_date TEXT,
            pts INTEGER,
            reb INTEGER,
            ast INTEGER,
            threes_made INTEGER,
            minutes_played INTEGER
        )
    ''')
    conn.commit()

    print("Identifying active players for today's slate...")
    players_in_db = cursor.execute("SELECT DISTINCT player_name FROM active_lines WHERE line_value IS NOT NULL").fetchall()
    
    if not players_in_db:
        return {"status": "error", "message": "No active players found. Please run 'Sync Odds' first."}

    count = 0
    
    # --- NEW: Disguise the script as a normal web browser ---
    custom_headers = {
        'Host': 'stats.nba.com',
        'Connection': 'keep-alive',
        'Accept': 'application/json, text/plain, */*',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Referer': 'https://www.nba.com/',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    for p in players_in_db:
        player_name = p['player_name']
        
        player_dict = players.find_players_by_full_name(player_name)
        if not player_dict:
            continue
            
        pid = player_dict[0]['id']
        
        try:
            time.sleep(1.0) # Increased to 1 full second to be extra polite to the NBA API
            # Injecting the custom headers into the request
            log = playergamelog.PlayerGameLog(player_id=pid, headers=custom_headers, timeout=10).get_data_frames()[0]
            
            if log.empty:
                continue

            cursor.execute("DELETE FROM player_logs WHERE player_name = ?", (player_name,))
            recent_games = log.head(14) 
            
            for _, row in recent_games.iterrows():
                cursor.execute('''
                    INSERT INTO player_logs (player_name, game_date, pts, reb, ast, threes_made, minutes_played)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    player_name, row['GAME_DATE'], int(row['PTS']), 
                    int(row['REB']), int(row['AST']), int(row['FG3M']), int(row['MIN'])
                ))
                count += 1
                
        except Exception as e:
            print(f"Error syncing {player_name}: {e}")
            continue

    conn.commit()
    conn.close()
    
    msg = f"Successfully synced {count} recent box scores for {len(players_in_db)} players."
    print(msg)
    return {"status": "success", "message": msg}

if __name__ == "__main__":
    sync_box_scores()