import numpy as np
import sqlite3
import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'edgeboard.db')

def run_weighted_sims_with_sos():
    conn = sqlite3.connect(DB_PATH)
    
    try:
        players_df = pd.read_sql("SELECT id, player_name, team, prop_type, line_value, opponent FROM active_lines", conn)
        logs_df = pd.read_sql("SELECT * FROM player_logs", conn)
        metrics_df = pd.read_sql("SELECT * FROM team_metrics", conn)
    except Exception as e:
        print(f"❌ Database Error: {e}")
        return

    avg_pace = metrics_df['pace'].mean()
    avg_def = metrics_df['defensive_rating'].mean()
    
    results = []
    print(f"🚀 Running simulations for {len(players_df)} props...")

    for _, p in players_df.iterrows():
        name, team, prop, opp = p['player_name'], p['team'], p['prop_type'], p['opponent']
        line = float(p['line_value'])
        
        # Sort logs by date to get the most recent games first
        p_logs = logs_df[logs_df['player_name'] == name].copy()
        if p_logs.empty: continue
        
        # Base Data Object
        player_result = {
            'player_name': name, 
            'prop_type': prop, 
            'line_value': line,
            'suggestion': 'OVER' # Default
        }

        # Calculate for each window
        for w in [3, 5, 10, 14]:
            subset = p_logs.head(w) # Take most recent W games
            if len(subset) < 2: continue

            col_map = {'PTS': 'pts', 'REB': 'reb', 'AST': 'ast', 'FG3M': 'threes_made'}
            if prop in col_map:
                outcomes = subset[col_map[prop]].values
            elif prop == 'PRA':
                outcomes = (subset['pts'] + subset['reb'] + subset['ast']).values
            else: continue

            # SOS Logic
            try:
                sos_past = metrics_df.loc[metrics_df['team_abbrev'] == team, 'defensive_rating'].values[0] / avg_def
                opp_stats = metrics_df[metrics_df['team_abbrev'] == opp]
                matchup_factor = (opp_stats['pace'].values[0] / avg_pace) * (opp_stats['defensive_rating'].values[0] / avg_def)
                multiplier = matchup_factor / sos_past
            except:
                multiplier = 1.0

            # 10k Simulations
            sim_results = np.random.choice(outcomes, size=10000, replace=True) * multiplier * np.random.normal(1.0, 0.05, 10000)
            prob_over = np.sum(sim_results > line) / 10000
            
            # Save specific window data
            player_result[f'win_rate_{w}'] = round(prob_over * 100, 1)
            player_result[f'ev_{w}'] = round((prob_over - 0.54) * 100, 1) # Simple EV calc
            player_result[f'proj_{w}'] = round(sim_results.mean(), 2)

        results.append(player_result)

    if results:
        pd.DataFrame(results).to_sql('sim_results', conn, if_exists='replace', index=False)
        print(f"✅ Saved {len(results)} multi-window simulations.")
    conn.close()

if __name__ == "__main__":
    run_weighted_sims_with_sos()