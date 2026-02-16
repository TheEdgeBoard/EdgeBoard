from flask import Flask, jsonify, request, render_template_string
import sqlite3
import os
import subprocess
import random
import smtplib
import secrets
from email.mime.text import MIMEText
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
# Ensures HTTPS is recognized correctly behind PythonAnywhere's proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

# --- CONFIGURATION ---
# Replace with your Gmail and the 16-character Google App Password
EMAIL_ADDRESS = "edgeboardanalytics@gmail.com"
EMAIL_PASSWORD = "kxet mzih snlr cqcy" 
BASE_URL = "https://www.edgeboard.live"

def get_db_connection():
    path = '/home/TheEdgeBoard/EdgeBoard/edgeboard.db'
    if not os.path.exists(path):
        path = 'edgeboard.db'
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def send_external_email(target_email, subject, body):
    """General purpose SMTP mailer."""
    msg = MIMEText(body)
    msg['Subject'] = subject
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
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return open(os.path.join(base_dir, 'index.html'), encoding='utf-8').read()

# --- NEW SELF-REGISTRATION SYSTEM ---

@app.route('/api/register', methods=['POST'])
def register_request():
    """Public route for prospective users to request access."""
    data = request.json
    # Generate a secure unique token for the password setup link
    token = secrets.token_urlsafe(32)
    
    conn = get_db_connection()
    try:
        # Store in pending_users using the 'code' column for our token
        conn.execute('''INSERT OR REPLACE INTO pending_users 
                        (username, full_name, email, code) 
                        VALUES (?, ?, ?, ?)''',
                    (data['username'], data['full_name'], data['email'], token))
        conn.commit()
        
        # 1. Send e-mail to User to set password
        setup_link = f"{BASE_URL}?setup_token={token}"
        user_body = f"Hello {data['full_name']},\n\nWelcome to EdgeBoard. To complete your registration and establish your password, please click the link below:\n\n{setup_link}\n\nIf you did not request this, please ignore this email."
        send_external_email(data['email'], "Set Your EdgeBoard Password", user_body)

        # 2. Send notification to YOU (the Admin)
        admin_body = f"New EdgeBoard Sign-up Request:\n\nName: {data['full_name']}\nUsername: {data['username']}\nEmail: {data['email']}"
        send_external_email(EMAIL_ADDRESS, "ALERT: New User Registration", admin_body)

        return jsonify({"status": "success", "message": "Instructions sent to your email."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/complete-signup', methods=['POST'])
def complete_signup():
    """Finalizes account by setting password and moving from pending to active."""
    data = request.json
    token = data.get('token')
    new_password = data.get('password')

    conn = get_db_connection()
    pending = conn.execute('SELECT * FROM pending_users WHERE code = ?', (token,)).fetchone()
    
    if pending:
        try:
            # Move to permanent users table
            conn.execute('''INSERT INTO users (username, password, role, full_name, email) 
                            VALUES (?, ?, 'viewer', ?, ?)''',
                        (pending['username'], new_password, pending['full_name'], pending['email']))
            # Clean up pending table
            conn.execute('DELETE FROM pending_users WHERE code = ?', (token,))
            conn.commit()
            return jsonify({"status": "success", "message": "Password set! You can now log in."})
        except Exception as e:
            return jsonify({"status": "error", "message": "Username may already be taken."}), 400
        finally:
            conn.close()
    
    conn.close()
    return jsonify({"status": "error", "message": "Invalid or expired link."}), 400

# --- AUTH & DATA ROUTES ---

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

@app.route('/api/data')
def get_data():
    conn = get_db_connection()
    rows = conn.execute('''SELECT player_name, team, prop_type, line_value, projected_value, ev_edge, context_tags 
                           FROM sim_results WHERE ev_edge >= 0 ORDER BY ev_edge DESC''').fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@app.route('/api/sync', methods=['POST'])
def manual_sync():
    if request.headers.get('X-User-Role') != 'admin':
        return jsonify({"status": "error"}), 403
    try:
        subprocess.run(["python3", "/home/TheEdgeBoard/EdgeBoard/sync_matchups.py"], check=True)
        subprocess.run(["python3", "/home/TheEdgeBoard/EdgeBoard/sync_injuries.py"], check=True)
        subprocess.run(["python3", "/home/TheEdgeBoard/EdgeBoard/run_sims.py"], check=True)
        return jsonify({"status": "success", "message": "Contextual Sync Complete."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/get-users', methods=['GET'])
def get_users():
    if request.headers.get('X-User-Role') != 'admin':
        return jsonify({"status": "error"}), 403
    conn = get_db_connection()
    users = conn.execute('SELECT username, full_name, email FROM users WHERE role = "viewer"').fetchall()
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
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(debug=True)