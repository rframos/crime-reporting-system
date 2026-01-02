import os
import datetime
import shutil
import traceback
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, abort, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image

# --- CONFIGURATION ---
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
app = Flask(__name__, root_path=base_dir, template_folder='templates', static_folder='static')

app.config['SECRET_KEY'] = 'sjdm_safe_city_2026_full_fix'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'local.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, 'static/uploads')
app.config['TRAIN_FOLDER'] = os.path.join(base_dir, 'static/training_data')

# Create necessary folders
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
    role = db.Column(db.String(20)) # Resident, Police Officer, Admin, Barangay Official

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    severity = db.Column(db.String(20))

class Incident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    incident_type = db.Column(db.String(50))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    status = db.Column(db.String(20), default='Pending')
    severity = db.Column(db.String(20))
    image_url = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except Exception:
        return None

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

@app.route('/reset-db')
def reset_db():
    try:
        # This force-creates all tables
        db.drop_all()
        db.create_all()
        
        # Setup Folders
        if os.path.exists(app.config['TRAIN_FOLDER']):
            shutil.rmtree(app.config['TRAIN_FOLDER'])
        os.makedirs(app.config['TRAIN_FOLDER'], exist_ok=True)
        
        # Default Categories
        default_cats = [
            Category(name="Theft", severity="Medium"),
            Category(name="Assault", severity="High"),
            Category(name="Vandalism", severity="Low")
        ]
        db.session.add_all(default_cats)
        db.session.commit()
        
        for cat in default_cats:
            os.makedirs(os.path.join(app.config['TRAIN_FOLDER'], cat.name), exist_ok=True)
            
        flash("Database Reset Successfully! Tables Created.", "success")
        return redirect(url_for('register_page'))
    except Exception as e:
        return f"Reset Error: {str(e)}"

@app.route('/')
@login_required
def index():
    return render_template('index.html', categories=Category.query.all())

@app.route('/cnn-admin')
@roles_required('Admin')
def cnn_admin():
    categories = Category.query.all()
    dataset = {}
    for cat in categories:
        path = os.path.join(app.config['TRAIN_FOLDER'], cat.name)
        dataset[cat.name] = os.listdir(path) if os.path.exists(path) else []
    return render_template('cnn_admin.html', categories=categories, dataset=dataset)

@app.route('/login')
def login_page(): return render_template('login.html')

@app.route('/register')
def register_page(): return render_template('register.html')

@app.route('/api/register', methods=['POST'])
def register():
    u = request.form.get('username')
    p = request.form.get('password')
    r = request.form.get('role')
    if User.query.filter_by(username=u).first():
        flash("User already exists.", "danger")
        return redirect(url_for('register_page'))
    db.session.add(User(username=u, password=generate_password_hash(p), role=r))
    db.session.commit()
    flash("Account created! Please login.", "success")
    return redirect(url_for('login_page'))

@app.route('/api/login', methods=['POST'])
def login():
    user = User.query.filter_by(username=request.form.get('username')).first()
    if user and check_password_hash(user.password, request.form.get('password')):
        login_user(user)
        return redirect(url_for('index'))
    flash("Invalid credentials.", "danger")
    return redirect(url_for('login_page'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login_page'))

# --- DATABASE INITIALIZATION ON STARTUP ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
