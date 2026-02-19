from flask import Flask, jsonify, request, render_template_string
import sqlite3
import os
import subprocess
import smtplib
from email.message import EmailMessage

app = Flask(__name__)

# --- CONFIGURATION ---
BASE_DIR = '/home/TheEdgeBoard/EdgeBoard/'
DB_PATH = os.path.join(BASE_DIR, 'edgeboard.db')
ADMIN_EMAIL = "edgeboardanalytics@gmail.com"
EMAIL_PASS = "mzac cwka rtek biwj"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- STATIC PAGES ---
@app.route('/tos')
def tos_page():
    return render_template_string('<body style="background:#0f172a;color:white;padding:40px;font-family:sans-serif;"><h1>Terms of Service</h1><p>Usage of EdgeBoard is for informational purposes only.</p><a href="/" style="color:#10b981;">Back to Home</a></body>')

@app.route('/about')
def about_page():
    return render_template_string('<body style="background:#0f172a;color:white;padding:40px;font-family:sans-serif;"><h1>About EdgeBoard</h1><p>Data-driven sports analytics.</p><a href="/" style="color:#10b981;">Back to Home</a></body>')

# --- MAIN ROUTES ---
@app.route('/')
def home():
    try:
        return open(os.path.join(BASE_DIR, 'index.html'), encoding='utf-8').read()
    except Exception as e:
        return f"Error loading site: {str(e)}"

@app.route('/setup-password')
def setup_password_page():
    username = request.args.get('user')
    if not username: return "Invalid link.", 400
    return render_template_string('''
        <!DOCTYPE html><html><head><title>Setup Password</title><script src="https://cdn.tailwindcss.com"></script></head>
        <body class="bg-gray-950 text-white flex items-center justify-center min-h-screen">
            <div class="bg-gray-900 p-8 rounded-2xl w-full max-w-sm text-center border border-gray-800">
                <h1 class="text-emerald-400 font-bold text-xl mb-4">EDGE BOARD</h1>
                <input id="pw" type="password" placeholder="New Password" class="w-full bg-gray-800 p-3 rounded mb-4 text-white">
                <button onclick="activate()" class="w-full bg-emerald-500 text-black font-bold py-3 rounded">ACTIVATE ACCOUNT</button>
            </div>
            <script>
                async function activate() {
                    const pass = document.getElementById('pw').value;
                    const res = await fetch('/api/activate-account', {
                        method: 'POST', headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({username: '{{user}}', password: pass})
                    });
                    const data = await res.json();
                    if(data.status === 'success') window.location.href = '/';
                    else alert(data.message);
                }
            </script>
        </body></html>
    ''', user=username)

# --- API ROUTES ---
@app.route('/api/activate-account', methods=['POST'])
def activate_account():
    data = request.json
    conn = get_db_connection()
    conn.execute('UPDATE users SET password = ?, status = "active" WHERE username = ?', (data['password'], data['username']))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (data['username'], data['password'])).fetchone()
    conn.close()
    if user: return jsonify({"status": "success", "role": user['role'], "username": user['username']})
    return jsonify({"status": "error", "message": "Invalid Credentials"}), 401

@app.route('/api/data')
def get_data():
    sport = request.args.get('sport', 'NBA')
    if sport != 'NBA': return jsonify([]) # Empty list for Coming Soon tabs

    conn = get_db_connection()
    # QUERY LOGIC: 
    # 1. Join Sim Results + Market Data
    # 2. Filter: Lineup Flag must be 0 (No changes)
    # 3. Filter: Win Rate >= 60% AND EV > 0 (Profitable Only)
    # 4. Filter: Must have hit last game (last_game_hit = 1)
    query = '''
        SELECT s.*, p.market_line, p.trend_history, p.last_game_hit, s.sportsbook, s.best_odds
        FROM sim_results s 
        JOIN daily_prospects p ON s.player_name = p.player_name AND s.prop_type = p.prop_type
        WHERE s.lineup_flag = 0 
        AND s.win_rate_10 >= 0.60 
        AND s.ev_10 > 0
        AND p.last_game_hit = 1
    '''
    try:
        results = conn.execute(query).fetchall()
    except:
        # Fallback if specific columns are empty/missing in dev
        results = []
    conn.close()
    return jsonify([dict(row) for row in results])

# --- ADMIN & SYNC ROUTES ---
@app.route('/api/sync/odds', methods=['POST'])
def sync_odds():
    try:
        subprocess.run(["/usr/bin/python3", os.path.join(BASE_DIR, "sync_odds.py")], check=True)
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)})

@app.route('/api/sync/stats', methods=['POST'])
def sync_stats():
    try:
        subprocess.run(["/usr/bin/python3", os.path.join(BASE_DIR, "sync_stats.py")], check=True)
        # Note: We usually run run_sims.py right after stats
        subprocess.run(["/usr/bin/python3", os.path.join(BASE_DIR, "run_sims.py")], check=True)
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True)