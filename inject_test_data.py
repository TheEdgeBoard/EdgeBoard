import sqlite3

def inject_data():
    conn = sqlite3.connect('edgeboard.db')
    c = conn.cursor()

    print("💉 Injecting TEST DATA into the database...")

    # 1. Clear existing lines
    c.execute("DELETE FROM active_lines")

    # 2. Insert Fake Betting Lines for tonight
    # We use players that we know you have stats for (LeBron, Curry, etc.)
    
    test_bets = [
        # LeBron James: Line 24.5 Points vs East All-Stars
        ("LeBron James", "LAL", "EST", "player_points", 24.5, -110, "2026-02-15T20:00:00Z", "DraftKings"),
        ("LeBron James", "LAL", "EST", "player_assists", 7.5, -120, "2026-02-15T20:00:00Z", "FanDuel"),
        
        # Steph Curry: Line 4.5 Threes
        ("Stephen Curry", "GSW", "EST", "player_threes", 4.5, -130, "2026-02-15T20:00:00Z", "MGM"),
        ("Stephen Curry", "GSW", "EST", "player_points", 26.5, -110, "2026-02-15T20:00:00Z", "DraftKings"),

        # Nikola Jokic: Line 11.5 Rebounds
        ("Nikola Jokic", "DEN", "EST", "player_rebounds", 11.5, -115, "2026-02-15T20:00:00Z", "Caesars"),
        ("Nikola Jokic", "DEN", "EST", "player_assists", 9.5, +105, "2026-02-15T20:00:00Z", "FanDuel"),
        
        # Luka Doncic: Line 31.5 Points
        ("Luka Doncic", "DAL", "EST", "player_points", 31.5, -110, "2026-02-15T20:00:00Z", "MGM"),
    ]

    c.executemany('''
        INSERT INTO active_lines 
        (player_name, team, opponent, prop_type, line_value, odds_over, game_time, merchant_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', test_bets)

    conn.commit()
    conn.close()
    print(f"✅ Successfully injected {len(test_bets)} test betting lines.")
    print("👉 Now run 'python run_sims.py' to see the magic happen.")

if __name__ == "__main__":
    inject_data()