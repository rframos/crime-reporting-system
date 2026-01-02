import os, datetime, shutil
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, abort, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
app = Flask(__name__, root_path=base_dir, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'sjdm_safe_city_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'local.db')
app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, 'static/uploads')
app.config['TRAIN_FOLDER'] = os.path.join(base_dir, 'static/training_data')

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login_page'

# --- MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    password = db.Column(db.String(255))
    role = db.Column(db.String(20)) # Resident, Police Officer, Admin

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    severity = db.Column(db.String(20))

class Incident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    incident_type = db.Column(db.String(50))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    severity = db.Column(db.String(20))
    image_url = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))

# --- ROUTES ---

@app.route('/reset-db')
def reset_db():
    db.drop_all()
    db.create_all()
    # Create Admin
    admin = User(username="admin", password=generate_password_hash("admin123"), role="Admin")
    db.session.add(admin)
    db.session.commit()
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['TRAIN_FOLDER'], exist_ok=True)
    flash("Database Reset & Admin Created (admin/admin123)", "success")
    return redirect(url_for('login_page'))

@app.route('/api/register', methods=['POST'])
def register():
    u, p, r = request.form.get('username'), request.form.get('password'), request.form.get('role')
    if User.query.filter_by(username=u).first():
        flash("User already exists!", "danger")
        return redirect(url_for('register_page'))
    db.session.add(User(username=u, password=generate_password_hash(p), role=r))
    db.session.commit()
    flash("Registration Successful! Please Login.", "success")
    return redirect(url_for('login_page'))

@app.route('/api/add-category', methods=['POST'])
@login_required
def add_category():
    name = request.form.get('name')
    sev = request.form.get('severity')
    if not Category.query.filter_by(name=name).first():
        db.session.add(Category(name=name, severity=sev))
        db.session.commit()
        os.makedirs(os.path.join(app.config['TRAIN_FOLDER'], name), exist_ok=True)
        flash(f"Category {name} added!", "success")
    return redirect(url_for('cnn_admin'))

@app.route('/api/report-incident', methods=['POST'])
@login_required
def report_incident():
    file = request.files.get('image')
    filename = ""
    if file:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    
    new_report = Incident(
        incident_type=request.form.get('incident_type'),
        latitude=float(request.form.get('lat')),
        longitude=float(request.form.get('lng')),
        severity=request.form.get('severity'),
        image_url=filename
    )
    db.session.add(new_report)
    db.session.commit()
    flash("Incident Reported Successfully!", "success")
    return redirect(url_for('index'))

@app.route('/')
@login_required
def index():
    return render_template('index.html', categories=Category.query.all())

@app.route('/cnn-admin')
@login_required
def cnn_admin():
    return render_template('cnn_admin.html', categories=Category.query.all())

@app.route('/login')
def login_page(): return render_template('login.html')

@app.route('/register')
def register_page(): return render_template('register.html')

@app.route('/api/login', methods=['POST'])
def login():
    user = User.query.filter_by(username=request.form.get('username')).first()
    if user and check_password_hash(user.password, request.form.get('password')):
        login_user(user)
        return redirect(url_for('index'))
    flash("Invalid Credentials", "danger")
    return redirect(url_for('login_page'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
