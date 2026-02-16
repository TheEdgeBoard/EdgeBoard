from flask import Flask, jsonify, request
import sqlite3
import os
import subprocess
import random
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Load environment variables (like API Keys)
load_dotenv()

app = Flask(__name__)

# --- CONFIGURATION (UPDATE THESE!) ---
# Use a Google "App Password", not your regular Gmail password.
EMAIL_ADDRESS = "your-email@gmail.com"
EMAIL_PASSWORD = "your-app-password" 

# --- DATABASE HELPER ---
def get_db_connection():
    """Maintains connection to the database based on your specific folder structure."""
    path = '/home/TheEdgeBoard/EdgeBoard/edgeboard.db'
    # Fallback for local testing
    if not os.path.exists(path):
        path = 'edgeboard.db'
    
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

# --- EMAIL ENGINE ---
def send_code(target_email, code):
    """Sends a 6-digit verification code via Gmail SMTP."""
    msg = MIMEText(f"Your EdgeBoard activation code is: {code}\n\nThis code will finalize your account creation.")
    msg['Subject'] = 'EdgeBoard Access Code'
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = target_email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

# --- WEB ROUTES ---
@app.route('/')
def home():
    """Serves the dashboard HTML file."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return open(os.path.join(base_dir, 'index.html'), encoding='utf-8').read()

# --- AUTHENTICATION API ---
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
            "username": user['username'],
            "full_name": user.get('full_name')
        })
    return jsonify({"status": "error", "message": "Invalid Credentials"}), 401

# --- CRM: ONBOARDING (PENDING STATE) ---
@app.route('/api/create-user', methods=['POST'])
def create_user():
    if request.headers.get('X-User-Role') != 'admin':
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

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
        return jsonify({"status": "pending", "message": "Verification code sent to email."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Email Error: {str(e)}"})

# --- CRM: VERIFICATION (FINAL ACTIVATION) ---
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
    
    return jsonify({"status": "error", "message": "Invalid Verification Code"}), 400

# --- CRM: USER DIRECTORY MANAGEMENT ---
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
    return jsonify({"status": "success", "message": f"Access revoked for {username}"})

# --- DATA ENGINE API ---
@app.route('/api/data')
def get_data():
    conn = get_db_connection()
    # Simplified query - ensure your sim_results table exists
    rows = conn.execute('SELECT * FROM sim_results ORDER BY ev_edge DESC').fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

# --- SYSTEM SYNC (ADMIN ONLY) ---
@app.route('/api/sync', methods=['POST'])
def manual_sync():
    if request.headers.get('X-User-Role') != 'admin':
        return jsonify({"status": "error"}), 403

    try:
        # Note: Ensure these paths match your EdgeBoard folder structure
        subprocess.run(["python", "/home/TheEdgeBoard/EdgeBoard/sync_odds.py"], check=True)
        subprocess.run(["python", "/home/TheEdgeBoard/EdgeBoard/sync_stats.py"], check=True)
        subprocess.run(["python", "/home/TheEdgeBoard/EdgeBoard/run_sims.py"], check=True)
        return jsonify({"status": "success", "message": "Global Market Refresh Complete."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True)