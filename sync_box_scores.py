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
        
    # --- ADD THESE TWO LINES HERE ---
    total_players = len(active_players)
    counter = 0
    print(f"📋 Identified {total_players} players to sync for today's slate.")

    headers = {'Authorization': BDL_API_KEY}

    for player_name in active_players:
        # --- ADD THIS LINE HERE ---
        counter += 1
        
        search_name = NAME_MAP.get(player_name, player_name)
        # Check mapping
        search_name = NAME_MAP.get(player_name, player_name)
        
        # Split name for a more reliable search
        parts = search_name.split()
        first_name = parts[0]
        last_name = parts[-1]

        print(f"🔍 Searching ID for: {search_name}")
        try:
            # Search by LAST NAME only to be safe
            url = f"https://api.balldontlie.io/v1/players?first_name={first_name}&last_name={last_name}"
            player_res = requests.get(url, headers=headers)
            time.sleep(1.1) 
            
            if player_res.status_code == 200:
                p_data = player_res.json().get('data', [])
                
                # If that specific first/last combo fails, try just last_name
                if not p_data:
                    url = f"https://api.balldontlie.io/v1/players?search={last_name}"
                    player_res = requests.get(url, headers=headers)
                    time.sleep(1.1)
                    p_data = player_res.json().get('data', [])

                if not p_data:
                    print(f"⚠️ {search_name} not found.")
                    continue
                
                # Match the first player in the list
                player_id = p_data[0]['id']
                # --- NEW: Fix the Team/Opponent Mapping Bug ---
                true_team = p_data[0]['team']['abbreviation']
                cursor.execute("SELECT team, opponent FROM active_lines WHERE player_name = ?", (player_name,))
                row = cursor.fetchone()
                
                if row:
                    api_team, api_opp = row['team'], row['opponent']
                    # If the true team from Balldontlie matches the opponent column, flip them!
                    if true_team == api_opp:
                        cursor.execute('''
                            UPDATE active_lines 
                            SET team = ?, opponent = ? 
                            WHERE player_name = ?
                        ''', (true_team, api_team, player_name))
                        print(f"   🔄 Flipped mismatch: {player_name} plays for {true_team}, not {api_team}")
                # ----------------------------------------------
                # ... (rest of your stats_res code remains the same)
                
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