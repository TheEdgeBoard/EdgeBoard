from flask import Flask, jsonify, request, render_template_string
import sqlite3
import os
import sys
import subprocess

# --- CONFIGURATION ---
BASE_DIR = '/home/TheEdgeBoard/EdgeBoard/'
sys.path.append(BASE_DIR)  # <--- CRITICAL: Allows importing your local scripts

app = Flask(__name__)
DB_PATH = os.path.join(BASE_DIR, 'edgeboard.db')

# --- IMPORT YOUR SCRIPTS ---
# This connects the 'sync_odds.py' return values to this app
try:
    from sync_odds import sync_odds as run_sync_odds
except ImportError:
    print("Warning: sync_odds.py not found or has errors.")

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

# --- API ROUTES ---
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    try:
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (data['username'],)).fetchone()
        conn.close()
        
        # Simple password check (In production, use hashing!)
        if user and user['password'] == data['password']:
            return jsonify({"status": "success", "role": user['role'], "username": user['username']})
        return jsonify({"status": "error", "message": "Invalid Credentials"}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    try:
        conn = get_db_connection()
        # Create table if not exists (Lazy init)
        conn.execute('''CREATE TABLE IF NOT EXISTS users 
                        (username TEXT PRIMARY KEY, password TEXT, full_name TEXT, email TEXT, role TEXT)''')
        
        # Check if user exists
        exists = conn.execute('SELECT 1 FROM users WHERE username = ?', (data['requested_username'],)).fetchone()
        if exists:
            conn.close()
            return jsonify({"status": "error", "message": "Username already taken"})

        conn.execute('INSERT INTO users (username, password, full_name, email, role) VALUES (?, ?, ?, ?, ?)',
                     (data['requested_username'], data['password'], data['full_name'], data['email'], 'user'))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Account created! You can now log in."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/data')
def get_data():
    sport = request.args.get('sport', 'NBA')
    if sport != 'NBA': return jsonify([]) 

    conn = get_db_connection()
    # Simplified Query to prevent crashes if columns are missing
    query = '''
        SELECT * FROM daily_prospects
    '''
    try:
        results = conn.execute(query).fetchall()
        # Convert to list of dicts
        data = [dict(row) for row in results]
    except Exception as e:
        print(f"DB Error: {e}")
        data = []
    conn.close()
    return jsonify(data)

# --- ADMIN & SYNC ROUTES (FIXED) ---

@app.route('/api/sync/odds', methods=['POST'])
def sync_odds_route():
    try:
        # CALL THE FUNCTION DIRECTLY
        # This gets the {"status":..., "message":...} from sync_odds.py
        result = run_sync_odds() 
        return jsonify(result)
    except Exception as e: 
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/sync/stats', methods=['POST'])
def sync_stats():
    try:
        # We still use subprocess here since we haven't updated sync_stats.py yet
        subprocess.run(["/usr/bin/python3", os.path.join(BASE_DIR, "sync_stats.py")], check=True)
        
        # Manually add the message so the frontend doesn't say "undefined"
        return jsonify({"status": "success", "message": "Stats synced successfully!"}) 
    except Exception as e: 
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True)