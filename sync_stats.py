import sqlite3
import pandas as pd
import time
from nba_api.stats.endpoints import playergamelog

DB_PATH = '/home/TheEdgeBoard/EdgeBoard/edgeboard.db'

def sync_player_performance():
    print("Starting Multi-Window Performance Sync...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    try:
        prospects = pd.read_sql("SELECT * FROM daily_prospects", conn)
    except:
        return

    for index, row in prospects.iterrows():
        try:
            time.sleep(0.6) # Respect API limits
            
            # Fetch Max Needed (14 Games)
            gamelog = playergamelog.PlayerGameLog(player_id=row['player_id'], season='2025-26')
            df_logs = gamelog.get_data_frames()[0]
            
            if df_logs.empty: continue

            # Map Stats
            stat_map = {'PTS':'PTS', 'REB':'REB', 'AST':'AST', 'FG3M':'FG3M', 'FG3A':'FG3A', 'FGM':'FGM', 'FGA':'FGA'}
            prop = row['prop_type']
            
            full_log = df_logs.copy()
            if prop in stat_map: full_log['ACTUAL'] = full_log[stat_map[prop]]
            elif prop == 'PRA': full_log['ACTUAL'] = full_log['PTS'] + full_log['REB'] + full_log['AST']
            elif prop == 'RA': full_log['ACTUAL'] = full_log['REB'] + full_log['AST']
            else: continue

            # --- CALCULATE ALL WINDOWS ---
            windows = [3, 5, 10, 14]
            data_updates = {}
            
            # Score Last Game (Momentum)
            data_updates['score_last_game'] = float(full_log.iloc[0]['ACTUAL'])

            for w in windows:
                slice_df = full_log.head(w)
                # Count Hits
                data_updates[f'hits_last_{w}_over'] = int((slice_df['ACTUAL'] > row['market_line']).sum())
                data_updates[f'hits_last_{w}_under'] = int((slice_df['ACTUAL'] < row['market_line']).sum())
                # Calculate Average for Sim Baseline
                data_updates[f'avg_last_{w}'] = float(slice_df['ACTUAL'].mean())

            # Update DB
            conn.execute(f'''
                UPDATE daily_prospects SET 
                    score_last_game = ?,
                    hits_last_3_over = ?, hits_last_3_under = ?, avg_last_3 = ?,
                    hits_last_5_over = ?, hits_last_5_under = ?, avg_last_5 = ?,
                    hits_last_10_over = ?, hits_last_10_under = ?, avg_last_10 = ?,
                    hits_last_14_over = ?, hits_last_14_under = ?, avg_last_14 = ?
                WHERE player_id = ? AND prop_type = ?
            ''', (
                data_updates['score_last_game'],
                data_updates['hits_last_3_over'], data_updates['hits_last_3_under'], data_updates['avg_last_3'],
                data_updates['hits_last_5_over'], data_updates['hits_last_5_under'], data_updates['avg_last_5'],
                data_updates['hits_last_10_over'], data_updates['hits_last_10_under'], data_updates['avg_last_10'],
                data_updates['hits_last_14_over'], data_updates['hits_last_14_under'], data_updates['avg_last_14'],
                row['player_id'], prop
            ))
            print(f"Synced {row['player_name']} {prop}")

        except Exception as e:
            continue

    conn.commit()
    conn.close()
    print("Multi-Window Sync Complete.")

if __name__ == "__main__":
    sync_player_performance()