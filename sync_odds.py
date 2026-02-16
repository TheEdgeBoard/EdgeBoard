import sqlite3
import requests
import os
import sys

# Your API Configuration
API_KEY = 'your_api_key_here'
API_URL = 'https://api.the-odds-api.com/v4/sports/basketball_nba/odds'

def sync_all_markets():
    conn = sqlite3.connect('/home/TheEdgeBoard/EdgeBoard/edgeboard.db')
    
    # 9 Categories to fetch
    markets = "player_points,player_rebounds,player_assists,player_pass_pts_reb_ast," \
              "player_points_3_made,player_field_goals_made,player_field_goals_attempts," \
              "player_points_3_attempts,player_rebounds_assists"

    params = {
        'apiKey': API_KEY,
        'regions': 'us',
        'markets': markets,
        'oddsFormat': 'american'
    }

    try:
        response = requests.get(API_URL, params=params)
        
        # 1. HANDLE API ERRORS
        if response.status_code != 200:
            print(f"API Error: {response.status_code}")
            sys.exit(1) # Fail so app.py knows

        data = response.json()

        # 2. HANDLE NO GAMES (The Fix)
        if not data:
            print("No games scheduled today (All-Star Break / Offseason).")
            # Clear old data so dashboard is empty, not broken
            conn.execute("DELETE FROM daily_prospects")
            conn.commit()
            conn.close()
            sys.exit(0) # Exit successfully

        # 3. NORMAL PROCESSING
        conn.execute("DELETE FROM daily_prospects")

        for game in data:
            for bookmaker in game.get('bookmakers', []):
                if bookmaker['key'] == 'draftkings': 
                    for market in bookmaker.get('markets', []):
                        prop_map = {
                            'player_points_3_made': 'FG3M',
                            'player_points_3_attempts': 'FG3A',
                            'player_field_goals_made': 'FGM',
                            'player_field_goals_attempts': 'FGA',
                            'player_rebounds_assists': 'RA'
                        }
                        
                        raw_type = market['key']
                        prop_type = prop_map.get(raw_type, raw_type.replace('player_', '').upper())

                        for outcome in market['outcomes']:
                            if outcome['name'] == 'Over': 
                                conn.execute('''
                                    INSERT INTO daily_prospects (player_name, team_id, opponent_id, prop_type, market_line, implied_prob_over, implied_prob_under)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                ''', (
                                    outcome['description'],
                                    game['home_team'] if outcome['description'] in game['home_team'] else game['away_team'],
                                    game['away_team'] if outcome['description'] in game['home_team'] else game['home_team'],
                                    prop_type,
                                    outcome['point'],
                                    0.52, 
                                    0.52
                                ))
        conn.commit()
        print("Market odds synced successfully.")
        
    except Exception as e:
        print(f"Odds Sync Failed: {e}")
        sys.exit(1)
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    sync_all_markets()