import sqlite3
import os

# --- DYNAMIC DB PATH ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'edgeboard.db')

def wipe_bad_stats():
    print("🧹 Starting local database cleanup...")
    if not os.path.exists(DB_PATH):
        print("❌ Database not found. Check your file path!")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tables we want to wipe completely to remove 2018 data and duplicates
    tables_to_wipe = ['player_logs', 'sim_results', 'team_metrics']
    
    for table in tables_to_wipe:
        try:
            cursor.execute(f"DELETE FROM {table}")
            print(f"   🗑️ Wiped all data from: {table}")
        except sqlite3.OperationalError:
            print(f"   ⚠️ Table {table} does not exist yet. Skipping.")
            
    conn.commit()
    conn.close()
    print("✅ Local stats wiped. Ready for fresh 2026 data!")

if __name__ == "__main__":
    wipe_bad_stats()