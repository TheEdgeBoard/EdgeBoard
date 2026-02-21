import sqlite3
import os

# --- DYNAMIC DB PATH ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'edgeboard.db')

def sync_stats():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Safely add our trend columns if they don't exist
    try: cursor.execute("ALTER TABLE active_lines ADD COLUMN trend_history TEXT")
    except sqlite3.OperationalError: pass 
    try: cursor.execute("ALTER TABLE active_lines ADD COLUMN last_game_hit INTEGER")
    except sqlite3.OperationalError: pass

    print("Starting local filter and calculating trends...")
    
    # FIX: Explicitly selecting 'id' as it is the Primary Key in your schema
    lines = cursor.execute("SELECT id, player_name, prop_type, line_value FROM active_lines WHERE line_value IS NOT NULL").fetchall()

    rows_to_delete = []
    updates = []

    for line in lines:
        # FIX: Access the data using the 'id' key
        row_id = line['id']
        player = line['player_name']
        prop = line['prop_type']
        
        # Ensure line_value is treated as a number for comparison
        try:
            line_val = float(line['line_value'])
        except (ValueError, TypeError):
            continue

        # Pull all of this player's downloaded games from our local logs, newest first
        logs = cursor.execute(
            "SELECT * FROM player_logs WHERE player_name = ? ORDER BY game_date DESC", 
            (player,)
        ).fetchall()

        # If they have no data, mark for deletion to keep the board clean
        if not logs:
            rows_to_delete.append((row_id,))
            continue

        hits = []
        for log in logs:
            pts = int(log['pts'] or 0)
            reb = int(log['reb'] or 0)
            ast = int(log['ast'] or 0)
            threes = int(log['threes_made'] or 0)

            achieved_stat = 0
            if prop == 'PTS': achieved_stat = pts
            elif prop == 'REB': achieved_stat = reb
            elif prop == 'AST': achieved_stat = ast
            elif prop == 'FG3M': achieved_stat = threes
            elif prop == 'PRA': achieved_stat = pts + reb + ast
            elif prop == 'PR': achieved_stat = pts + reb
            elif prop == 'RA': achieved_stat = reb + ast

            # Record a '1' if they hit the over, '0' if they missed
            hits.append('1' if achieved_stat > line_val else '0')

        # FILTER: Look at index 0 (their most recent game). If it's a 0, kill the prop.
        if hits and hits[0] == '0':
            rows_to_delete.append((row_id,))
        elif hits:
            # If they hit, join their hits into a string (e.g. "1,0,1,1") and queue the update
            trend_str = ",".join(hits)
            updates.append((trend_str, 1, row_id))

    # --- EXECUTE THE DATABASE CHANGES ---
    # Using 'id' here to match the selection above
    if rows_to_delete:
        cursor.executemany("DELETE FROM active_lines WHERE id = ?", rows_to_delete)
        
    if updates:
        cursor.executemany("UPDATE active_lines SET trend_history = ?, last_game_hit = ? WHERE id = ?", updates)

    conn.commit()
    conn.close()

    print(f"Trash Bin: Deleted {len(rows_to_delete)} cold props.")
    print(f"Hot Board: Calculated trends for {len(updates)} surviving props.")

if __name__ == "__main__":
    sync_stats()