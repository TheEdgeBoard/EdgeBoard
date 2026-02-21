import sqlite3
import os
import requests
import time
from dotenv import load_dotenv

load_dotenv()

BDL_API_KEY = os.getenv('BDL_API_KEY')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'edgeboard.db')

def sync_team_metrics():
    print("🏀 Updating NBA Team Metrics (Pace & Defensive Rating)...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Ensure table exists with the columns your simulation expects
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS team_metrics (
            team_abbrev TEXT PRIMARY KEY,
            pace REAL,
            defensive_rating REAL
        )
    ''')

    headers = {'Authorization': BDL_API_KEY}
    
    # We pull for the current 2025-26 season
    url = "https://api.balldontlie.io/nba/v1/teams/stats?season=2025"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            teams_data = response.json().get('data', [])
            
            for team in teams_data:
                # Map BDL fields to your simulation's needs
                # Note: BDL provides 'pace' and 'def_rating' directly
                abbrev = team['team']['abbreviation']
                pace = team['pace']
                def_rating = team['def_rating']
                
                cursor.execute('''
                    INSERT INTO team_metrics (team_abbrev, pace, defensive_rating)
                    VALUES (?, ?, ?)
                    ON CONFLICT(team_abbrev) DO UPDATE SET
                        pace=excluded.pace,
                        defensive_rating=excluded.defensive_rating
                ''', (abbrev, pace, def_rating))
            
            conn.commit()
            print(f"✅ Successfully updated metrics for {len(teams_data)} teams.")
        else:
            print(f"❌ Failed to fetch team stats: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error during team sync: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    sync_team_metrics()