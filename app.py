from flask import Flask, jsonify, request
import sqlite3
import os
import subprocess
import random
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Load environment variables (for local testing support)
load_dotenv()

app = Flask(__name__)

# --- CONFIGURATION ---
# IMPORTANT: Use your 16-character Google App Password here
# Replace with your actual credentials or load from os.environ
EMAIL_ADDRESS = "your-email@gmail.com"
EMAIL_PASSWORD = "your-app-password" 

def get_db_connection():
    """Points to the specific path on PythonAnywhere."""
    # Production path on PythonAnywhere
    path = '/home/TheEdgeBoard/EdgeBoard/edgeboard.db'
    # Fallback for local testing if production path doesn't exist
    if not os.path.exists('/home/TheEdgeBoard/EdgeBoard/'):
        path = 'edgeboard.db'
        
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

# --- DATA & ANALYTICS: MULTI-SIM OUTPUT ---
@app.route('/api/data')
def get_data():
    conn = get_db_connection()
    # Selects all 4 simulation windows (3, 5, 10, 14) to send to frontend
    rows = conn.execute('SELECT * FROM sim_results ORDER BY ev_10 DESC').fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

# --- SYSTEM SYNC ROUTES ---

@app.route('/api/sync/odds', methods=['POST'])
def sync_odds_only():
    """Step 1: Just fetch the latest lines (Fast)."""
    if request.headers.get('X-User-Role') != 'admin':
        return jsonify({"status": "error"}), 403
    
    base_path = "/home/TheEdgeBoard/EdgeBoard/"
    if not os.path.exists(base_path): base_path = "" # Local fallback

    try:
        # Capture output to check for "No games" message
        result = subprocess.run(
            ["python3", os.path.join(base_path, "sync_odds.py")], 
            check=True, 
            capture_output=True, 
            text=True
        )
        
        # Check standard output for the "No games" message
        if "No games scheduled" in result.stdout:
            return jsonify({
                "status": "warning", 
                "message": "No NBA games scheduled today (All-Star/Offseason)."
            })
            
        return jsonify({"status": "success", "message": "Odds Synced Successfully."})

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        return jsonify({"status": "error", "message": f"Odds Sync Error: {error_msg}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/sync/stats', methods=['POST'])
def sync_stats_only():
    """Step 2: Fetch deep history & Run Multi-Sims (Slow)."""
    if request.headers.get('X-User-Role') != 'admin':
        return jsonify({"status": "error"}), 403
    
    base_path = "/home/TheEdgeBoard/EdgeBoard/"
    if not os.path.exists(base_path): base_path = "" # Local fallback

    try:
        # 1. Performance Data (3/5/10/14 Games)
        subprocess.run(["python3", os.path.join(base_path, "sync_stats.py")], check=True)
        
        # 2. Matchup Context (Pace/Defense)
        subprocess.run(["python3", os.path.join(base_path, "sync_matchups.py")], check=True)
        
        # 3. Injury Reports
        subprocess.run(["python3", os.path.join(base_path, "sync_injuries.py")], check=True)
        
        # 4. Multi-Window Simulations (Calculates EV for all 4 windows)
        subprocess.run(["python3", os.path.join(base_path, "run_sims.py")], check=True)
        
        return jsonify({"status": "success", "message": "Multi-Window Stats & Sims Complete."})

    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": f"Stats Pipeline Error: {str(e)}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True)