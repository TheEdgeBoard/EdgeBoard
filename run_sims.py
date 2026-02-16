import numpy as np
import sqlite3
import pandas as pd

DB_PATH = '/home/TheEdgeBoard/EdgeBoard/edgeboard.db'

def run_multi_window_sims():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    players = pd.read_sql("SELECT * FROM daily_prospects", conn)
    try:
        opponents = pd.read_sql("SELECT * FROM team_matchup_data", conn)
        injuries = pd.read_sql("SELECT team_id FROM injuries_today", conn)
        out_team_ids = injuries['team_id'].tolist()
    except:
        opponents = pd.DataFrame()
        out_team_ids = []

    results = []
    print(f"Running Multi-Sims for {len(players)} players...")

    for _, p in players.iterrows():
        # Context (Defense, Pace, Injuries)
        matchup = opponents[opponents['team_id'] == p['opponent_id']] if not opponents.empty else pd.DataFrame()
        pace_adj = (matchup.iloc[0]['pace_factor'] / 100) if not matchup.empty else 1.0
        def_adj = (matchup.iloc[0]['def_rating'] / 110) if not matchup.empty else 1.0
        usage_adj = 1.10 if p['team_id'] in out_team_ids else 1.0
        context_multiplier = pace_adj * def_adj * usage_adj
        
        sim_data = {}
        
        # --- LOOP: RUN 4 SIMULATIONS ---
        windows = [3, 5, 10, 14]
        for w in windows:
            # Baseline = Average of this specific window
            baseline = p[f'avg_last_{w}']
            if pd.isna(baseline) or baseline == 0: baseline = p['avg_season']
            
            # Run Sim
            mu_final = baseline * context_multiplier
            outcomes = np.random.poisson(mu_final, 5000)
            
            # Calculate Probabilities
            prob_over = np.sum(outcomes > p['market_line']) / 5000
            
            # Store Results
            sim_data[f'proj_{w}'] = round(mu_final, 2)
            sim_data[f'win_rate_{w}'] = round(prob_over * 100, 1) # Raw Over %
            sim_data[f'ev_{w}'] = round((prob_over - 0.52) * 100, 1) # Raw Over EV

        # --- DETERMINE PRIMARY SUGGESTION ---
        # Default to 10-game window for direction, but allow UI to flip data
        suggestion = "OVER" if sim_data['ev_10'] > 0 else "UNDER"
        
        # If UNDER, flip the EV/WinRate math for storage so positive = good
        if suggestion == "UNDER":
            for w in windows:
                sim_data[f'ev_{w}'] = round(((100 - sim_data[f'win_rate_{w}']) / 100 - 0.52) * 100, 1)
                sim_data[f'win_rate_{w}'] = round(100 - sim_data[f'win_rate_{w}'], 1)

        row_data = {
            'player_name': p['player_name'], 'team': p['team_id'], 
            'prop_type': p['prop_type'], 'line_value': p['market_line'],
            'suggestion': suggestion, 'context_tags': '',
            'hits_3_over': p['hits_last_3_over'], 'hits_3_under': p['hits_last_3_under'],
            'hits_5_over': p['hits_last_5_over'], 'hits_5_under': p['hits_last_5_under'],
            'hits_10_over': p['hits_last_10_over'], 'hits_10_under': p['hits_last_10_under'],
            'hits_14_over': p['hits_last_14_over'], 'hits_14_under': p['hits_last_14_under']
        }
        row_data.update(sim_data)
        results.append(row_data)

    if results:
        df = pd.DataFrame(results)
        df.to_sql('sim_results', conn, if_exists='replace', index=False)
        print(f"Saved {len(results)} profiles.")
    
    conn.close()

if __name__ == "__main__":
    run_multi_window_sims()