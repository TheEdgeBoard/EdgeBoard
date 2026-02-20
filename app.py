from flask import Flask, jsonify, request, render_template, render_template_string, session
import sqlite3
import os
import sys
import subprocess

# --- CONFIGURATION ---
BASE_DIR = '/home/TheEdgeBoard/EdgeBoard/'
sys.path.append(BASE_DIR)

app = Flask(__name__)
app.secret_key = 'any_random_words_here'
DB_PATH = os.path.join(BASE_DIR, 'edgeboard.db')

# --- IMPORT YOUR SCRIPTS ---
# This connects the 'sync_odds.py' return values to this app
# --- IMPORT YOUR SCRIPTS ---
try:
    from sync_odds import sync_odds as run_sync_odds
    from sync_stats import sync_stats as run_sync_stats
    from sync_box_scores import sync_box_scores as run_sync_box_scores # <-- THE NEW BOX SCORE LINE
except ImportError:
    print("Warning: Sync scripts not found or have errors.")

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
        # --- NEW: Check if Admin is logged in ---
        is_admin = False
        if session.get('logged_in') and session.get('role') == 'admin':
            is_admin = True
            
        # Read the file manually since it is in the root folder
        html_content = open(os.path.join(BASE_DIR, 'index.html'), encoding='utf-8').read()
        
        # Use render_template_string to inject the 'is_admin' variable into the HTML
        return render_template_string(html_content, is_admin=is_admin)
        
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
        
        # Simple password check
        if user and user['password'] == data['password']:
            # --- NEW: Save user info to Session ---
            session['username'] = user['username']
            session['role'] = user['role']
            session['logged_in'] = True
            # --------------------------------------
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
    try:
        query = '''
            SELECT 
                a.*, 
                s.suggestion,
                s.win_rate_3, s.ev_3,
                s.win_rate_5, s.ev_5,
                s.win_rate_10, s.ev_10,
                s.win_rate_14, s.ev_14
            FROM active_lines a
            LEFT JOIN sim_results s 
                ON a.player_name = s.player_name 
                AND a.prop_type = s.prop_type
            WHERE a.line_value IS NOT NULL
        '''
        results = conn.execute(query).fetchall()
        data = [dict(row) for row in results]
    except Exception as e:
        print(f"DB Error: {e}")
        data = []
    finally:
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
def sync_stats_route(): # Renamed slightly to avoid conflicts
    try:
        # Call the function directly just like odds!
        run_sync_stats() 
        return jsonify({"status": "success", "message": "Stats synced successfully!"}) 
    except Exception as e: 
        # Now if it crashes, it will tell us exactly WHY on your screen!
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/sync/box_scores', methods=['POST'])
def sync_box_scores_route():
    try:
        result = run_sync_box_scores() 
        return jsonify(result)
    except Exception as e: 
        return jsonify({"status": "error", "message": str(e)})   
# ==========================================
# ADMIN USER MANAGEMENT SECTION
# ==========================================

@app.route('/admin/users')
def manage_users():
    # We use DB_PATH here so it finds your REAL database file
    conn = sqlite3.connect(DB_PATH) 
    cursor = conn.cursor()
    
    try:
        # Match the columns exactly to your database screenshot
        # rowid is used as a safe 'id' column
        query = "SELECT rowid, full_name, email, username, access_level, password_hash FROM users"
        cursor.execute(query)
        users = cursor.fetchall()
    except Exception as e:
        print(f"Error fetching users: {e}")
        users = []
    finally:
        conn.close()

    return render_template('admin_users.html', users=users)


@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    # Use DB_PATH to ensure we are deleting from the correct file
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # We use rowid here to match the ID displayed in your table
        cursor.execute("DELETE FROM users WHERE rowid = ?", (user_id,))
        conn.commit()
        print(f"Deleted user ID: {user_id}")
    except Exception as e:
        print(f"Error deleting user: {e}")
    finally:
        conn.close()

    return redirect(url_for('manage_users'))
