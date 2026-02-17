from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
import os
import subprocess
import random
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# --- CONFIGURATION ---
BASE_DIR = '/home/TheEdgeBoard/EdgeBoard/'
DB_PATH = os.path.join(BASE_DIR, 'edgeboard.db')

# Required for Flask-Admin sessions and SQLAlchemy
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-123')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- DATABASE MODELS (For Flask-Admin & SQLAlchemy) ---

class User(db.Model):
    __tablename__ = 'users'
    username = db.Column(db.String(80), primary_key=True)
    password = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(20), default='viewer')
    full_name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))

class DailyProspect(db.Model):
    __tablename__ = 'daily_prospects'
    # Adding a hidden ID for SQLAlchemy compatibility
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    player_id = db.Column(db.Integer)
    player_name = db.Column(db.String(100))
    team_id = db.Column(db.String(20))
    opponent_id = db.Column(db.String(20))
    prop_type = db.Column(db.String(20))
    market_line = db.Column(db.Float)
    
    # Trend Data (Will store "24,19,30,22,25" for Chart.js)
    trend_history = db.Column(db.String(200), default="") 

class SimResult(db.Model):
    __tablename__ = 'sim_results'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    player_name = db.Column(db.String(100))
    suggestion = db.Column(db.String(20))
    win_rate_10 = db.Column(db.Float)
    ev_10 = db.Column(db.Float)
    # Adding all windows for the API
    ev_3 = db.Column(db.Float)
    ev_5 = db.Column(db.Float)
    ev_14 = db.Column(db.Float)

# --- FLASK-ADMIN SETUP ---
# This builds the visual CMS at /admin
admin = Admin(app, name='EdgeBoard CMS', template_mode='bootstrap3')

# We customize the view to hide passwords in the list
class UserAdminView(ModelView):
    column_exclude_list = ['password']
    column_searchable_list = ['username', 'email']

admin.add_view(UserAdminView(User, db.session))
admin.add_view(ModelView(DailyProspect, db.session))

# --- WEB & API ROUTES ---

@app.route('/')
def home():
    return open(os.path.join(BASE_DIR, 'index.html'), encoding='utf-8').read()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(username=data['username'], password=data['password']).first()
    if user:
        return jsonify({"status": "success", "role": user.role, "username": user.username})
    return jsonify({"status": "error", "message": "Invalid Credentials"}), 401

@app.route('/api/data')
def get_data():
    # Joins Sim Results with Prospect Data to get the Trend History
    results = db.session.execute('''
        SELECT s.*, p.trend_history 
        FROM sim_results s
        JOIN daily_prospects p ON s.player_name = p.player_name 
        AND s.prop_type = p.prop_type
    ''').fetchall()
    
    return jsonify([dict(row) for row in results])

# --- SYSTEM SYNC ROUTES ---

@app.route('/api/sync/odds', methods=['POST'])
def sync_odds_only():
    if request.headers.get('X-User-Role') != 'admin': return jsonify({"status": "error"}), 403
    try:
        subprocess.run(["python3", os.path.join(BASE_DIR, "sync_odds.py")], check=True)
        return jsonify({"status": "success", "message": "Odds Synced."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/sync/stats', methods=['POST'])
def sync_stats_only():
    if request.headers.get('X-User-Role') != 'admin': return jsonify({"status": "error"}), 403
    try:
        subprocess.run(["python3", os.path.join(BASE_DIR, "sync_stats.py")], check=True)
        subprocess.run(["python3", os.path.join(BASE_DIR, "run_sims.py")], check=True)
        return jsonify({"status": "success", "message": "Stats & Sims Complete."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True)