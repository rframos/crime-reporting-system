import os
import datetime
import numpy as np
import cv2
import tensorflow as tf
import shutil
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# --- INITIAL SETUP ---
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
app = Flask(__name__, root_path=base_dir, template_folder='templates', static_folder='static')

app.config['SECRET_KEY'] = 'safecity_sjdm_2026_final_v2'
app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, 'static/uploads')
app.config['TRAIN_FOLDER'] = os.path.join(base_dir, 'static/training_data')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///local.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['TRAIN_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login_page'

# --- MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='Resident') # Admin, Police, Barangay, Resident

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

# --- ACCESS CONTROL ---
def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role not in roles: return abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- THE RESET ROUTE (FIXED) ---
@app.route('/reset-db')
def reset_db():
    """Drops all tables and recreates the system from scratch."""
    with app.app_context():
        db.drop_all()
        db.create_all()
        
        # Re-add default categories
        cats = [
            Category(name="Theft", severity="Medium"),
            Category(name="Vandalism", severity="Low"),
            Category(name="Assault", severity="High")
        ]
        db.session.add_all(cats)
        db.session.commit()
        
        # Ensure training folders exist for these cats
        for c in cats:
            os.makedirs(os.path.join(app.config['TRAIN_FOLDER'], c.name), exist_ok=True)
            
    return "Database Reset Successful! All data cleared. Default categories (Theft, Vandalism, Assault) restored. <a href='/register'>Register Admin</a>"

# --- CATEGORY & IMAGE MGMT ---
@app.route('/api/categories/delete/<int:id>', methods=['POST'])
@roles_required('Admin')
def delete_category(id):
    cat = Category.query.get(id)
    if cat:
        # Remove training folder
        shutil.rmtree(os.path.join(app.config['TRAIN_FOLDER'], cat.name), ignore_errors=True)
        db.session.delete(cat)
        db.session.commit()
    return redirect(url_for('cnn_admin'))

# --- AUTH & PAGE ROUTES ---
@app.route('/')
@login_required
def index(): return render_template('index.html', categories=Category.query.all())

@app.route('/cnn-admin')
@roles_required('Admin')
def cnn_admin():
    categories = Category.query.all()
    dataset = {cat.name: os.listdir(os.path.join(app.config['TRAIN_FOLDER'], cat.name)) 
               if os.path.exists(os.path.join(app.config['TRAIN_FOLDER'], cat.name)) else [] 
               for cat in categories}
    return render_template('cnn_admin.html', categories=categories, dataset=dataset)

@app.route('/login')
def login_page(): return render_template('login.html')

@app.route('/register')
def register_page(): return render_template('register.html')

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

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login_page'))

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True)
