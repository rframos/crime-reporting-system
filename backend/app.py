import os
import datetime
import numpy as np
import cv2
import tensorflow as tf
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# --- CONFIG ---
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
app = Flask(__name__, root_path=base_dir, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'safecity_sjdm_2026_full'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///local.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, 'static/uploads')

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
    confidence = db.Column(db.Float, default=0.0) 
    image_url = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))

# --- RBAC ---
def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role not in roles: return abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- ROUTES ---
@app.route('/')
@login_required
def index():
    return render_template('index.html', categories=Category.query.all())

@app.route('/heatmap')
@roles_required('Admin', 'Police', 'Barangay')
def heatmap_page():
    return render_template('heatmap.html', categories=Category.query.all())

@app.route('/reports')
@roles_required('Admin', 'Police', 'Barangay')
def reports():
    incidents = Incident.query.order_by(Incident.created_at.desc()).all()
    return render_template('reports.html', incidents=incidents)

# --- SYSTEM FEATURES ---
@app.route('/reset-db')
def reset_db():
    db.drop_all(); db.create_all()
    db.session.add_all([Category(name="Theft", severity="Medium"), Category(name="Vandalism", severity="Low")])
    db.session.commit()
    return "Database Reset Successful."

@app.route('/api/report', methods=['POST'])
@login_required
def create_report():
    img = request.files.get('image')
    lat, lng = request.form.get('lat'), request.form.get('lng')
    final_type = request.form.get('type')
    
    f_name = None
    if img:
        f_name = secure_filename(f"{datetime.datetime.now().timestamp()}_{img.filename}")
        img.save(os.path.join(app.config['UPLOAD_FOLDER'], f_name))

    new_inc = Incident(incident_type=final_type, latitude=float(lat), longitude=float(lng), image_url=f_name, confidence=95.0)
    
    # Create Notification for Officials
    new_notif = Notification(message=f"New {final_type} reported at {lat}, {lng}!")
    
    db.session.add(new_inc)
    db.session.add(new_notif)
    db.session.commit()
    return jsonify({"status": "success"})

@app.route('/api/notifications')
@roles_required('Admin', 'Police', 'Barangay')
def get_notifications():
    notifs = Notification.query.order_by(Notification.created_at.desc()).limit(5).all()
    return jsonify([{"id": n.id, "message": n.message, "time": n.created_at.strftime('%H:%M')} for n in notifs])

# --- AUTH ---
@app.route('/api/register', methods=['POST'])
def register():
    uname = request.form.get('username')
    new_user = User(username=uname, password=generate_password_hash(request.form.get('password')), role=request.form.get('role'))
    db.session.add(new_user); db.session.commit()
    return jsonify({"status": "success"})

@app.route('/api/login', methods=['POST'])
def login():
    user = User.query.filter_by(username=request.form.get('username')).first()
    if user and check_password_hash(user.password, request.form.get('password')):
        login_user(user); return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 401

@app.route('/login')
def login_page(): return render_template('login.html')

@app.route('/register')
def register_page(): return render_template('register.html')

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login_page'))

@app.route('/api/incidents')
@login_required
def get_incidents_api():
    inc = Incident.query.all()
    return jsonify([{"lat": i.latitude, "lng": i.longitude, "type": i.incident_type} for i in inc])

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True)
