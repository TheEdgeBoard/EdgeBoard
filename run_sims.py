import numpy as np
import sqlite3
import pandas as pd

def run_simulations():
    conn = sqlite3.connect('/home/TheEdgeBoard/EdgeBoard/edgeboard.db')
    
    # Load all context
    players = pd.read_sql("SELECT * FROM daily_prospects", conn)
    matchups = pd.read_sql("SELECT * FROM team_matchup_data", conn)
    injuries = pd.read_sql("SELECT team_id FROM injuries_today", conn)['team_id'].tolist()

    results = []

    for _, p in players.iterrows():
        # 1. BASELINE (60% Last 6 games / 40% Season)
        baseline = (p['avg_last_6'] * 0.6) + (p['avg_season'] * 0.4)
        
        # 2. MATCHUP ADJUSTMENTS
        m = matchups[matchups['team_id'] == p['opponent_id']]
        pace_adj = (m['pace_factor'].values[0] / 100) if not m.empty else 1.0
        # Lower DRtg means better defense (League avg ~110)
        def_adj = (110 / m['def_rating'].values[0]) if not m.empty else 1.0
        
        # 3. USAGE ADJUSTMENT
        usage_adj = 1.15 if p['team_id'] in injuries else 1.0
        
        # FINAL PROJECTED MEAN (μ)
        mu_adj = baseline * pace_adj * def_adj * usage_adj
        
        # 4. MONTE CARLO (10,000 Trials)
        # Using Poisson for counting stats
        sim_results = np.random.poisson(mu_adj, 10000)
        win_prob = np.sum(sim_results > p['market_line']) / 10000
        edge = (win_prob - p['implied_prob']) * 100
        
        # 5. TAGGING
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

    df_final = pd.DataFrame(results).sort_values('ev_edge', ascending=False)
    df_final[df_final['ev_edge'] >= 0].to_sql('sim_results', conn, if_exists='replace', index=False)
    conn.close()

if __name__ == "__main__":
    run_simulations()