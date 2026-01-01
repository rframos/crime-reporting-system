import os
import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
app = Flask(__name__, root_path=base_dir, template_folder='templates', static_folder='static')

app.config['SECRET_KEY'] = 'sjdm_safe_city_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'local.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login_page'

# --- MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='Resident') 

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    severity = db.Column(db.String(20), default='Low')

class Incident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    incident_type = db.Column(db.String(50))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    status = db.Column(db.String(20), default='Pending')
    severity = db.Column(db.String(20), default='Low') # Added for better filtering
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))

# --- ROUTES ---
@app.route('/')
@login_required
def index():
    return render_template('index.html', categories=Category.query.all())

@app.route('/heatmap')
@login_required
def heatmap_page():
    # Pass categories to the heatmap for the filter dropdown
    return render_template('heatmap.html', categories=Category.query.all())

@app.route('/api/incidents')
@login_required
def get_incidents():
    # Supports ?type=Theft or ?severity=High
    inc_type = request.args.get('type')
    severity = request.args.get('severity')
    
    query = Incident.query
    if inc_type and inc_type != 'All':
        query = query.filter_by(incident_type=inc_type)
    if severity and severity != 'All':
        query = query.filter_by(severity=severity)
        
    incidents = query.all()
    return jsonify([{"lat": i.latitude, "lng": i.longitude, "type": i.incident_type, "severity": i.severity} for i in incidents])

# (Login/Register/Logout routes remain the same)
@app.route('/login')
def login_page(): return render_template('login.html')

@app.route('/register')
def register_page(): return render_template('register.html')

@app.route('/api/register', methods=['POST'])
def register():
    uname = request.form.get('username'); passw = request.form.get('password'); role = request.form.get('role')
    if User.query.filter_by(username=uname).first(): return "User exists", 400
    db.session.add(User(username=uname, password=generate_password_hash(passw), role=role))
    db.session.commit()
    return jsonify({"status": "success"})

@app.route('/api/login', methods=['POST'])
def login():
    user = User.query.filter_by(username=request.form.get('username')).first()
    if user and check_password_hash(user.password, request.form.get('password')):
        login_user(user); return jsonify({"status": "success"})
    return "Error", 401

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login_page'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
