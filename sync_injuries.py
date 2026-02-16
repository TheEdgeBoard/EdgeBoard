import sqlite3
import pandas as pd
from nbainjuries import injury # 2026 official library
from datetime import datetime

def sync_injuries():
    # Pull today's official report
    try:
        df = injury.get_reportdata(datetime.now(), return_df=True)
        # Filter for only confirmed 'Out' players
        df_out = df[df['status'].str.contains('Out', case=False)]
        
        conn = sqlite3.connect('/home/TheEdgeBoard/EdgeBoard/edgeboard.db')
        df_out[['player_id', 'team_id']].to_sql('injuries_today', conn, if_exists='replace', index=False)
        conn.close()
        print(f"Injury report synced: {len(df_out)} players out.")
    except Exception as e:
        print(f"Injury sync failed: {e}")

if __name__ == "__main__":
    sync_injuries()