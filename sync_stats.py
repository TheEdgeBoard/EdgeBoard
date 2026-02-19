import sqlite3
import pandas as pd
import time
from nba_api.stats.endpoints import playergamelog

DB_PATH = '/home/TheEdgeBoard/EdgeBoard/edgeboard.db'

def sync_stats():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("Fetching active prospects...")
    prospects = cursor.execute("SELECT * FROM daily_prospects WHERE market_line IS NOT NULL").fetchall()
    
    updates = []
    
    for p in prospects:
        try:
            pid = p['player_id'] # Ensure player_id exists in DB
            if not pid: continue
            
            # Fetch last 20 games
            time.sleep(0.6) 
            log = playergamelog.PlayerGameLog(player_id=pid, season='2024-25').get_data_frames()[0].head(20)
            
            prop = p['prop_type']
            line = float(p['market_line'])
            
            # Map Prop to Stat Column
            col = 'PTS' if prop == 'Points' else 'REB' if prop == 'Rebounds' else 'AST' if prop == 'Assists' else 'FG3M' if 'Three' in prop else None
            
            if not col and prop == 'Pts+Rebs+Asts':
                log['PRA'] = log['PTS'] + log['REB'] + log['AST']
                col = 'PRA'
                
            if col and not log.empty:
                # Calculate Hit History (1 = Covered Line, 0 = Missed)
                hits = ['1' if val > line else '0' for val in log[col]]
                trend_str = ",".join(hits)
                last_hit = int(hits[0]) if hits else 0
                
                updates.append((trend_str, last_hit, p['player_name'], prop))
                print(f"Updated {p['player_name']}: Last Hit={last_hit}, Trend={trend_str[:5]}...")
                
        except Exception as e:
            print(f"Skipping {p['player_name']}: {e}")

    cursor.executemany('UPDATE daily_prospects SET trend_history = ?, last_game_hit = ? WHERE player_name = ? AND prop_type = ?', updates)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    sync_stats()