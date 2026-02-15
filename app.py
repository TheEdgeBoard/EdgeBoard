from flask import Flask, jsonify, request
import sqlite3
import os
import subprocess
from dotenv import load_dotenv

# Load environment variables (API Keys, etc.)
load_dotenv()

app = Flask(__name__)

# --- DATABASE HELPER ---
def get_db_connection():
    """Maintains a clean connection to the database across local and cloud environments."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'edgeboard.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# --- WEB ROUTES ---
@app.route('/')
def home():
    """Serves the main dashboard interface."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(base_dir, 'index.html')
    return open(html_path, encoding='utf-8').read()

# --- AUTHENTICATION API ---
@app.route('/api/login', methods=['POST'])
def login():
    """Validates credentials and returns the user's role and identity."""
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
            "username": user['username'],
            "full_name": user.get('full_name', 'User')
        })
    
    return jsonify({"status": "error", "message": "Access Denied"}), 401

# --- USER MANAGEMENT API (Admin Only) ---
@app.route('/api/create-user', methods=['POST'])
def create_user():
    """Forces 'viewer' role and saves full contact information for new clients."""
    # 1. Verification: Only an Admin can hit this route
    admin_role = request.headers.get('X-User-Role')
    if admin_role != 'admin':
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    data = request.json
    username = data.get('username')
    password = data.get('password')
    full_name = data.get('full_name')
    phone = data.get('phone')
    email = data.get('email')

    if not username or not password:
        return jsonify({"status": "error", "message": "Required: Username and Password"}), 400

    try:
        conn = get_db_connection()
        # Role is hard-coded as 'viewer' to prevent elevation attacks
        conn.execute('''
            INSERT INTO users (username, password, role, full_name, phone, email) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (username, password, 'viewer', full_name, phone, email))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"Client {full_name} successfully onboarded."})
    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "System Error: Username already exists."})

# --- ANALYTICS DATA API ---
@app.route('/api/data')
def get_data():
    """Fetches the latest simulation results joined with active betting lines."""
    conn = get_db_connection()
    query = '''
        SELECT 
            s.player_name, s.prop_type, s.projected_value, 
            s.win_probability, s.ev_edge,
            a.line_value, a.team, a.opponent
        FROM sim_results s
        JOIN active_lines a ON s.player_name = a.player_name AND s.prop_type = a.prop_type
        ORDER BY s.ev_edge DESC
    '''
    rows = conn.execute(query).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

# --- SYSTEM SYNC API (Admin Only) ---
@app.route('/api/sync', methods=['POST'])
def manual_sync():
    """Triggers the full NBA data pipeline."""
    user_role = request.headers.get('X-User-Role')
    if user_role != 'admin':
        return jsonify({"status": "error", "message": "Forbidden"}), 403

    try:
        # Executes the external Python scripts
        subprocess.run(["python", "sync_odds.py"], check=True)
        subprocess.run(["python", "sync_stats.py"], check=True)
        subprocess.run(["python", "run_sims.py"], check=True)
        return jsonify({"status": "success", "message": "Global Market Data Refreshed."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True, port=5000)