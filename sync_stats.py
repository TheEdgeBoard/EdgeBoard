import sqlite3
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
import re
from nba_api.stats.endpoints import leaguedashteamstats, playergamelog
from nba_api.stats.static import players, teams

def get_db_connection():
    return sqlite3.connect('edgeboard.db')

# --- PART 1: SCRAPE STARTERS FROM BASKETBALL MONSTER ---
def get_starters_from_web():
    url = "https://basketballmonster.com/nbalineups.aspx"
    print(f"🕵️  Scraping Starters from: {url}")
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Basketball Monster usually puts player names in specific table cells
        # We look for links to player pages or table cells that hold names
        player_names = set()

        # Find all cells that might contain players
        # The site structure often changes, but names are usually inside <td> tags
        # We will look for <td> tags that don't have certain classes or styles
        # A more robust way is to find all <a> tags that link to player profiles if possible
        # For now, we scrape text and clean it
        
        # Strategy: Look for the specific grid structure
        # Rows often start with "PG", "SG", "SF", "PF", "C"
        rows = soup.find_all('tr')
        
        for row in rows:
            cells = row.find_all('td')
            if not cells: 
                continue
                
            first_cell = cells[0].get_text(strip=True)
            
            # Check if this row is a position row
            if first_cell in ['PG', 'SG', 'SF', 'PF', 'C']:
                # The players are usually in the 2nd (Home) and 3rd (Away) columns
                # or scattered depending on the layout. 
                # BasketballMonster usually does: Pos | Visitor Player | Home Player
                
                if len(cells) >= 3:
                    # Visitor Player
                    p1 = cells[1].get_text(strip=True)
                    # Home Player
                    p2 = cells[2].get_text(strip=True)
                    
                    if p1: player_names.add(clean_name(p1))
                    if p2: player_names.add(clean_name(p2))

        # Convert to list
        starters = list(player_names)
        print(f"✅ Found {len(starters)} projected starters.")
        return starters

    except Exception as e:
        print(f"❌ Error scraping Basketball Monster: {e}")
        # Fallback to a small list if site is down so script doesn't crash
        return ["LeBron James", "Stephen Curry", "Luka Doncic", "Nikola Jokic", "Giannis Antetokounmpo"]

def clean_name(name):
    # Basketball Monster adds status tags like "LeBron James Q" or " P"
    # We remove any single capital letter at the end or " GTD"
    
    # Remove ' Q', ' P', ' O', ' D', ' GTD' from end of string
    name = re.sub(r'\s+[QPOD]$', '', name) 
    name = re.sub(r'\s+GTD$', '', name)
    return name.strip()

# --- PART 2: UPDATE TEAM METRICS ---
def sync_team_metrics():
    print("🔄 Connecting to NBA.com for Team Stats...")
    
    try:
        # Fetch team stats for the Current Season
        team_stats = leaguedashteamstats.LeagueDashTeamStats(
            season='2025-26', 
            measure_type_detailed_defense='Advanced'
        ).get_data_frames()[0]
    except Exception as e:
        print(f"⚠️ Error fetching team stats (Check connection): {e}")
        return

    # Create Lookup for Abbreviations
    nba_teams = teams.get_teams()
    team_map = {team['full_name']: team['abbreviation'] for team in nba_teams}

    conn = get_db_connection()
    c = conn.cursor()

    for index, row in team_stats.iterrows():
        team_name = row['TEAM_NAME']
        team_abbr = team_map.get(team_name)
        if not team_abbr: team_abbr = team_name[:3].upper()

        pace = row['PACE']
        def_rating = row['DEF_RATING']
        
        c.execute('''
            INSERT INTO team_metrics (team_abbrev, pace, defensive_rating)
            VALUES (?, ?, ?)
            ON CONFLICT(team_abbrev) DO UPDATE SET
            pace=excluded.pace,
            defensive_rating=excluded.defensive_rating
        ''', (team_abbr, pace, def_rating))
    
    conn.commit()
    conn.close()
    print("✅ Team Metrics Updated.")

# --- PART 3: UPDATE PLAYER LOGS ---
def sync_player_logs():
    # 1. Get the list from the web
    target_players = get_starters_from_web()
    
    conn = get_db_connection()
    c = conn.cursor()
    
    print(f"🔄 Syncing Last 6 Games for {len(target_players)} players...")
    print("   (This may take 1-2 minutes to respect API rate limits)")

    count = 0
    for name in target_players:
        if name == "" or "Lineups" in name: continue

        # 1. Find Player ID
        nba_players = players.find_players_by_full_name(name)
        if not nba_players:
            # Try fuzzy matching if exact name fails? (Skipping for speed now)
            print(f"   ⚠️ NBA.com ID not found: {name}")
            continue
        
        player_id = nba_players[0]['id']
        
        # 2. Fetch Game Logs
        # DELAY IS CRITICAL: If you go too fast, NBA.com bans your IP for an hour.
        time.sleep(0.65) 
        
        try:
            logs = playergamelog.PlayerGameLog(player_id=player_id, season='2025-26').get_data_frames()[0]
            last_6 = logs.head(6)

            for i, game in last_6.iterrows():
                c.execute('''
                    INSERT INTO player_logs (player_name, game_date, pts, reb, ast, threes_made, minutes_played)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (name, game['GAME_DATE'], game['PTS'], game['REB'], game['AST'], game['FG3M'], game['MIN']))
            
            count += 1
            if count % 10 == 0:
                print(f"   ... Synced {count} players")
                conn.commit() # Save progress every 10 players
            
        except Exception as e:
            print(f"   ❌ Error fetching {name}")

    conn.commit()
    conn.close()
    print(f"✅ Player Logs Sync Complete. ({count} players updated)")

if __name__ == "__main__":
    sync_team_metrics()
    sync_player_logs()