import requests
import sqlite3
import os
import sys
from datetime import datetime

# --- CONFIGURATION ---
API_KEY = 'e95fe4afaf21151d8ac43cfaef741522'
SPORT = 'basketball_nba'
REGIONS = 'us'
MARKETS = 'player_points,player_rebounds,player_assists,player_threes,player_points_rebounds_assists,player_points_rebounds,player_rebounds_assists'
ODDS_FORMAT = 'decimal'
DATE_FORMAT = 'iso'

# Ensure this path is correct for your server
DB_PATH = '/home/TheEdgeBoard/EdgeBoard/edgeboard.db'

def sync_odds():
    print(f"Fetching expanded prop markets for {SPORT}...")

    # 1. Fetch the Games
    url = f'https://api.the-odds-api.com/v4/sports/{SPORT}/odds'
    params = {
        'api_key': API_KEY,
        'regions': REGIONS,
        'markets': MARKETS,
        'oddsFormat': ODDS_FORMAT,
        'dateFormat': DATE_FORMAT,
    }

    try:
        response = requests.get(url, params=params)
        
        if response.status_code != 200:
            error_msg = f"API Error: {response.status_code} - {response.text}"
            print(error_msg)
            return {"status": "error", "message": error_msg}

        data = response.json()
        if not data:
            print("No games scheduled today.")
            return {"status": "error", "message": "No games scheduled today."}

        # 2. Connect to DB
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Clear old odds
        cursor.execute('DELETE FROM daily_prospects') 

        print(f"Processing {len(data)} games...")
        count = 0

        for game in data:
            home_team = game['home_team']
            away_team = game['away_team']

            for bookmaker in game['bookmakers']:
                # Filter for major US books
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
                        
                        # Insert into DB
                        cursor.execute('''
                            INSERT INTO daily_prospects (
                                player_name, team_id, opponent_id, prop_type, market_line, 
                                hits_last_3_over, hits_last_3_under, avg_last_3,
                                hits_last_5_over, hits_last_5_under, avg_last_5,
                                hits_last_10_over, hits_last_10_under, avg_last_10,
                                hits_last_14_over, hits_last_14_under, avg_last_14
                            ) VALUES (?, ?, ?, ?, ?, 0,0,0, 0,0,0, 0,0,0, 0,0,0)
                        ''', (player_name, home_team, away_team, prop_type, line))
                        count += 1

        conn.commit()
        conn.close()
        
        success_msg = f"Successfully synced {count} props."
        print(success_msg)
        return {"status": "success", "message": success_msg}

    except Exception as e:
        error_msg = f"Sync Crash: {str(e)}"
        print(error_msg)
        return {"status": "error", "message": error_msg}

if __name__ == "__main__":
    sync_odds()