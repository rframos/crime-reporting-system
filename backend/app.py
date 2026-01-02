import os
import datetime
import shutil
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
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'sjdm_safe_city_2026_secure')

# --- WEB DATABASE CONNECTION LOGIC ---
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///' + os.path.join(base_dir, 'local.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Image Paths
app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, 'static/uploads')
app.config['TRAIN_FOLDER'] = os.path.join(base_dir, 'static/training_data')
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
    role = db.Column(db.String(20)) 

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
    except:
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

# --- DATABASE MANAGEMENT ---
@app.route('/reset-db')
def reset_db():
    try:
        db.drop_all()
        db.create_all()
        if os.path.exists(app.config['TRAIN_FOLDER']):
            shutil.rmtree(app.config['TRAIN_FOLDER'])
        os.makedirs(app.config['TRAIN_FOLDER'], exist_ok=True)
        
        default_cats = [
            Category(name="Theft", severity="Medium"),
            Category(name="Assault", severity="High"),
            Category(name="Vandalism", severity="Low")
        ]
        db.session.add_all(default_cats)
        db.session.commit()
        for cat in default_cats:
            os.makedirs(os.path.join(app.config['TRAIN_FOLDER'], cat.name), exist_ok=True)
        flash("Web Database and folders successfully reset!", "success")
        return redirect(url_for('register_page'))
    except Exception as e:
        return f"Web Database Reset Failed: {str(e)}"

# --- CNN ADMIN ROUTES ---
@app.route('/cnn-admin')
@roles_required('Admin')
def cnn_admin():
    categories = Category.query.all()
    dataset = {}
    for cat in categories:
        path = os.path.join(app.config['TRAIN_FOLDER'], cat.name)
        dataset[cat.name] = os.listdir(path) if os.path.exists(path) else []
    return render_template('cnn_admin.html', categories=categories, dataset=dataset)

@app.route('/api/cnn/add-category', methods=['POST'])
@roles_required('Admin')
def add_category():
    name = request.form.get('name')
    severity = request.form.get('severity')
    if name:
        new_cat = Category(name=name, severity=severity)
        db.session.add(new_cat)
        db.session.commit()
        os.makedirs(os.path.join(app.config['TRAIN_FOLDER'], name), exist_ok=True)
        flash(f"Category {name} added!", "success")
    return redirect(url_for('cnn_admin'))

@app.route('/api/cnn/upload', methods=['POST'])
@roles_required('Admin')
def upload_training_image():
    category = request.form.get('category')
    file = request.files.get('file')
    if file and category:
        filename = secure_filename(file.filename)
        save_path = os.path.join(app.config['TRAIN_FOLDER'], category, filename)
        file.save(save_path)
        flash("Training image uploaded successfully!", "success")
    return redirect(url_for('cnn_admin'))

@app.route('/api/cnn/delete-image', methods=['POST'])
@roles_required('Admin')
def delete_training_image():
    category = request.form.get('category')
    filename = request.form.get('filename')
    file_path = os.path.join(app.config['TRAIN_FOLDER'], category, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        flash("Image removed.", "info")
    return redirect(url_for('cnn_admin'))

# --- NAVIGATION ---
@app.route('/')
@login_required
def index():
    return render_template('index.html', categories=Category.query.all())

@app.route('/heatmap')
@login_required
def heatmap():
    return render_template('heatmap.html')

@app.route('/reports')
@login_required
def reports():
    incidents = Incident.query.order_by(Incident.created_at.desc()).all()
    return render_template('reports.html', incidents=incidents)

@app.route('/contacts')
@login_required
def contacts():
    return render_template('contacts.html')

@app.route('/login')
def login_page(): return render_template('login.html')

@app.route('/register')
def register_page(): return render_template('register.html')

# --- API ROUTES ---
@app.route('/api/incident-data')
def incident_data():
    incidents = Incident.query.all()
    data = [[inc.latitude, inc.longitude, 0.8] for inc in incidents if inc.latitude and inc.longitude]
    return jsonify(data)

@app.route('/api/register', methods=['POST'])
def register():
    u, p, r = request.form.get('username'), request.form.get('password'), request.form.get('role')
    if User.query.filter_by(username=u).first():
        flash("Username already taken.", "danger")
        return redirect(url_for('register_page'))
    db.session.add(User(username=u, password=generate_password_hash(p), role=r))
    db.session.commit()
    flash("Registration successful! Please login.", "success")
    return redirect(url_for('login_page'))

@app.route('/api/login', methods=['POST'])
def login():
    user = User.query.filter_by(username=request.form.get('username')).first()
    if user and check_password_hash(user.password, request.form.get('password')):
        login_user(user)
        return redirect(url_for('index'))
    flash("Invalid login.", "danger")
    return redirect(url_for('login_page'))

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login_page'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
