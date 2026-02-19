import sqlite3
import requests
from bs4 import BeautifulSoup

DB_PATH = '/home/TheEdgeBoard/EdgeBoard/edgeboard.db'

def run():
    print("Checking Basketball Monster for Lineup Changes...")
    try:
        res = requests.get("https://basketballmonster.com/nbalineups.aspx", timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Find teams with "Lineup Change" indicator
        changed_teams = []
        for box in soup.select(".TeamLineupBox"):
            if "Lineup Change" in box.text:
                team_code = box.select_one(".TeamAbbrev").text.strip()
                changed_teams.append(team_code)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Reset everyone to 0 first
        cursor.execute("UPDATE sim_results SET lineup_flag = 0")
        
        # Flag players on changed teams
        for team in changed_teams:
            cursor.execute("UPDATE sim_results SET lineup_flag = 1 WHERE team_name = ?", (team,))
            
        conn.commit()
        conn.close()
        print(f"Flagged Teams: {changed_teams}")
        
    except Exception as e:
        print(f"Error checking lineups: {e}")

if __name__ == "__main__":
    run()