import sqlite3
import time
import os
import requests
from datetime import datetime
from dotenv import load_dotenv

# --- LOAD ENVIRONMENT VARIABLES ---
load_dotenv()

# --- CONFIGURATION ---
BDL_API_KEY = os.getenv('BDL_API_KEY') 
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'edgeboard.db')

# --- NAME MAPPING ---
NAME_MAP = {
    "R.J. Barrett": "RJ Barrett",
    "C.J. McCollum": "CJ McCollum",
    "Moe Wagner": "Moritz Wagner",
    "Jabari Smith Jr": "Jabari Smith",
    "Paul Reed Jr": "Paul Reed"
}

def sync_box_scores():
    print("🚀 Starting Balldontlie Box Score Sync (All-Star Tier)...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get active players from today's lines
    try:
        cursor.execute("SELECT DISTINCT player_name FROM active_lines")
        active_players = [row['player_name'] for row in cursor.fetchall()]
    except Exception as e:
        print(f"❌ Error reading active_lines: {e}")
        return

    headers = {'Authorization': BDL_API_KEY}

    for player_name in active_players:
        # Check mapping
        search_name = NAME_MAP.get(player_name, player_name)
        
        # --- FIX: New Balldontlie ID Lookup (Replaces old 'players' line) ---
        print(f"🔍 Searching ID for: {search_name}")
        try:
            player_res = requests.get(f"https://api.balldontlie.io/v1/players?search={search_name}", headers=headers)
            time.sleep(1.1) # All-Star Tier throttle
            
            if player_res.status_code == 200:
                p_data = player_res.json().get('data', [])
                if not p_data:
                    print(f"⚠️ {search_name} not found.")
                    continue
                
                player_id = p_data[0]['id']
                
                # Now fetch the last 14 games
                stats_res = requests.get(f"https://api.balldontlie.io/v1/stats?player_ids[]={player_id}&per_page=14", headers=headers)
                time.sleep(1.1)
                
                if stats_res.status_code == 200:
                    stats_data = stats_res.json().get('data', [])
                    
                    # Wipe old logs for this player to keep data fresh
                    cursor.execute("DELETE FROM player_logs WHERE player_name = ?", (player_name,))
                    
                    for game in stats_data:
                        cursor.execute('''
                            INSERT INTO player_logs (player_name, game_date, pts, reb, ast, threes_made)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (player_name, game['game']['date'], game['pts'], game['reb'], game['ast'], game['fg3m']))
                    
                    print(f"✅ Synced {len(stats_data)} games for {player_name}")
            
            elif player_res.status_code == 429:
                print("🛑 Rate limited! Cooling down for 30s...")
                time.sleep(30)
                
        except Exception as e:
            print(f"❌ Error syncing {player_name}: {e}")

    conn.commit()
    conn.close()
    print("🏁 Sync Complete!")

if __name__ == "__main__":
    sync_box_scores()