@app.route('/admin/db')
def view_database():
    # SECURITY: Only let Admins see the raw database
    if not session.get('logged_in') or session.get('role') != 'admin':
        return "Unauthorized. Please log in as an Admin.", 403

    conn = get_db_connection()
    try:
        # Removed the LIMIT keyword so it pulls the entire table
        active_lines = conn.execute("SELECT * FROM active_lines ORDER BY player_name").fetchall()
        player_logs = conn.execute("SELECT * FROM player_logs ORDER BY id DESC").fetchall()
    except Exception as e:
        return f"Database Error: {e}"
    finally:
        conn.close()

    # Build a simple, dark-mode HTML table to display the data
    html = """
    <body style="background:#0f172a;color:white;padding:20px;font-family:sans-serif;">
        <div style="max-width: 1200px; margin: auto;">
            <h1 style="color:#10b981;">Database Viewer (Live)</h1>
            <a href="/" style="color:#3b82f6; text-decoration: none; font-weight: bold;">&larr; Back to Dashboard</a>
            
            <h2 style="margin-top: 30px; color: #94a3b8;">active_lines (Top 100)</h2>
            <div style="overflow-x:auto; border: 1px solid #334155; border-radius: 8px;">
                <table style="width: 100%; text-align: left; border-collapse: collapse; font-size: 14px;">
                    <tr style="background: #1e293b; border-bottom: 1px solid #334155;">
                        <th style="padding: 10px;">Player</th>
                        <th style="padding: 10px;">Prop</th>
                        <th style="padding: 10px;">Line</th>
                        <th style="padding: 10px;">Best Odds</th>
                        <th style="padding: 10px;">Trend History</th>
                    </tr>
                    {% for row in active_lines %}
                    <tr style="border-bottom: 1px solid #334155;">
                        <td style="padding: 10px;">{{ row['player_name'] }}</td>
                        <td style="padding: 10px;">{{ row['prop_type'] }}</td>
                        <td style="padding: 10px;">{{ row['line_value'] }}</td>
                        <td style="padding: 10px;">{{ row['odds_over'] }}</td>
                        <td style="padding: 10px;">{{ row['trend_history'] }}</td>
                    </tr>
                    {% endfor %}
                </table>
            </div>

            <h2 style="margin-top: 40px; color: #94a3b8;">player_logs (Recent 100)</h2>
            <div style="overflow-x:auto; border: 1px solid #334155; border-radius: 8px;">
                <table style="width: 100%; text-align: left; border-collapse: collapse; font-size: 14px;">
                    <tr style="background: #1e293b; border-bottom: 1px solid #334155;">
                        <th style="padding: 10px;">ID</th>
                        <th style="padding: 10px;">Player</th>
                        <th style="padding: 10px;">Date</th>
                        <th style="padding: 10px;">PTS</th>
                        <th style="padding: 10px;">REB</th>
                        <th style="padding: 10px;">AST</th>
                        <th style="padding: 10px;">3PM</th>
                    </tr>
                    {% for row in player_logs %}
                    <tr style="border-bottom: 1px solid #334155;">
                        <td style="padding: 10px; color: #64748b;">{{ row['id'] }}</td>
                        <td style="padding: 10px; font-weight: bold;">{{ row['player_name'] }}</td>
                        <td style="padding: 10px;">{{ row['game_date'] }}</td>
                        <td style="padding: 10px;">{{ row['pts'] }}</td>
                        <td style="padding: 10px;">{{ row['reb'] }}</td>
                        <td style="padding: 10px;">{{ row['ast'] }}</td>
                        <td style="padding: 10px;">{{ row['threes_made'] }}</td>
                    </tr>
                    {% endfor %}
                </table>
            </div>
        </div>
    </body>
    """
    return render_template_string(html, active_lines=active_lines, player_logs=player_logs)
if __name__ == '__main__':
    app.run(debug=True)