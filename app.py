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
EMAIL_PASS = "mzac cwka rtek biwj" # 16-character Google App Password
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
def send_email(subject, recipient, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = ADMIN_EMAIL
    msg['To'] = recipient
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(ADMIN_EMAIL, EMAIL_PASS)
            smtp.send_message(msg)
    except Exception as e:
        print(f"Email error: {e}")
@app.route('/setup-password')
def setup_password_page():
    username = request.args.get('user')
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head><title>Setup Password</title><script src="https://cdn.tailwindcss.com"></script></head>
        <body class="bg-gray-950 text-white flex items-center justify-center min-h-screen">
            <div class="bg-gray-900 border border-gray-800 p-8 rounded-2xl w-full max-w-sm">
                <h1 class="text-emerald-400 font-bold mb-4">Set Password for {{user}}</h1>
                <input id="pw" type="password" placeholder="New Password" class="w-full bg-gray-800 p-3 rounded mb-4">
                <button onclick="activate()" class="w-full bg-emerald-500 text-black font-bold py-3 rounded">ACTIVATE</button>
            </div>
            <script>
                async function activate() {
                    const res = await fetch('/api/activate-account', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({username: '{{user}}', password: document.getElementById('pw').value})
                    });
                    const data = await res.json();
                    alert(data.message);
                    if(data.status === 'success') window.location.href = '/';
                }
            </script>
        </body></html>
    ''', user=username)

@app.route('/api/activate-account', methods=['POST'])
def activate_account():
    data = request.json
    conn = get_db_connection()
    conn.execute('UPDATE users SET password = ?, status = "active" WHERE username = ?',
                 (data['password'], data['username']))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Account activated!"})
@app.route('/')
def home():
    try:
        return open(os.path.join(BASE_DIR, 'index.html'), encoding='utf-8').read()
    except Exception as e:
        return f"Error: index.html not found. {str(e)}"

# --- AUTH & USER MANAGEMENT ---

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

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    conn = get_db_connection()
    try:
        # NOTICE: We use data['requested_username'] to match the JS payload
        conn.execute('''
            INSERT INTO users (username, password, role, full_name, email, status) 
            VALUES (?, ?, ?, ?, ?, ?)''',
            (data['requested_username'], 'PENDING_SETUP', 'viewer', 
             data['full_name'], data['email'], 'pending'))
        conn.commit()
        return jsonify({"status": "success"})
    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "Username already exists"}), 400
    finally:
        conn.close()

@app.route('/api/admin/users', methods=['GET'])
def get_all_users():
    # Only returns data if the request comes from an admin
    role = request.args.get('role')
    if role != 'admin':
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    
    conn = get_db_connection()
    users = conn.execute('SELECT username, password, role FROM users').fetchall()
    conn.close()
    return jsonify([dict(row) for row in users])

@app.route('/api/admin/delete-user', methods=['POST'])
def delete_user():
    data = request.json
    conn = get_db_connection()
    conn.execute('DELETE FROM users WHERE username = ?', (data['username'],))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

# --- DATA & SYNC ---

@app.route('/api/data')
def get_data():
    conn = get_db_connection()
    query = '''
        SELECT s.*, p.market_line, p.trend_history 
        FROM sim_results s 
        JOIN daily_prospects p ON s.player_name = p.player_name 
        AND s.prop_type = p.prop_type
    '''
    results = conn.execute(query).fetchall()
    conn.close()
    return jsonify([dict(row) for row in results])

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