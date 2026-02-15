from flask import Flask, jsonify, request
import sqlite3
import os
import subprocess
import random
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# --- EMAIL SETTINGS (Update these!) ---
EMAIL_ADDRESS = "your-email@gmail.com"
EMAIL_PASSWORD = "your-app-password" # Not your login password!

def send_code(target_email, code):
    msg = MIMEText(f"Your EdgeBoard activation code is: {code}")
    msg['Subject'] = 'EdgeBoard Access Code'
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = target_email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

def get_db_connection():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'edgeboard.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return open(os.path.join(base_dir, 'index.html'), encoding='utf-8').read()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                        (data['username'], data['password'])).fetchone()
    conn.close()
    if user:
        return jsonify({"status": "success", "role": user['role'], "username": user['username']})
    return jsonify({"status": "error"}), 401

@app.route('/api/create-user', methods=['POST'])
def create_user():
    if request.headers.get('X-User-Role') != 'admin':
        return jsonify({"status": "error"}), 403

    data = request.json
    code = str(random.randint(100000, 999999)) # 6-digit code

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
        return jsonify({"status": "pending", "message": "Code sent to client's email."})
    except Exception as e:
        return jsonify({"status": "error", "message": "Email failed to send."})

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
    
    return jsonify({"status": "error", "message": "Wrong Code"}), 400

@app.route('/api/data')
def get_data():
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM sim_results').fetchall() # Simplified for example
    conn.close()
    return jsonify([dict(row) for row in rows])

if __name__ == '__main__':
    app.run(debug=True)