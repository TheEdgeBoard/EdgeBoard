from flask import Flask, jsonify, request
import sqlite3
import os

app = Flask(__name__)

# This tells Python where to find your database
def get_db_connection():
    conn = sqlite3.connect('edgeboard.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    # This serves your frozen HTML file
    return open('index.html', encoding='utf-8').read()

@app.route('/api/data')
def get_data():
    conn = get_db_connection()
    # Pulls the joined data from simulations and betting lines
    query = '''
        SELECT 
            s.player_name, 
            s.prop_type, 
            s.projected_value, 
            s.win_probability, 
            s.ev_edge,
            a.line_value,
            a.team,
            a.opponent
        FROM sim_results s
        JOIN active_lines a ON s.player_name = a.player_name AND s.prop_type = a.prop_type
        ORDER BY s.ev_edge DESC
    '''
    rows = conn.execute(query).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@app.route('/api/sync', methods=['POST'])
def manual_sync():
    # This runs when you click the 'Manual Sync' button on the website
    import subprocess
    try:
        # Runs your scripts in order
        subprocess.run(["python", "sync_odds.py"], check=True)
        subprocess.run(["python", "sync_stats.py"], check=True)
        subprocess.run(["python", "run_sims.py"], check=True)
        return jsonify({"status": "success", "message": "Database Sync Complete!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    # Starts the server on port 5000
    app.run(debug=True, port=5000)