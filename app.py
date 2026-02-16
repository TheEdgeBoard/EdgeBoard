from flask import Flask, jsonify, request
import sqlite3
import os
import subprocess
import random
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Load environment variables for security (Optional but recommended)
load_dotenv()

app = Flask(__name__)

# --- CONFIGURATION ---
# Replace with your Gmail and the 16-character Google App Password
EMAIL_ADDRESS = "edgeboardanalytics@gmail.com"
EMAIL_PASSWORD = "gqkj rmid vwci tezp" 

def get_db_connection():
    """Connects to the SQLite database on PythonAnywhere."""
    path = '/home/TheEdgeBoard/EdgeBoard/edgeboard.db'
    if not os.path.exists(path):
        path = 'edgeboard.db'
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def send_code(target_email, code):
    """Sends 6-digit verification codes via Gmail SMTP."""
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

# --- PRIMARY WEB ROUTES ---
@app.route('/')
def home():
    """Serves the main dashboard (index.html)."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return open(os.path.join(base_dir, 'index.html'), encoding='utf-8').read()

# --- AUTHENTICATION ENGINE ---
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

# --- CRM & CLIENT MANAGEMENT ---
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

# --- DATA ANALYTICS (Monte Carlo Output) ---
@app.route('/api/data')
def get_data():
    conn = get_db_connection()
    # Grabs sorted positive edges with our new context tags (🔥, 🏎️, etc.)
    rows = conn.execute('''
        SELECT player_name, team, prop_type, line_value, projected_value, ev_edge, context_tags 
        FROM sim_results 
        WHERE ev_edge >= 0 
        ORDER BY ev_edge DESC
    ''').fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

# --- CONTEXTUAL SYNC CHAIN ---
@app.route('/api/sync', methods=['POST'])
def manual_sync():
    """
    Orchestrates the Contextual Monte Carlo Chain:
    1. Matchup Data (Defense/Pace)
    2. Injury Data (Usage Adjustments)
    3. Simulation Execution (10k Iterations)
    """
    if request.headers.get('X-User-Role') != 'admin':
        return jsonify({"status": "error"}), 403
    try:
        # Step 1: Opponent Defense & Pace
        subprocess.run(["python3", "/home/TheEdgeBoard/EdgeBoard/sync_matchups.py"], check=True)
        
        # Step 2: Injury Report Check
        subprocess.run(["python3", "/home/TheEdgeBoard/EdgeBoard/sync_injuries.py"], check=True)
        
        # Step 3: Weighted Monte Carlo Sims
        subprocess.run(["python3", "/home/TheEdgeBoard/EdgeBoard/run_sims.py"], check=True)
        
        return jsonify({"status": "success", "message": "Intelligence Chain Complete. View the dashboard for new Edges."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True)