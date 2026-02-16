from flask import Flask, jsonify, request
import sqlite3
import os
import subprocess
import random
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Load environment variables for security (if using .env file)
load_dotenv()

app = Flask(__name__)

# --- CONFIGURATION ---
# IMPORTANT: Use your 16-character Google App Password here
# Replace with your actual credentials or load from os.environ
EMAIL_ADDRESS = "edgeboardanalytics@gmail.com"
EMAIL_PASSWORD = "kxet mzih snlr cqcy" 

def get_db_connection():
    """Points to the specific path on PythonAnywhere."""
    path = '/home/TheEdgeBoard/EdgeBoard/edgeboard.db'
    if not os.path.exists(path):
        path = 'edgeboard.db' # Fallback for local testing
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def send_code(target_email, code):
    """Sends 6-digit verification codes via Gmail."""
    msg = MIMEText(f"Your EdgeBoard activation code is: {code}")
    msg['Subject'] = 'EdgeBoard Access Code'
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = target_email
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
    except Exception as e:
        print(f"SMTP Error: {e}")

# --- WEB ROUTES ---
@app.route('/')
def home():
    """Serves the main dashboard."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return open(os.path.join(base_dir, 'index.html'), encoding='utf-8').read()

# --- AUTHENTICATION ---
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                        (data['username'], data['password'])).fetchone()
    conn.close()
    if user:
        return jsonify({
            "status": "success", 
            "role": user['role'], 
            "username": user['username']
        })
    return jsonify({"status": "error", "message": "Invalid Credentials"}), 401

# --- CRM: ONBOARDING ---
@app.route('/api/create-user', methods=['POST'])
def create_user():
    if request.headers.get('X-User-Role') != 'admin':
        return jsonify({"status": "error"}), 403
    
    data = request.json
    code = str(random.randint(100000, 999999))
    
    conn = get_db_connection()
    conn.execute('''INSERT OR REPLACE INTO pending_users 
                    (username, password, role, full_name, phone, email, code) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (data['username'], data['password'], 'viewer', 
                 data['full_name'], data['phone'], data['email'], code))
    conn.commit()
    conn.close()
    
    try:
        send_code(data['email'], code)
        return jsonify({"status": "pending", "message": "Code sent to email."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Email failed: {str(e)}"})

# --- CRM: VERIFICATION ---
@app.route('/api/verify-code', methods=['POST'])
def verify_code():
    data = request.json
    conn = get_db_connection()
    pending = conn.execute('SELECT * FROM pending_users WHERE username = ? AND code = ?',
                           (data['username'], data['code'])).fetchone()
    if pending:
        conn.execute('''INSERT INTO users (username, password, role, full_name, phone, email) 
                        VALUES (?, ?, ?, ?, ?, ?)''',
                    (pending['username'], pending['password'], 'viewer', 
                     pending['full_name'], pending['phone'], pending['email']))
        conn.execute('DELETE FROM pending_users WHERE username = ?', (pending['username'],))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Account Activated!"})
    return jsonify({"status": "error", "message": "Invalid Code"}), 400

# --- CRM: USER MANAGEMENT (ADMIN ONLY) ---
@app.route('/api/get-users', methods=['GET'])
def get_users():
    if request.headers.get('X-User-Role') != 'admin':
        return jsonify({"status": "error"}), 403
    conn = get_db_connection()
    users = conn.execute('SELECT username, password, full_name, email, phone FROM users WHERE role = "viewer"').fetchall()
    conn.close()
    return jsonify([dict(row) for row in users])

@app.route('/api/delete-user/<username>', methods=['DELETE'])
def delete_user(username):
    if request.headers.get('X-User-Role') != 'admin':
        return jsonify({"status": "error"}), 403
    conn = get_db_connection()
    conn.execute('DELETE FROM users WHERE username = ?', (username,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": f"User {username} deleted."})

# --- DATA & ANALYTICS: HIGH-CONVICTION OUTPUT ---
@app.route('/api/data')
def get_data():
    conn = get_db_connection()
    # Updated Query: Selects suggestion (Over/Under) and win_rate for the new UI
    rows = conn.execute('''
        SELECT player_name, team, prop_type, line_value, suggestion, projected_value, ev_edge, win_rate, context_tags 
        FROM sim_results 
        ORDER BY ev_edge DESC
    ''').fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

# --- SYSTEM SYNC: THE INTELLIGENCE PIPELINE ---
@app.route('/api/sync', methods=['POST'])
def manual_sync():
    """
    Runs the full intelligence pipeline in the strict logical order required 
    for High-Conviction filtering (4/6 Hits + 60% Sim Win Rate).
    """
    if request.headers.get('X-User-Role') != 'admin':
        return jsonify({"status": "error"}), 403
    
    base_path = "/home/TheEdgeBoard/EdgeBoard/"
    # For local testing, remove the base_path prefix if needed
    if not os.path.exists(base_path): base_path = ""

    try:
        # 1. MARKET DATA: Fetch fresh lines for all 9 categories (PTS, REB, AST, 3PM, FGA, etc.)
        subprocess.run(["python3", os.path.join(base_path, "sync_odds.py")], check=True)
        
        # 2. PERFORMANCE DATA: Calc 4/6 consistency and Last Game hit/miss against those specific lines
        subprocess.run(["python3", os.path.join(base_path, "sync_stats.py")], check=True)
        
        # 3. CONTEXT DATA: Fetch Opponent Pace/Defense ranks and Injury Reports
        subprocess.run(["python3", os.path.join(base_path, "sync_matchups.py")], check=True)
        subprocess.run(["python3", os.path.join(base_path, "sync_injuries.py")], check=True)
        
        # 4. SIMULATION ENGINE: Run Monte Carlo with 60% Win Rate Threshold
        subprocess.run(["python3", os.path.join(base_path, "run_sims.py")], check=True)
        
        return jsonify({"status": "success", "message": "High-Conviction Sync Complete."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Pipeline Error: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)