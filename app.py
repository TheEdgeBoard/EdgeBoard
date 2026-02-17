from flask import Flask, jsonify, request
import sqlite3
import os
import subprocess

app = Flask(__name__)

# --- CONFIGURATION ---
BASE_DIR = '/home/TheEdgeBoard/EdgeBoard/'
DB_PATH = os.path.join(BASE_DIR, 'edgeboard.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    try:
        return open(os.path.join(BASE_DIR, 'index.html'), encoding='utf-8').read()
    except Exception as e:
        return f"Error: index.html not found. {str(e)}"

# --- AUTH ROUTES ---

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                   (data['username'], data['password'], 'viewer'))
        conn.commit()
        return jsonify({"status": "success"})
    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "Username already exists"}), 400
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                       (data['username'], data['password'])).fetchone()
    conn.close()
    if user:
        return jsonify({"status": "success", "role": user['role'], "username": user['username']})
    return jsonify({"status": "error", "message": "Invalid Credentials"}), 401

@app.route('/api/change-password', methods=['POST'])
def change_password():
    data = request.json
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                       (data['username'], data['old_password'])).fetchone()
    if user:
        conn.execute('UPDATE users SET password = ? WHERE username = ?',
                   (data['new_password'], data['username']))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Password updated successfully"})
    conn.close()
    return jsonify({"status": "error", "message": "Verification failed"}), 401

# --- DATA ROUTE ---

@app.route('/api/data')
def get_data():
    conn = get_db_connection()
    # Joined query to get both simulation results and market line info
    query = '''
        SELECT 
            s.player_name, 
            s.prop_type, 
            s.suggestion, 
            s.win_rate_10, 
            s.ev_10,
            p.market_line, 
            p.trend_history 
        FROM sim_results s 
        JOIN daily_prospects p ON s.player_name = p.player_name 
        AND s.prop_type = p.prop_type
    '''
    results = conn.execute(query).fetchall()
    conn.close()
    return jsonify([dict(row) for row in results])

# --- SYNC ROUTES ---

@app.route('/api/sync/odds', methods=['POST'])
def sync_odds_only():
    try:
        subprocess.run(["/usr/bin/python3", os.path.join(BASE_DIR, "sync_odds.py")], check=True)
        return jsonify({"status": "success", "message": "Odds Synced."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/sync/stats', methods=['POST'])
def sync_stats_only():
    try:
        subprocess.run(["/usr/bin/python3", os.path.join(BASE_DIR, "sync_stats.py")], check=True)
        subprocess.run(["/usr/bin/python3", os.path.join(BASE_DIR, "run_sims.py")], check=True)
        return jsonify({"status": "success", "message": "Analytics Complete."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True)