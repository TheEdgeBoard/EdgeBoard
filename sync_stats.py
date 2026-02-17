import sqlite3
import pandas as pd
import time
import sys

# Try importing the NBA API
try:
    from nba_api.stats.endpoints import playergamelog
except ImportError:
    print("CRITICAL ERROR: 'nba_api' library not found. Run 'pip3 install nba_api'")
    sys.exit(1)

DB_PATH = '/home/TheEdgeBoard/EdgeBoard/edgeboard.db'

def sync_player_performance():
    print("Starting Multi-Window Performance & Trend Sync...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    try:
        # Load all prospects currently in the database (synced from sync_odds.py)
        prospects = pd.read_sql("SELECT * FROM daily_prospects", conn)
        if prospects.empty:
            print("No prospects found in database. Run sync_odds first.")
            conn.close()
            return
            
    except Exception as e:
        print(f"Database Error: {e}")
        conn.close()
        return

    print(f"Processing {len(prospects)} player props...")

    for index, row in prospects.iterrows():
        try:
            # Respect NBA API rate limits (essential for PythonAnywhere)
            time.sleep(0.7) 
            
            # Fetch the last 14 games (covers our max window)
            gamelog = playergamelog.PlayerGameLog(player_id=row['player_id'], season='2025-26')
            df_logs = gamelog.get_data_frames()[0]
            
            if df_logs.empty:
                print(f"No stats found for {row['player_name']}")
                continue

            # Mapping API columns to our prop types
            stat_map = {'PTS':'PTS', 'REB':'REB', 'AST':'AST', 'FG3M':'FG3M'}
            prop = row['prop_type']
            
            full_log = df_logs.copy()
            
            # Calculate actual values based on the prop type
            if prop in stat_map: 
                full_log['ACTUAL'] = full_log[stat_map[prop]]
            elif prop == 'PRA': 
                full_log['ACTUAL'] = full_log['PTS'] + full_log['REB'] + full_log['AST']
            elif prop == 'PR': 
                full_log['ACTUAL'] = full_log['PTS'] + full_log['REB']
            elif prop == 'RA': 
                full_log['ACTUAL'] = full_log['REB'] + full_log['AST']
            else: 
                continue

            # --- TREND HISTORY (For Chart.js) ---
            # Get the last 5 games and convert to a comma-separated string
            last_5_scores = full_log.head(5)['ACTUAL'].astype(str).tolist()
            trend_string = ",".join(last_5_scores) # Result: "24,19,30,22,25"

            # --- CALCULATE WINDOWS (L3, L5, L10, L14) ---
            windows = [3, 5, 10, 14]
            data_updates = {}
            
            for w in windows:
                slice_df = full_log.head(w)
                # Check if we have enough games to calculate
                if len(slice_df) < 1: continue
                
                data_updates[f'hits_{w}_over'] = int((slice_df['ACTUAL'] > row['market_line']).sum())
                data_updates[f'hits_{w}_under'] = int((slice_df['ACTUAL'] < row['market_line']).sum())
                data_updates[f'avg_{w}'] = float(slice_df['ACTUAL'].mean())

            # Update the database
            # We update by ID now to be safe with the new SQLAlchemy structure
            conn.execute('''
                UPDATE daily_prospects SET 
                    trend_history = ?,
                    hits_last_3_over = ?, hits_last_3_under = ?, avg_last_3 = ?,
                    hits_last_5_over = ?, hits_last_5_under = ?, avg_last_5 = ?,
                    hits_last_10_over = ?, hits_last_10_under = ?, avg_last_10 = ?,
                    hits_last_14_over = ?, hits_last_14_under = ?, avg_last_14 = ?
                WHERE player_name = ? AND prop_type = ?
            ''', (
                trend_string,
                data_updates.get('hits_3_over', 0), data_updates.get('hits_3_under', 0), data_updates.get('avg_3', 0),
                data_updates.get('hits_5_over', 0), data_updates.get('hits_5_under', 0), data_updates.get('avg_5', 0),
                data_updates.get('hits_10_over', 0), data_updates.get('hits_10_under', 0), data_updates.get('avg_10', 0),
                data_updates.get('hits_14_over', 0), data_updates.get('hits_14_under', 0), data_updates.get('avg_14', 0),
                row['player_name'], prop
            ))
            
            print(f"Synced {row['player_name']} ({prop}) - Trend: {trend_string}")

        except Exception as e:
            print(f"Error processing {row.get('player_name', 'Unknown')}: {e}")
            continue

    conn.commit()
    conn.close()
    print("Performance & Trend Sync Complete.")

if __name__ == "__main__":
    sync_player_performance()