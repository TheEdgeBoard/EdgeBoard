import sqlite3
import pandas as pd
import subprocess

def export_tables():
    conn = sqlite3.connect('edgeboard.db')
    # Export only the sports data
    for table in ['active_lines', 'player_logs', 'sim_results', 'team_metrics']:
        df = pd.read_sql(f"SELECT * FROM {table}", conn)
        df.to_csv(f"{table}.csv", index=False)
    conn.close()
    print("✅ Sports tables exported to CSV.")

    # Push CSVs to GitHub
    subprocess.run(["git", "add", "*.csv"])
    subprocess.run(["git", "commit", "-m", "Daily stats update"])
    subprocess.run(["git", "push", "origin", "main"])

if __name__ == "__main__":
    export_tables()