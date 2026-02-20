import requests
import sqlite3
import os
import sys
from datetime import datetime

# --- CONFIGURATION ---
API_KEY = 'bfcd3c1188c7060e3547925d9df6cd32' 
SPORT = 'basketball_nba'
REGIONS = 'us'

# Map Odds API full team names to your team_metrics abbreviations
TEAM_MAP = {
    "Atlanta Hawks": "ATL",
    "Boston Celtics": "BOS",
    "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA",
    "Chicago Bulls": "CHI",
    "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL",
    "Denver Nuggets": "DEN",
    "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW",
    "Houston Rockets": "HOU",
    "Indiana Pacers": "IND",
    "Los Angeles Clippers": "LAC",
    "Los Angeles Lakers": "LAL",
    "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA",
    "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK",
    "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR",
    "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR",
    "Utah Jazz": "UTA",
    "Washington Wizards": "WAS"
}

# MARKETS LIST
MARKETS = 'player_points,player_rebounds,player_assists,player_threes,player_points_rebounds_assists,player_points_rebounds,player_rebounds_assists'

ODDS_FORMAT = 'decimal'
DATE_FORMAT = 'iso'
# --- DYNAMIC DB PATH ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'edgeboard.db')

def sync_odds():
    print(f"Fetching expanded prop markets for {SPORT}...")

    schedule_url = f'https://api.the-odds-api.com/v4/sports/{SPORT}/events'
    schedule_params = {
        'api_key': API_KEY,
        'regions': REGIONS,
        'dateFormat': DATE_FORMAT,
    }

    try:
        sched_response = requests.get(schedule_url, params=schedule_params)
        
        if sched_response.status_code != 200:
            print(f"Schedule API Error: {sched_response.status_code} - {sched_response.text}")
            return {"status": "error", "message": f"Schedule Error {sched_response.status_code}"}

        schedule_data = sched_response.json()
        
        if not schedule_data:
            print("No games scheduled today.")
            return {"status": "error", "message": "No games scheduled today."}

        # Connect to DB
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # --- NEW: Build the table on the live server if it is missing ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT, -- Ensure ID is here for deduplication
                player_name TEXT,
                team TEXT,
                opponent TEXT,
                prop_type TEXT,
                line_value REAL,
                odds_over REAL,
                game_time TEXT,
                merchant_name TEXT,
                last_updated TEXT
            )
        ''')

        # --- THIS IS THE SPOT ---
        # Clear the active_lines table so we don't have yesterday's lines mixed in
        cursor.execute('DELETE FROM active_lines')
        conn.commit()

        print(f"Found {len(schedule_data)} games. Starting Prop Sync...")
        count = 0 
        last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for game_summary in schedule_data:
            game_id = game_summary['id']
    
    # --- ADD THE MAPPING LOGIC HERE ---
    # 1. Capture the raw names from the API FIRST
            home_raw = game_summary['home_team']
            away_raw = game_summary['away_team']
    
    # 2. Use the TEAM_MAP to convert them to abbreviations
    # If a name isn't in the map, it will just keep the raw name
            team = TEAM_MAP.get(home_raw, home_raw) 
            opponent = TEAM_MAP.get(away_raw, away_raw)
    # ----------------------------------
            
            game_time = game_summary.get('commence_time', '')
            
            prop_url = f'https://api.the-odds-api.com/v4/sports/{SPORT}/events/{game_id}/odds'
            prop_params = {
                'api_key': API_KEY,
                'regions': REGIONS,
                'markets': MARKETS,
                'oddsFormat': ODDS_FORMAT,
                'dateFormat': DATE_FORMAT,
            }

            try:
                prop_response = requests.get(prop_url, params=prop_params)
                
                if prop_response.status_code != 200:
                    continue
                
                game_data = prop_response.json()

                for bookmaker in game_data.get('bookmakers', []):
                    merchant_name = bookmaker['key']
                    
                    if merchant_name not in ['draftkings', 'fanduel', 'mgm', 'caesars']:
                        continue

                    for market in bookmaker['markets']:
                        market_key = market['key'] 
                        
                        prop_map = {
                            'player_points': 'PTS',
                            'player_rebounds': 'REB',
                            'player_assists': 'AST',
                            'player_threes': 'FG3M', 
                            'player_points_rebounds_assists': 'PRA',
                            'player_points_rebounds': 'PR',
                            'player_rebounds_assists': 'RA'
                        }
                        
                        prop_type = prop_map.get(market_key)
                        if not prop_type: continue

                        for outcome in market['outcomes']:
                            if outcome.get('name') != 'Over':
                                continue

                            player_name = outcome['description']
                            line_value = outcome.get('point')
                            odds_over = outcome.get('price', 0)

                            if line_value is None: continue

                            # MATCHES YOUR DATABASE: Insert into active_lines using your exact columns
                            cursor.execute('''
                                INSERT INTO active_lines (
                                    player_name, team, opponent, prop_type, 
        line_value, odds_over, game_time, merchant_name, last_updated
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
''', (
    player_name, 
    team,         # <--- These now contain the standardized 
    opponent,     # <--- abbreviations (e.g., 'LAL', 'NYK')
    prop_type, 
    line_value, 
    odds_over, 
    game_time, 
    merchant_name, 
    last_updated
))
                            count += 1
            
            except Exception as e_game:
                print(f"Error processing game {game_id}: {e_game}")
                continue

        # 1. Commit all the new props you just inserted
        conn.commit()

        # 2. RUN THE CLEANUP ONCE HERE
        print("Deduplicating active lines...")
        cursor.execute("""
            DELETE FROM active_lines 
            WHERE id NOT IN (
                SELECT MAX(id) 
                FROM active_lines 
                GROUP BY player_name, prop_type, merchant_name
            )
        """)

        conn.commit()
        conn.close()
        
        msg = f"Successfully synced {count} props from {len(schedule_data)} games into active_lines."
        print(msg)
        return {"status": "success", "message": msg}

    except Exception as e:
        print(f"Sync Crash: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    sync_odds()