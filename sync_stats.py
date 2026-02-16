import sqlite3
import pandas as pd
import time
from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players

# Database Path Configuration
DB_PATH = '/home/TheEdgeBoard/EdgeBoard/edgeboard.db'

def sync_player_performance():
    """
    Fetches the last 6 games for every active prospect and calculates:
    1. Score in Last Game (Momentum check)
    2. Hits in Last 6 Games (Consistency check)
    3. Average over Last 6 Games (Trend baseline)
    """
    print("Starting Performance Sync...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # 1. Get the list of players & lines we need to check
    try:
        prospects = pd.read_sql("SELECT * FROM daily_prospects", conn)
    except Exception as e:
        print(f"Error reading prospects: {e}")
        return

    print(f"Analyzing {len(prospects)} betting lines...")

    # 2. Iterate through each player/prop combination
    for index, row in prospects.iterrows():
        try:
            p_id = row['player_id']
            line = row['market_line']
            prop = row['prop_type']
            
            # 3. Fetch Game Logs (2025-26 Season)
            # We add a tiny sleep to be nice to the NBA API limits
            time.sleep(0.6) 
            gamelog = playergamelog.PlayerGameLog(player_id=p_id, season='2025-26')
            df_logs = gamelog.get_data_frames()[0]
            
            # We only need the last 6 games
            last_6 = df_logs.head(6).copy()
            
            if last_6.empty:
                print(f"No logs for {row['player_name']}")
                continue

            # 4. Map Prop Types to API Columns
            # API Columns: PTS, REB, AST, FG3M, FG3A, FGM, FGA
            stat_map = {
                'PTS': 'PTS',
                'REB': 'REB',
                'AST': 'AST',
                'FG3M': 'FG3M', # 3-Pointers Made
                'FG3A': 'FG3A', # 3-Pointers Attempted
                'FGM': 'FGM',   # Field Goals Made
                'FGA': 'FGA'    # Field Goals Attempted
            }

            # 5. Calculate the 'ACTUAL' value for the specific prop
            if prop in stat_map:
                last_6['ACTUAL'] = last_6[stat_map[prop]]
            elif prop == 'PRA': # Points + Rebounds + Assists
                last_6['ACTUAL'] = last_6['PTS'] + last_6['REB'] + last_6['AST']
            elif prop == 'RA': # Rebounds + Assists
                last_6['ACTUAL'] = last_6['REB'] + last_6['AST']
            else:
                # If prop type is unknown/unsupported, skip calculation
                continue

            # 6. Calculate Metrics
            # A. Last Game Score (For Momentum Filter)
            score_last_game = float(last_6.iloc[0]['ACTUAL'])
            
            # B. Hits in Last 6 (For Consistency Filter)
            hits_over = int((last_6['ACTUAL'] > line).sum())
            hits_under = int((last_6['ACTUAL'] < line).sum())
            
            # C. Average (For Simulation Baseline)
            avg_last_6 = float(last_6['ACTUAL'].mean())

            # 7. Update Database
            conn.execute('''
                UPDATE daily_prospects 
                SET score_last_game = ?, 
                    hits_last_6_over = ?, 
                    hits_last_6_under = ?, 
                    avg_last_6 = ?
                WHERE player_id = ? AND prop_type = ?
            ''', (score_last_game, hits_over, hits_under, avg_last_6, p_id, prop))
            
            print(f"Synced {row['player_name']} {prop}: Last={score_last_game}, Over={hits_over}/6")

        except Exception as e:
            print(f"Failed sync for {row['player_name']}: {e}")
            continue

    conn.commit()
    conn.close()
    print("Performance Sync Complete.")

if __name__ == "__main__":
    sync_player_performance()