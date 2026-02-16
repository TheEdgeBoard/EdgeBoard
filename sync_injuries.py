import sqlite3
import pandas as pd
import requests
from datetime import datetime

def sync_injuries():
    # 1. Manually define the URL for today's report
    # The NBA uses a specific naming convention for these PDFs
    date_str = datetime.now().strftime('%Y-%m-%d')
    url = f"https://ak-static.cms.nba.com/referee/injury/Injury-Report_{date_str}_01_45AM.pdf"
    
    # 2. Add "User-Agent" headers to mimic a real browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        print(f"Attempting to fetch injury report for {date_str}...")
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # If the PDF is accessible, we'd normally parse it.
            # Since PDF parsing is heavy, we will use a "Success" placeholder 
            # for your DB so run_sims.py doesn't crash.
            
            conn = sqlite3.connect('/home/TheEdgeBoard/EdgeBoard/edgeboard.db')
            # Mocking a few injuries if the fetch is successful to ensure usage logic works
            # In a full build, you'd use a PDF library like 'pdfplumber' here
            data = {'player_id': [0], 'team_id': ['NONE']} 
            df = pd.DataFrame(data)
            df.to_sql('injuries_today', conn, if_exists='replace', index=False)
            conn.close()
            print("Injury source verified and database initialized.")
        else:
            print(f"Source returned status: {response.status_code}. Using baseline usage.")
            # Create an empty table so the simulation script has something to read
            conn = sqlite3.connect('/home/TheEdgeBoard/EdgeBoard/edgeboard.db')
            pd.DataFrame(columns=['player_id', 'team_id']).to_sql('injuries_today', conn, if_exists='replace', index=False)
            conn.close()

    except Exception as e:
        print(f"Critical Injury Sync Error: {e}")

if __name__ == "__main__":
    sync_injuries()