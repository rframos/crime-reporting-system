import os
import datetime
import shutil
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, abort, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# --- INITIALIZATION ---
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
app = Flask(__name__, root_path=base_dir, template_folder='templates', static_folder='static')

app.config['SECRET_KEY'] = 'sjdm_safe_city_2026_final'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'local.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['TRAIN_FOLDER'] = os.path.join(base_dir, 'static/training_data')

# Ensure core training folder exists
os.makedirs(app.config['TRAIN_FOLDER'], exist_ok=True)

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

# --- CNN ADMIN ROUTES ---

@app.route('/cnn-admin')
@roles_required('Admin')
def cnn_admin():
    categories = Category.query.all()
    dataset = {}
    for cat in categories:
        path = os.path.join(app.config['TRAIN_FOLDER'], cat.name)
        if os.path.exists(path):
            dataset[cat.name] = os.listdir(path)
        else:
            os.makedirs(path, exist_ok=True)
            dataset[cat.name] = []
    return render_template('cnn_admin.html', categories=categories, dataset=dataset)

@app.route('/api/add-category', methods=['POST'])
@roles_required('Admin')
def add_category():
    name = request.form.get('name').strip()
    severity = request.form.get('severity')
    if not name:
        flash("Category name cannot be empty!", "danger")
        return redirect(url_for('cnn_admin'))
    
    if not Category.query.filter_by(name=name).first():
        new_cat = Category(name=name, severity=severity)
        db.session.add(new_cat)
        db.session.commit()
        # Create folder for images
        os.makedirs(os.path.join(app.config['TRAIN_FOLDER'], name), exist_ok=True)
        flash(f"Category '{name}' created successfully!", "success")
    else:
        flash("Category already exists!", "warning")
    return redirect(url_for('cnn_admin'))

@app.route('/api/upload-training', methods=['POST'])
@roles_required('Admin')
def upload_training():
    cat_name = request.form.get('category')
    files = request.files.getlist('images')
    
    if not cat_name or not files:
        flash("Missing category or images!", "danger")
        return redirect(url_for('cnn_admin'))

    cat_path = os.path.join(app.config['TRAIN_FOLDER'], cat_name)
    os.makedirs(cat_path, exist_ok=True)
    
    count = 0
    for f in files:
        if f and f.filename != '':
            filename = secure_filename(f.filename)
            f.save(os.path.join(cat_path, filename))
            count += 1
    
    flash(f"Successfully uploaded {count} images to {cat_name}!", "success")
    return redirect(url_for('cnn_admin'))

@app.route('/api/delete-training-img', methods=['POST'])
@roles_required('Admin')
def delete_training_img():
    data = request.json
    cat = data.get('category')
    filename = data.get('filename')
    path = os.path.join(app.config['TRAIN_FOLDER'], cat, filename)
    if os.path.exists(path):
        os.remove(path)
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404

# --- AUTH ROUTES ---
@app.route('/')
@login_required
def index(): return render_template('index.html', categories=Category.query.all())

@app.route('/login')
def login_page(): return render_template('login.html')

@app.route('/register')
def register_page(): return render_template('register.html')

@app.route('/api/register', methods=['POST'])
def register():
    u, p, r = request.form.get('username'), request.form.get('password'), request.form.get('role')
    if User.query.filter_by(username=u).first():
        flash("Username taken!", "danger")
        return redirect(url_for('register_page'))
    db.session.add(User(username=u, password=generate_password_hash(p), role=r))
    db.session.commit()
    flash("Account created!", "success")
    return redirect(url_for('login_page'))

@app.route('/api/login', methods=['POST'])
def login():
    user = User.query.filter_by(username=request.form.get('username')).first()
    if user and check_password_hash(user.password, request.form.get('password')):
        login_user(user); return redirect(url_for('index'))
    flash("Login failed!", "danger")
    return redirect(url_for('login_page'))

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login_page'))

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
