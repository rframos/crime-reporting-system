import os
import datetime
import numpy as np
import cv2
import tensorflow as tf
import threading
import shutil
import zipfile
from io import BytesIO
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from tensorflow.keras import backend as K

# --- SETUP ---
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
app = Flask(__name__, root_path=base_dir, template_folder='templates', static_folder='static')

app.config['SECRET_KEY'] = 'safecity_sjdm_2026_final'
app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, 'static/uploads')
app.config['TRAIN_FOLDER'] = os.path.join(base_dir, 'static/training_data')
app.config['MODEL_PATH'] = os.path.join(base_dir, 'crime_model.h5')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['TRAIN_FOLDER'], exist_ok=True)

uri = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
if uri.startswith("postgres://"): uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login_page'

training_info = {"status": "Idle", "last_run": "Never"}

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
    description = db.Column(db.Text)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    status = db.Column(db.String(20), default='Pending')
    severity = db.Column(db.String(20), default='Low')
    confidence = db.Column(db.Float, default=0.0)
    image_url = db.Column(db.String(255), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))

# --- RBAC ---
def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role not in roles:
                return abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- AI LOGIC ---
def process_and_classify(image_path):
    if not os.path.exists(app.config['MODEL_PATH']): return None, None, 0
    try:
        K.clear_session()
        model = tf.keras.models.load_model(app.config['MODEL_PATH'])
        img = cv2.resize(cv2.imread(image_path), (150, 150))
        img = np.expand_dims(img.astype('float32') / 255.0, axis=0)
        preds = model.predict(img)
        idx = np.argmax(preds[0])
        conf = float(np.max(preds[0]) * 100)
        cats = Category.query.order_by(Category.id).all()
        K.clear_session()
        if idx < len(cats): return cats[idx].name, cats[idx].severity, conf
    except: pass
    return None, None, 0

# --- ROUTES ---
@app.route('/')
@login_required
def index(): 
    return render_template('index.html', categories=Category.query.all())

@app.route('/heatmap')
@roles_required('Admin', 'Police', 'Barangay')
def heatmap_page(): 
    return render_template('heatmap.html', categories=Category.query.all())

@app.route('/contact')
@roles_required('Resident', 'Barangay')
def contact_page(): 
    return render_template('contacts.html')

@app.route('/reports')
@roles_required('Admin', 'Police', 'Barangay')
def reports():
    incidents = Incident.query.order_by(Incident.created_at.desc()).all()
    return render_template('reports.html', incidents=incidents)

@app.route('/cnn-admin')
@roles_required('Admin')
def cnn_admin():
    counts = {}
    if os.path.exists(app.config['TRAIN_FOLDER']):
        for d in os.listdir(app.config['TRAIN_FOLDER']):
            if os.path.isdir(os.path.join(app.config['TRAIN_FOLDER'], d)):
                counts[d] = len(os.listdir(os.path.join(app.config['TRAIN_FOLDER'], d)))
    return render_template('cnn_admin.html', categories=Category.query.all(), counts=counts)

# --- API ---
@app.route('/api/incidents')
@login_required
def get_incidents_api():
    incidents = Incident.query.all()
    return jsonify([{
        "lat": i.latitude, 
        "lng": i.longitude, 
        "type": i.incident_type
    } for i in incidents])

@app.route('/api/report', methods=['POST'])
@login_required
def create_report():
    img = request.files.get('image')
    lat, lng = request.form.get('lat'), request.form.get('lng')
    final_type = request.form.get('type')
    cat = Category.query.filter_by(name=final_type).first()
    f_sev, f_conf, f_name = (cat.severity if cat else "Low"), 0.0, None
    if img:
        f_name = secure_filename(f"{datetime.datetime.now().timestamp()}_{img.filename}")
        path = os.path.join(app.config['UPLOAD_FOLDER'], f_name)
        img.save(path)
        ai_t, ai_s, ai_c = process_and_classify(path)
        if ai_t: final_type, f_sev, f_conf = ai_t, ai_s, ai_c
    new_inc = Incident(incident_type=final_type, description=request.form.get('description'),
                       latitude=float(lat), longitude=float(lng), image_url=f_name,
                       severity=f_sev, confidence=round(f_conf, 2), user_id=current_user.id)
    db.session.add(new_inc); db.session.commit()
    return jsonify({"status": "success", "classified_as": final_type, "confidence": f_conf})

# --- RESET & AUTH ---
@app.route('/reset-db')
def reset_db():
    if os.path.exists(app.config['TRAIN_FOLDER']): shutil.rmtree(app.config['TRAIN_FOLDER'])
    os.makedirs(app.config['TRAIN_FOLDER'], exist_ok=True)
    if os.path.exists(app.config['MODEL_PATH']): os.remove(app.config['MODEL_PATH'])
    db.drop_all(); db.create_all()
    for n, s in [('Theft','Medium'), ('Fire','Critical')]:
        db.session.add(Category(name=n, severity=s))
        os.makedirs(os.path.join(app.config['TRAIN_FOLDER'], n), exist_ok=True)
    db.session.commit()
    return redirect(url_for('login_page'))

@app.route('/login')
def login_page(): return render_template('login.html')

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
