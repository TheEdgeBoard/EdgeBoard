import numpy as np
import sqlite3
import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'edgeboard.db')

def run_weighted_sims_with_sos():
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Load your core tables
    try:
        players_df = pd.read_sql("SELECT id, player_name, team, prop_type, line_value, opponent FROM active_lines", conn)
        logs_df = pd.read_sql("SELECT * FROM player_logs", conn)
        metrics_df = pd.read_sql("SELECT * FROM team_metrics", conn)
    except Exception as e:
        print(f"❌ Database Error: {e}")
        return

    # Calculate league averages for normalization
    avg_pace = metrics_df['pace'].mean()
    avg_def = metrics_df['defensive_rating'].mean()
    
    results = []
    print(f"🚀 Running simulations for {len(players_df)} props...")

    for _, p in players_df.iterrows():
        name, team, prop, opp = p['player_name'], p['team'], p['prop_type'], p['opponent']
        line = float(p['line_value'])
        
        p_logs = logs_df[logs_df['player_name'] == name].copy()
        if p_logs.empty: 
            continue
        
        # --- FIX: Define outcomes based on prop type ---
        col_map = {'PTS': 'pts', 'REB': 'reb', 'AST': 'ast', 'FG3M': 'threes_made'}
        if prop in col_map:
            outcomes = p_logs[col_map[prop]].values
        elif prop == 'PRA':
            outcomes = (p_logs['pts'] + p_logs['reb'] + p_logs['ast']).values
        elif prop == 'PR':
            outcomes = (p_logs['pts'] + p_logs['reb']).values
        elif prop == 'RA':
            outcomes = (p_logs['reb'] + p_logs['ast']).values
        else:
            continue

        # --- CALCULATE SOS (PAST DIFFICULTY) ---
        try:
            sos_past = metrics_df.loc[metrics_df['team_abbrev'] == team, 'defensive_rating'].values[0] / avg_def
        except:
            sos_past = 1.0

        # --- CALCULATE CURRENT MATCHUP FACTOR ---
        opp_stats = metrics_df[metrics_df['team_abbrev'] == opp]
        if not opp_stats.empty:
            pace_factor = opp_stats['pace'].values[0] / avg_pace
            def_factor = opp_stats['defensive_rating'].values[0] / avg_def
            matchup_factor = pace_factor * def_factor
        else:
            matchup_factor = 1.0

        # Final SOS-Adjusted Multiplier
        final_multiplier = matchup_factor / sos_past

        # --- MONTE CARLO SIMULATION (10,000 iterations) ---
        base_samples = np.random.choice(outcomes, size=10000, replace=True)
        noise = np.random.normal(1.0, 0.05, 10000) 
        sim_results = base_samples * final_multiplier * noise
        
        prob_over = np.sum(sim_results > line) / 10000
        prob_over = max(0.02, min(0.98, prob_over))

        suggestion = "OVER" if prob_over > 0.54 else "UNDER"
        display_prob = prob_over if suggestion == "OVER" else (1 - prob_over)

        results.append({
            'player_name': name, 'prop_type': prop, 'line_value': line,
            'suggestion': suggestion,
            'win_rate_10': round(display_prob * 100, 1),
            'proj_10': round(sim_results.mean(), 2)
        })

    if results:
        pd.DataFrame(results).to_sql('sim_results', conn, if_exists='replace', index=False)
        print(f"✅ Successfully saved {len(results)} simulations to 'sim_results' table.")
    else:
        print("⚠️ No results generated. Check if player_logs match active_lines.")
        
    conn.close()

# --- THE MISSING PART: EXECUTION ---
if __name__ == "__main__":
    run_weighted_sims_with_sos()