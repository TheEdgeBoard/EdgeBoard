import sqlite3
import pandas as pd
import time
from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players

DB_PATH = '/home/TheEdgeBoard/EdgeBoard/edgeboard.db'

def sync_stats():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # --- 1. SAFEGUARD: Add missing columns if they don't exist yet ---
    try:
        cursor.execute("ALTER TABLE active_lines ADD COLUMN trend_history TEXT")
    except sqlite3.OperationalError:
        pass 
        
    try:
        cursor.execute("ALTER TABLE active_lines ADD COLUMN last_game_hit INTEGER")
    except sqlite3.OperationalError:
        pass

    # ====================================================================
    # --- 2. NEW LOCAL FILTER: Drop bets that missed in the last game ---
    # ====================================================================
    print("Running initial local filter against recent player_logs...")
    
    # Grab all current lines
    initial_lines = cursor.execute("SELECT rowid, player_name, prop_type, line_value FROM active_lines WHERE line_value IS NOT NULL").fetchall()
    rows_to_delete = []

    for line in initial_lines:
        row_id = line['rowid']
        player = line['player_name']
        prop = line['prop_type']
        line_val = float(line['line_value'])

        # Grab the single most recent game for this player from local logs
        # Assuming lower ID = more recent based on your database structure
        recent_log = cursor.execute("SELECT * FROM player_logs WHERE player_name = ? ORDER BY id ASC LIMIT 1", (player,)).fetchone()

        if recent_log:
            try:
                # Safely convert to integers
                pts = int(recent_log['pts'] or 0)
                reb = int(recent_log['reb'] or 0)
                ast = int(recent_log['ast'] or 0)
                threes = int(recent_log['threes_made'] or 0)
            except ValueError:
                continue

            achieved_stat = 0
            
            # Map the prop type to the local database columns
            if prop == 'PTS': achieved_stat = pts
            elif prop == 'REB': achieved_stat = reb
            elif prop == 'AST': achieved_stat = ast
            elif prop == 'FG3M': achieved_stat = threes
            elif prop == 'PRA': achieved_stat = pts + reb + ast
            elif prop == 'PR': achieved_stat = pts + reb
            elif prop == 'RA': achieved_stat = reb + ast
            else:
                continue # Unknown prop, leave it alone

            # If they did NOT hit the OVER in the last game, mark for deletion
            if achieved_stat <= line_val:
                rows_to_delete.append((row_id,))

    # Execute the mass deletion of cold props
    if rows_to_delete:
        cursor.executemany("DELETE FROM active_lines WHERE rowid = ?", rows_to_delete)
        conn.commit()
        print(f"Filtered out {len(rows_to_delete)} cold props that missed their line in the last game.")
    else:
        print("No props filtered out locally.")

    # ====================================================================
    # --- 3. THE HEAVY LIFT: Run API updates on the REMAINING props ---
    # ====================================================================
    print("Fetching remaining hot prospects from API...")
    prospects = cursor.execute("SELECT * FROM active_lines WHERE line_value IS NOT NULL").fetchall()
    
    updates = []
    
    for p in prospects:
        try:
            player_name = p['player_name']
            
            player_dict = players.find_players_by_full_name(player_name)
            if not player_dict:
                print(f"Player ID not found for {player_name}")
                continue
            pid = player_dict[0]['id']
            
            time.sleep(0.6) 
            log = playergamelog.PlayerGameLog(player_id=pid).get_data_frames()[0].head(20)
            
            prop = p['prop_type']
            line = float(p['line_value'])
            
            col = None
            if prop in ['PTS', 'REB', 'AST', 'FG3M']:
                col = prop
            elif prop == 'PRA':
                log['PRA'] = log['PTS'] + log['REB'] + log['AST']
                col = 'PRA'
            elif prop == 'PR':
                log['PR'] = log['PTS'] + log['REB']
                col = 'PR'
            elif prop == 'RA':
                log['RA'] = log['REB'] + log['AST']
                col = 'RA'
                
            if col and not log.empty:
                hits = ['1' if val > line else '0' for val in log[col]]
                trend_str = ",".join(hits)
                last_hit = int(hits[0]) if hits else 0
                
                updates.append((trend_str, last_hit, player_name, prop))
                print(f"Updated {player_name}: Last Hit={last_hit}, Trend={trend_str[:5]}...")
                
        except Exception as e:
            print(f"Skipping {p['player_name']}: {e}")

    # --- 4. UPDATE YOUR DB ---
    if updates:
        cursor.executemany('UPDATE active_lines SET trend_history = ?, last_game_hit = ? WHERE player_name = ? AND prop_type = ?', updates)
        conn.commit()
        print(f"Successfully updated API stats for {len(updates)} props.")
    else:
        print("No stats to update.")
        
    conn.close()

if __name__ == "__main__":
    sync_stats()