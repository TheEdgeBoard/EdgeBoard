import requests
import sqlite3
import os
import sys
from datetime import datetime

# --- CONFIGURATION ---
API_KEY = 'e95fe4afaf21151d8ac43cfaef741522' 
SPORT = 'basketball_nba'
REGIONS = 'us'

# YOUR ORIGINAL MARKETS LIST
MARKETS = 'player_points,player_rebounds,player_assists,player_threes,player_points_rebounds_assists,player_points_rebounds,player_rebounds_assists'

ODDS_FORMAT = 'decimal'
DATE_FORMAT = 'iso'
DB_PATH = '/home/TheEdgeBoard/EdgeBoard/edgeboard.db'

def sync_odds():
    print(f"Fetching expanded prop markets for {SPORT}...")

    # --- STEP 1: Get the Schedule (Game IDs only) ---
    # We use the /events endpoint first to get the list of Game IDs.
    # This endpoint DOES NOT return odds, but it avoids the "Market Error".
    schedule_url = f'https://api.the-odds-api.com/v4/sports/{SPORT}/events'
    schedule_params = {
        'api_key': API_KEY,
        'regions': REGIONS,
        'dateFormat': DATE_FORMAT,
    }

    try:
        # Fetch Schedule
        sched_response = requests.get(schedule_url, params=schedule_params)
        
        if sched_response.status_code != 200:
            print(f"Schedule API Error: {sched_response.status_code} - {sched_response.text}")
            return {"status": "error", "message": f"Schedule Error {sched_response.status_code}"}

        schedule_data = sched_response.json()
        
        if not schedule_data:
            print("No games scheduled today.")
            return {"status": "error", "message": "No games scheduled today."}

        # Connect to DB and Clear Old Data
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM daily_prospects')
        conn.commit()

        print(f"Found {len(schedule_data)} games. Starting Prop Sync (this may take a moment)...")
        count = 0 

        # --- STEP 2: Loop through each game to get Player Props ---
        for game_summary in schedule_data:
            game_id = game_summary['id']
            home_team = game_summary['home_team']
            away_team = game_summary['away_team']
            
            # Construct URL for THIS specific game
            # This is the fix: Using /events/{id}/odds instead of the bulk endpoint
            prop_url = f'https://api.the-odds-api.com/v4/sports/{SPORT}/events/{game_id}/odds'
            prop_params = {
                'api_key': API_KEY,
                'regions': REGIONS,
                'markets': MARKETS, # Requesting player props here is allowed!
                'oddsFormat': ODDS_FORMAT,
                'dateFormat': DATE_FORMAT,
            }

            try:
                # Fetch Props for this single game
                prop_response = requests.get(prop_url, params=prop_params)
                
                # Skip if this specific game fails, but don't crash the whole loop
                if prop_response.status_code != 200:
                    print(f"Skipping game {home_team} vs {away_team}: {prop_response.status_code}")
                    continue
                
                game_data = prop_response.json()

                # --- STEP 3: Parse the Data (Your Original Logic) ---
                # game_data is now a single object, not a list, so we access 'bookmakers' directly
                for bookmaker in game_data.get('bookmakers', []):
                    
                    # Filter for major books
                    if bookmaker['key'] not in ['draftkings', 'fanduel', 'mgm', 'caesars']:
                        continue

                    for market in bookmaker['markets']:
                        market_key = market['key'] 
                        
                        # Map API keys to readable Prop Types
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
                            player_name = outcome['description']
                            line = outcome.get('point')
                            if not line: continue
                            
                            price = outcome.get('price', 0)

                            cursor.execute('''
                                INSERT INTO daily_prospects (
                                    player_name, team_id, opponent_id, prop_type, market_line, best_odds,
                                    hits_last_3_over, hits_last_3_under, avg_last_3,
                                    hits_last_5_over, hits_last_5_under, avg_last_5,
                                    hits_last_10_over, hits_last_10_under, avg_last_10,
                                    hits_last_14_over, hits_last_14_under, avg_last_14
                                ) VALUES (?, ?, ?, ?, ?, ?, 0,0,0, 0,0,0, 0,0,0, 0,0,0)
                            ''', (player_name, home_team, away_team, prop_type, line, price))
                            count += 1
            
            except Exception as e_game:
                print(f"Error processing game {game_id}: {e_game}")
                continue

        # Final Commit after all games are processed
        conn.commit()
        conn.close()
        
        msg = f"Successfully synced {count} props from {len(schedule_data)} games."
        print(msg)
        return {"status": "success", "message": msg}

    except Exception as e:
        print(f"Sync Crash: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    sync_odds()