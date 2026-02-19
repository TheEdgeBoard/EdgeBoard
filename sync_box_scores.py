import sqlite3
import time
import pandas as pd
from datetime import datetime, timedelta
from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players

DB_PATH = '/home/TheEdgeBoard/EdgeBoard/edgeboard.db'

def sync_box_scores():
    print("Starting Box Score Sync...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # --- 1. SAFEGUARD: Build table if missing ---
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

    # --- 2. GET ACTIVE PLAYERS ---
    # We only want to pull box scores for players who actually have prop lines today
    print("Identifying active players for today's slate...")
    players_in_db = cursor.execute("SELECT DISTINCT player_name FROM active_lines WHERE line_value IS NOT NULL").fetchall()
    
    if not players_in_db:
        msg = "No active players found. Please run 'Sync Odds' first."
        print(msg)
        return {"status": "error", "message": msg}

    count = 0

    # --- 3. FETCH AND UPDATE LOGS ---
    for p in players_in_db:
        player_name = p['player_name']
        
        player_dict = players.find_players_by_full_name(player_name)
        if not player_dict:
            continue
            
        pid = player_dict[0]['id']
        
        try:
            time.sleep(0.6) # Prevent NBA API rate limiting
            log = playergamelog.PlayerGameLog(player_id=pid).get_data_frames()[0]
            
            if log.empty:
                continue

            # Clear out this specific player's old logs so we don't get duplicates
            cursor.execute("DELETE FROM player_logs WHERE player_name = ?", (player_name,))
            
            # Grab their 7 most recent games (safely covers a rolling 14-day window)
            recent_games = log.head(7) 
            
            for _, row in recent_games.iterrows():
                cursor.execute('''
                    INSERT INTO player_logs (player_name, game_date, pts, reb, ast, threes_made, minutes_played)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    player_name, 
                    row['GAME_DATE'], 
                    int(row['PTS']), 
                    int(row['REB']), 
                    int(row['AST']), 
                    int(row['FG3M']), 
                    int(row['MIN'])
                ))
                count += 1
                
            print(f"Synced recent box scores for {player_name}")
                
        except Exception as e:
            print(f"Error syncing box scores for {player_name}: {e}")

    conn.commit()
    conn.close()
    
    msg = f"Successfully synced {count} recent box scores for {len(players_in_db)} players."
    print(msg)
    return {"status": "success", "message": msg}

if __name__ == "__main__":
    sync_box_scores()