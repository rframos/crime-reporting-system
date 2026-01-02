import os
import datetime
import shutil
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, abort, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# --- CONFIGURATION ---
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
app = Flask(__name__, root_path=base_dir, template_folder='templates', static_folder='static')

app.config['SECRET_KEY'] = 'sjdm_safe_city_2026_full_fix'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'local.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, 'static/uploads')
app.config['TRAIN_FOLDER'] = os.path.join(base_dir, 'static/training_data')

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
    role = db.Column(db.String(20)) # Resident, Police Officer, Admin

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
def load_user(user_id): return User.query.get(int(user_id))

def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role not in roles: return abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- THE RESET ROUTE ---
@app.route('/reset-db')
def reset_db():
    db.drop_all()
    db.create_all()
    
    # Setup folders
    if os.path.exists(app.config['TRAIN_FOLDER']):
        shutil.rmtree(app.config['TRAIN_FOLDER'])
    os.makedirs(app.config['TRAIN_FOLDER'], exist_ok=True)
    
    # Add Default Categories
    default_cats = [
        Category(name="Theft", severity="Medium"),
        Category(name="Assault", severity="High"),
        Category(name="Vandalism", severity="Low")
    ]
    db.session.add_all(default_cats)
    db.session.commit()
    
    for cat in default_cats:
        os.makedirs(os.path.join(app.config['TRAIN_FOLDER'], cat.name), exist_ok=True)
        
    flash("System successfully reset! Folders recreated and default categories added.", "success")
    return redirect(url_for('register_page'))

# --- CORE PAGE ROUTES ---
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

@app.route('/heatmap')
@login_required
def heatmap():
    return render_template('heatmap.html', categories=Category.query.all())

@app.route('/reports')
@login_required
def reports():
    incidents = Incident.query.order_by(Incident.created_at.desc()).all()
    return render_template('reports.html', incidents=incidents)

@app.route('/contacts')
@login_required
def contacts():
    return render_template('contacts.html')

# --- API ROUTES (POSTS) ---
@app.route('/api/add-category', methods=['POST'])
@roles_required('Admin')
def add_category():
    name = request.form.get('name').strip()
    sev = request.form.get('severity')
    if name and not Category.query.filter_by(name=name).first():
        db.session.add(Category(name=name, severity=sev))
        db.session.commit()
        os.makedirs(os.path.join(app.config['TRAIN_FOLDER'], name), exist_ok=True)
        flash(f"Category '{name}' added successfully.", "success")
    else:
        flash("Invalid name or category already exists.", "danger")
    return redirect(url_for('cnn_admin'))

@app.route('/api/upload-training', methods=['POST'])
@roles_required('Admin')
def upload_training():
    cat_name = request.form.get('category')
    files = request.files.getlist('images')
    cat_path = os.path.join(app.config['TRAIN_FOLDER'], cat_name)
    
    if not os.path.exists(cat_path):
        os.makedirs(cat_path, exist_ok=True)
        
    for f in files:
        if f:
            f.save(os.path.join(cat_path, secure_filename(f.filename)))
    
    flash(f"Images uploaded to {cat_name}.", "success")
    return redirect(url_for('cnn_admin'))

@app.route('/api/register', methods=['POST'])
def register():
    u, p, r = request.form.get('username'), request.form.get('password'), request.form.get('role')
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

@app.route('/login')
def login_page(): return render_template('login.html')

@app.route('/register')
def register_page(): return render_template('register.html')

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login_page'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
