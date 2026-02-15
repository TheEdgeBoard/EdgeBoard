from flask import Flask, jsonify, request
import sqlite3
import os
import subprocess
from dotenv import load_dotenv

# Load environment variables for the Cloud
load_dotenv()

app = Flask(__name__)

# Helper to find the database path correctly on PythonAnywhere or Local
def get_db_connection():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'edgeboard.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    # Opens your HTML with UTF-8 encoding to prevent Windows errors
    base_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(base_dir, 'index.html')
    return open(html_path, encoding='utf-8').read()

# --- NEW LOGIN API ---
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                        (username, password)).fetchone()
    conn.close()

    if user:
        return jsonify({
            "status": "success",
            "role": user['role'],
            "username": user['username']
        })
    
    return jsonify({"status": "error", "message": "Access Denied: Invalid Credentials"}), 401

# --- DATA FETCH API (Viewable by everyone) ---
@app.route('/api/data')
def get_data():
    conn = get_db_connection()
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

# --- SECURE SYNC API (Admin Only) ---
@app.route('/api/sync', methods=['POST'])
def manual_sync():
    # Security Check: We expect the role to be passed in a header
    user_role = request.headers.get('X-User-Role')
    
    if user_role != 'admin':
        return jsonify({"status": "error", "message": "FORBIDDEN: Admin access required to sync."}), 403

    try:
        # Runs your authentic data scripts in order
        subprocess.run(["python", "sync_odds.py"], check=True)
        subprocess.run(["python", "sync_stats.py"], check=True)
        subprocess.run(["python", "run_sims.py"], check=True)
        return jsonify({"status": "success", "message": "Global Database Sync Complete!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    # Local development settings
    app.run(debug=True, port=5000)