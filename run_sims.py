import sqlite3
import numpy as np
import pandas as pd

# --- CONFIGURATION ---
SIMULATIONS = 10000       # 10k runs per bet is standard for Monte Carlo
LEAGUE_AVG_PACE = 99.5    # 2025-26 Estimate
LEAGUE_AVG_DEF_RTG = 115.0 # 2025-26 Estimate

def get_db_connection():
    return sqlite3.connect('edgeboard.db')

def calculate_ev(win_prob, american_odds):
    # Convert American Odds (e.g. -110 or +150) to Decimal
    if american_odds > 0:
        decimal_odds = (american_odds / 100) + 1
    else:
        decimal_odds = (100 / abs(american_odds)) + 1
        
    # EV Formula: (Win % * Profit) - (Loss % * Stake)
    stake = 100
    profit = (stake * decimal_odds) - stake
    
    ev_value = (win_prob * profit) - ((1 - win_prob) * stake)
    
    # Return as ROI Percentage
    return (ev_value / stake) * 100

def run_simulation_logic():
    conn = get_db_connection()
    c = conn.cursor()

    print("🧠 Starting Monte Carlo Simulation Engine...")

    # 1. Get Active Lines
    try:
        lines_df = pd.read_sql("SELECT * FROM active_lines", conn)
    except Exception as e:
        print("⚠️ No active lines found. Did you run 'sync_odds.py'?")
        return

    if lines_df.empty:
        print("⚠️ Database has no betting lines. Run 'sync_odds.py' first!")
        return

    # Clear old results
    c.execute("DELETE FROM sim_results")
    print(f"   Analyzing {len(lines_df)} betting lines...")

    # 2. Loop through each line
    results_count = 0
    for index, row in lines_df.iterrows():
        player_name = row['player_name']
        prop_type = row['prop_type'] # e.g. 'player_points'
        line_value = row['line_value']
        odds = row['odds_over']
        opponent = row['opponent'] # e.g. 'Lakers' or 'LAL'
        
        # 3. Get Player Stats (Last 6 Games)
        # We assume the name matches exactly. Real production code needs fuzzy matching.
        logs_df = pd.read_sql(f"SELECT * FROM player_logs WHERE player_name = '{player_name}'", conn)
        
        if len(logs_df) < 3:
            # Skip players with insufficient data
            continue

        # 4. Map Prop Type to Database Column
        stat_map = {
            'player_points': 'pts',
            'player_rebounds': 'reb',
            'player_assists': 'ast',
            'player_threes': 'threes_made'
        }
        
        if prop_type not in stat_map:
            continue # Skip unsupported props like 'steals' for now
            
        target_stat = stat_map[prop_type]
        base_lambda = logs_df[target_stat].mean() # The Player's Baseline

        # 5. Get Opponent Adjustments (Pace & Defense)
        # We try to match 'opponent' (from Odds API) to 'team_abbrev' (from NBA.com)
        # This is tricky because Odds API might say "Los Angeles Lakers" and NBA says "LAL"
        # For V1, we will just use League Average if we can't find a match
        
        # Simple lookup attempt
        opp_metrics = pd.read_sql(f"SELECT * FROM team_metrics WHERE team_abbrev = '{opponent}' OR team_abbrev = '{opponent[:3].upper()}'", conn)
        
        if not opp_metrics.empty:
            opp_pace = opp_metrics.iloc[0]['pace']
            opp_def = opp_metrics.iloc[0]['defensive_rating']
            
            # THE ADJUSTMENT:
            # Faster Pace = More Possessions = Higher Stats
            # Bad Defense (High Rating) = More Points Allowed = Higher Stats
            pace_factor = opp_pace / LEAGUE_AVG_PACE
            def_factor = opp_def / LEAGUE_AVG_DEF_RTG
            
            adj_lambda = base_lambda * pace_factor * def_factor
        else:
            # Fallback: No adjustment
            adj_lambda = base_lambda

        # 6. RUN SIMULATION (Poisson Distribution)
        sim_results = np.random.poisson(adj_lambda, SIMULATIONS)
        
        # Calculate Win %
        wins = np.sum(sim_results > line_value)
        win_prob = wins / SIMULATIONS
        
        # Calculate EV
        ev = calculate_ev(win_prob, odds)
        
        # 7. Save to Database
        c.execute('''
            INSERT INTO sim_results (player_name, prop_type, projected_value, win_probability, ev_edge)
            VALUES (?, ?, ?, ?, ?)
        ''', (player_name, prop_type, round(adj_lambda, 1), round(win_prob * 100, 1), round(ev, 1)))
        
        results_count += 1
        if results_count % 10 == 0:
            print(f"   🎲 Simulating... {player_name} ({prop_type}): EV {ev:.1f}%")

    conn.commit()
    conn.close()
    print(f"✅ Simulation Complete. {results_count} bets analyzed and saved.")

if __name__ == "__main__":
    run_simulation_logic()