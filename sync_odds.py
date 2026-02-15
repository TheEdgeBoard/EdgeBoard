import requests
import sqlite3
import json

# =================CONFIGURATION=================
# PASTE YOUR API KEY HERE
API_KEY = 'YOUR_API_KEY_HERE' 

# The specific markets you requested
# Note: 'player_points_rebounds_assists' requires a paid plan on some APIs, 
# but individual stats are usually free.
MARKETS = 'player_points,player_rebounds,player_assists,player_threes'
REGIONS = 'us' # us, uk, eu, au
ODDS_FORMAT = 'american' # american, decimal
BOOKMAKERS = 'draftkings,fanduel' # comma separated
# ===============================================

def get_db_connection():
    return sqlite3.connect('edgeboard.db')

def fetch_nba_odds():
    print("🚀 Connecting to The Odds API...")
    
    # 1. Get Upcoming Games (Event IDs)
    url_events = f'https://api.the-odds-api.com/v4/sports/basketball_nba/events?apiKey={API_KEY}'
    response = requests.get(url_events)
    
    if response.status_code != 200:
        print(f"❌ Error getting events: {response.status_code}")
        print(response.text)
        return

    events = response.json()
    print(f"📅 Found {len(events)} upcoming games.")

    conn = get_db_connection()
    c = conn.cursor()

    # Clear old lines to keep the dashboard fresh
    c.execute("DELETE FROM active_lines")
    print("🧹 Cleared old lines from database.")

    # 2. Loop through each game and get the props
    for event in events:
        game_id = event['id']
        home_team = event['home_team']
        away_team = event['away_team']
        start_time = event['commence_time']

        print(f"   Downloading Props for: {away_team} @ {home_team}...")

        url_odds = f'https://api.the-odds-api.com/v4/sports/basketball_nba/events/{game_id}/odds?apiKey={API_KEY}&regions={REGIONS}&markets={MARKETS}&bookmakers={BOOKMAKERS}&oddsFormat={ODDS_FORMAT}'
        
        odds_response = requests.get(url_odds)
        if odds_response.status_code != 200:
            print(f"   ⚠️ Failed to get odds for game {game_id}")
            continue

        odds_data = odds_response.json()

        # 3. Parse the complicated JSON into our clean Database
        for bookmaker in odds_data['bookmakers']:
            bookie_name = bookmaker['title']
            
            for market in bookmaker['markets']:
                prop_type = market['key'] # e.g., 'player_points'
                
                for outcome in market['outcomes']:
                    player_name = outcome['description']
                    label = outcome['name'] # 'Over' or 'Under'
                    line = outcome['point']
                    price = outcome['price'] # e.g., -110
                    
                    # We only want the OVER lines for now to simplify the EV calculation
                    # (You can remove this check if you want Unders too)
                    if label == 'Over':
                        c.execute('''
                            INSERT INTO active_lines 
                            (player_name, team, opponent, prop_type, line_value, odds_over, game_time, merchant_name)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (player_name, home_team, away_team, prop_type, line, price, start_time, bookie_name))

    conn.commit()
    conn.close()
    print("✅ Sync Complete! Database updated with live odds.")

if __name__ == "__main__":
    fetch_nba_odds()