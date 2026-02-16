To prevent your system from crashing during the All-Star break or on rare "no-game" days (like Thanksgiving or the NCAA Championship), we need to add Graceful Exit logic.

This ensures that if the database is empty, the scripts simply say "No data found" and close cleanly (Status 0) rather than panicking and crashing (Status 1).

1. The "Season-Proof" run_sims.py
I have added a check at the beginning. If the daily_prospects table is empty or missing, the script will print a message and exit without trying to perform any math.

Python
import numpy as np
import sqlite3
import pandas as pd
import os

DB_PATH = '/home/TheEdgeBoard/EdgeBoard/edgeboard.db'

def run_contextual_simulations():
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # 1. Verify Database State
        tables_query = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        tables = [t[0] for t in tables_query]
        
        if 'daily_prospects' not in tables:
            print("STANDBY: No daily prospects table found. (Expected during All-Star Break)")
            return

        players = pd.read_sql("SELECT * FROM daily_prospects", conn)

        # 2. Check for Empty Data (The "Break" Safeguard)
        if players.empty:
            print("SYSTEM STANDBY: 0 games scheduled for today. Skipping simulations.")
            # Clear old results so we don't show stale bets from last week
            conn.execute("DELETE FROM sim_results")
            conn.commit()
            return

        # 3. Load Matchups and Injuries
        matchups = pd.read_sql("SELECT * FROM team_matchup_data", conn) if 'team_matchup_data' in tables else pd.DataFrame()
        injuries = pd.read_sql("SELECT team_id FROM injuries_today", conn)['team_id'].tolist() if 'injuries_today' in tables else []

        results = []
        for _, p in players.iterrows():
            # BASELINE (60/40 Weighting)
            baseline = (p['avg_last_6'] * 0.6) + (p['avg_season'] * 0.4)
            
            # MATCHUP ADJUSTMENTS (Default to 1.0 if no data)
            m = matchups[matchups['team_id'] == p['opponent_id']] if not matchups.empty else pd.DataFrame()
            pace_adj = (m['pace_factor'].values[0] / 100) if not m.empty else 1.0
            def_adj = (110 / m['def_rating'].values[0]) if not m.empty else 1.0
            usage_adj = 1.15 if p['team_id'] in injuries else 1.0
            
            # MATH: Adjusted Mean
            mu_adj = baseline * pace_adj * def_adj * usage_adj
            
            # SIMULATION (10k Iterations)
            sim_outcomes = np.random.poisson(mu_adj, 10000)
            win_prob = np.sum(sim_outcomes > p['market_line']) / 10000
            edge = (win_prob - p['implied_probability']) * 100
            
            # TAGGING
            tags = []
            if p['avg_last_6'] > p['avg_season']: tags.append("🔥")
            if pace_adj > 1.03: tags.append("🏎️")
            if usage_adj > 1.0: tags.append("📈")

            results.append({
                'player_name': p['player_name'],
                'team': p['team_id'],
                'prop_type': p['prop_type'],
                'line_value': p['market_line'],
                'projected_value': round(mu_adj, 2),
                'ev_edge': round(edge, 2),
                'context_tags': " ".join(tags)
            })

        # 4. Save Clean Results
        df_final = pd.DataFrame(results)
        if not df_final.empty:
            df_final[df_final['ev_edge'] >= 0].sort_values('ev_edge', ascending=False).to_sql('sim_results', conn, if_exists='replace', index=False)
            print(f"Success: {len(df_final)} simulations processed.")
        else:
            print("Simulations ran, but no positive edges were found.")

    except Exception as e:
        print(f"Simulation Component Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run_contextual_simulations()