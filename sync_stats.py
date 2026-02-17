import sqlite3
import time
from nba_api.stats.endpoints import playergamelog

DB_PATH = '/home/TheEdgeBoard/EdgeBoard/edgeboard.db'

def sync():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    prospects = conn.execute('SELECT * FROM daily_prospects').fetchall()
    
    for p in prospects:
        try:
            time.sleep(0.8) # Avoid API blocks
            log = playergamelog.PlayerGameLog(player_id=p['player_id'], season='2025-26').get_data_frames()[0]
            if log.empty: continue

            # Get last 5 games for the trend sparkline
            trend = ",".join(log.head(5)['PTS'].astype(str).tolist())
            
            # Simple hit rate for L5
            hits_5 = int((log.head(5)['PTS'] > p['market_line']).sum())
            
            conn.execute('UPDATE daily_prospects SET trend_history = ?, hits_last_5_over = ? WHERE player_name = ? AND prop_type = ?',
                         (trend, hits_5, p['player_name'], p['prop_type']))
            print(f"Synced {p['player_name']}")
        except:
            continue
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    sync()