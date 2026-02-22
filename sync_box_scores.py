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

# --- UPDATE THIS SECTION ---
NAME_MAP = {
    "GG Jackson": "Gregory Jackson II",
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
        
        # Split name for a more reliable search
        parts = search_name.split()
        first_name = parts[0]
        last_name = parts[-1]

        # --- NEW LOGIC: FORCE GG JACKSON ID AND SKIP SEARCH ---
        player_id = None
        if "Gregory Jackson" in search_name or "GG Jackson" in search_name:
            player_id = 56677830
            print(f"🎯 Using Hardcoded ID for: {search_name} ({player_id})")

        try:
            # Only search if we don't already have an ID
            if not player_id:
                print(f"🔍 Searching ID for: {search_name}")
                # Search by FIRST and LAST NAME
                url = f"https://api.balldontlie.io/v1/players?first_name={first_name}&last_name={last_name}"
                player_res = requests.get(url, headers=headers)
                time.sleep(1.1) 
                
                if player_res.status_code == 200:
                    p_data = player_res.json().get('data', [])
                    
                    # If that specific first/last combo fails, try just a general search
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
                
                elif player_res.status_code == 429:
                    print("🛑 Rate limited during search! Cooling down for 30s...")
                    time.sleep(30)
                    continue
                else:
                    print(f"❌ Search Error {player_res.status_code} for {player_name}")
                    continue

            # --- NOW FETCH STATS USING THE PLAYER_ID (Hardcoded or Searched) ---
            # We need to get the team info first for the flipping logic
            if "Gregory Jackson" in search_name or "GG Jackson" in search_name:
                p_info_res = requests.get(f"https://api.balldontlie.io/v1/players/{player_id}", headers=headers)
                p_info = p_info_res.json().get('data', {})
            else:
                p_info = p_data[0] # Already had it from search

            # --- Fix the Team/Opponent Mapping Bug ---
            true_team = p_info['team']['abbreviation']
            cursor.execute("SELECT team, opponent FROM active_lines WHERE player_name = ?", (player_name,))
            row = cursor.fetchone()
            
            if row:
                api_team, api_opp = row['team'], row['opponent']
                if true_team == api_opp:
                    cursor.execute('''
                        UPDATE active_lines 
                        SET team = ?, opponent = ? 
                        WHERE player_name = ?
                    ''', (true_team, api_team, player_name))
                    print(f"    🔄 Flipped mismatch: {player_name} plays for {true_team}, not {api_team}")
            
            # --- FETCH ALL SEASON STATS (INCLUDING 2026) THEN TRUNCATE TO 14 ---
            all_season_stats = []
            cursor_id = None
            
            print(f"📊 Pulling 2025-26 logs for {player_name} to find last 14...")
            
            while True:
                stats_url = f"https://api.balldontlie.io/nba/v1/stats?player_ids[]={player_id}&seasons[]=2025&per_page=100"
                if cursor_id:
                    stats_url += f"&cursor={cursor_id}"
                
                stats_res = requests.get(stats_url, headers=headers)
                time.sleep(1.1) 
                
                if stats_res.status_code == 200:
                    res_json = stats_res.json()
                    all_season_stats.extend(res_json.get('data', []))
                    
                    cursor_id = res_json.get('meta', {}).get('next_cursor')
                    if not cursor_id:
                        break
                elif stats_res.status_code == 429:
                    print("🛑 Rate limited! Cooling down for 30s...")
                    time.sleep(30)
                else:
                    break

            if all_season_stats:
                # 1. SORT all games by date (Newest first)
                all_season_stats.sort(key=lambda x: x['game']['date'], reverse=True)

                # 2. TAKE ONLY THE TOP 14 (The most recent ones)
                recent_14 = all_season_stats[:14]

                # 3. SAVE ONLY THESE 14 TO THE DATABASE
                cursor.execute("DELETE FROM player_logs WHERE player_name = ?", (player_name,))
                
                for game in recent_14:
                    clean_date = game['game']['date'].split('T')[0]
                    cursor.execute('''
                        INSERT INTO player_logs (player_name, game_date, pts, reb, ast, threes_made)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (player_name, clean_date, game['pts'], game['reb'], game['ast'], game['fg3m']))
                
                print(f"✅ Synced {len(recent_14)} most recent games for {player_name}")

        except Exception as e:
            print(f"❌ Error syncing {player_name}: {e}")

    conn.commit()
    conn.close()
    print("🏁 Sync Complete!")

if __name__ == "__main__":
    sync_box_scores()