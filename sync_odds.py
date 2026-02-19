import requests
import sqlite3
import os
import sys
import time
from datetime import datetime

# --- CONFIGURATION ---
API_KEY = 'e95fe4afaf21151d8ac43cfaef741522' # Reminder: Put your new burner key here!
SPORT = 'basketball_nba'
REGIONS = 'us'

# MARKETS LIST
MARKETS = 'player_points,player_rebounds,player_assists,player_threes,player_points_rebounds_assists,player_points_rebounds,player_rebounds_assists'

ODDS_FORMAT = 'decimal'
DATE_FORMAT = 'iso'
DB_PATH = '/home/TheEdgeBoard/EdgeBoard/edgeboard.db'

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
            return {"status": "error", "message": f"Schedule Error {sched_response.status_code}"}

        schedule_data = sched_response.json()
        
        if not schedule_data:
            return {"status": "error", "message": "No games scheduled today."}

        # Connect to DB & Build Table
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_lines (
                player_name TEXT, team TEXT, opponent TEXT, prop_type TEXT,
                line_value REAL, odds_over REAL, game_time TEXT, merchant_name TEXT, last_updated TEXT
            )
        ''')

        cursor.execute('DELETE FROM active_lines')
        conn.commit()

        print(f"Found {len(schedule_data)} games. Starting Prop Sync...")
        count = 0 
        last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for game_summary in schedule_data:
            game_id = game_summary['id']
            team = game_summary['home_team']
            opponent = game_summary['away_team']
            game_time = game_summary.get('commence_time', '')
            
            time.sleep(1.5) # Rate limit pause

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
                if prop_response.status_code != 200: continue
                game_data = prop_response.json()

                # --- NEW: Deduplication Dictionary ---
                unique_props = {}

                for bookmaker in game_data.get('bookmakers', []):
                    merchant_name = bookmaker['key']
                    if merchant_name not in ['draftkings', 'fanduel', 'mgm', 'caesars']: continue

                    for market in bookmaker['markets']:
                        market_key = market['key'] 
                        prop_map = {
                            'player_points': 'PTS', 'player_rebounds': 'REB', 'player_assists': 'AST',
                            'player_threes': 'FG3M', 'player_points_rebounds_assists': 'PRA',
                            'player_points_rebounds': 'PR', 'player_rebounds_assists': 'RA'
                        }
                        prop_type = prop_map.get(market_key)
                        if not prop_type: continue

                        for outcome in market['outcomes']:
                            if outcome.get('name') != 'Over': continue

                            player_name = outcome['description']
                            line_value = outcome.get('point')
                            odds_over = outcome.get('price', 0)

                            if line_value is None: continue

                            # Create a unique key for this player + prop type (e.g., "LeBron James-PTS")
                            dict_key = f"{player_name}-{prop_type}"

                            # If we haven't seen this prop yet, add it
                            if dict_key not in unique_props:
                                unique_props[dict_key] = {
                                    'player_name': player_name, 'prop_type': prop_type,
                                    'line_value': line_value, 'odds_over': odds_over, 'merchant_name': merchant_name
                                }
                            else:
                                # If we HAVE seen it, only replace it if the line is the SAME but odds are BETTER
                                existing = unique_props[dict_key]
                                if existing['line_value'] == line_value and odds_over > existing['odds_over']:
                                    existing['odds_over'] = odds_over
                                    existing['merchant_name'] = merchant_name

                # --- NOW insert the cleaned, unique data into the database ---
                for prop_data in unique_props.values():
                    cursor.execute('''
                        INSERT INTO active_lines (
                            player_name, team, opponent, prop_type, 
                            line_value, odds_over, game_time, merchant_name, last_updated
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (prop_data['player_name'], team, opponent, prop_data['prop_type'], 
                          prop_data['line_value'], prop_data['odds_over'], game_time, prop_data['merchant_name'], last_updated))
                    count += 1
            
            except Exception as e_game:
                continue

        conn.commit()
        conn.close()
        
        msg = f"Successfully synced {count} unique props from {len(schedule_data)} games."
        print(msg)
        return {"status": "success", "message": msg}

    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    sync_odds()