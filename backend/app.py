import os
import datetime
import shutil
import zipfile
import io
import numpy as np
import tensorflow as tf
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, abort, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# --- CONFIGURATION ---
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
app = Flask(__name__, root_path=base_dir, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'sjdm_rose_pink_secure_2026')

# Database Connection
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///' + os.path.join(base_dir, 'local.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Paths
app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, 'static/uploads')
app.config['TRAIN_FOLDER'] = os.path.join(base_dir, 'static/training_data')
app.config['MODEL_PATH'] = os.path.join(base_dir, 'static/incident_model.h5')

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
    image_url = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role not in roles: return abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- DATASET BACKUP & RESTORE ---
@app.route('/api/cnn/export-dataset')
@roles_required('Admin')
def export_dataset():
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(app.config['TRAIN_FOLDER']):
            for file in files:
                file_path = os.path.join(root, file)
                zf.write(file_path, os.path.relpath(file_path, app.config['TRAIN_FOLDER']))
    memory_file.seek(0)
    return send_file(memory_file, download_name='sjdm_dataset_backup.zip', as_attachment=True)

@app.route('/api/cnn/import-dataset', methods=['POST'])
@roles_required('Admin')
def import_dataset():
    file = request.files.get('zip_file')
    if file and file.filename.endswith('.zip'):
        with zipfile.ZipFile(file) as zf:
            zf.extractall(app.config['TRAIN_FOLDER'])
            # Sync extracted folders into Database Categories
            for d in os.listdir(app.config['TRAIN_FOLDER']):
                if os.path.isdir(os.path.join(app.config['TRAIN_FOLDER'], d)):
                    if not Category.query.filter_by(name=d).first():
                        db.session.add(Category(name=d, severity="Medium"))
            db.session.commit()
        flash("Dataset and Categories restored!", "success")
    return redirect(url_for('cnn_admin'))

# --- CNN TRAINING ---
@app.route('/api/cnn/train', methods=['POST'])
@roles_required('Admin')
def train_model():
    try:
        datagen = tf.keras.preprocessing.image.ImageDataGenerator(rescale=1./255, validation_split=0.2)
        train_gen = datagen.flow_from_directory(
            app.config['TRAIN_FOLDER'], 
            target_size=(128,128), 
            batch_size=32, 
            class_mode='categorical', 
            subset='training'
        )
        
        if train_gen.samples == 0:
            flash("Upload training images first!", "danger")
            return redirect(url_for('cnn_admin'))

        model = tf.keras.Sequential([
            tf.keras.layers.Conv2D(32, (3,3), activation='relu', input_shape=(128,128,3)),
            tf.keras.layers.MaxPooling2D(2,2),
            tf.keras.layers.Flatten(),
            tf.keras.layers.Dense(train_gen.num_classes, activation='softmax')
        ])
        model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
        model.fit(train_gen, epochs=5)
        model.save(app.config['MODEL_PATH'])
        flash("AI Model trained successfully!", "success")
    except Exception as e: 
        flash(f"Training failed: {str(e)}", "danger")
    return redirect(url_for('cnn_admin'))

# --- NAVIGATION & DASHBOARD ---
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/cnn-admin')
@roles_required('Admin')
def cnn_admin():
    categories = Category.query.all()
    dataset = {}
    for cat in categories:
        path = os.path.join(app.config['TRAIN_FOLDER'], cat.name)
        if not os.path.exists(path): os.makedirs(path, exist_ok=True)
        dataset[cat.name] = os.listdir(path)
    return render_template('cnn_admin.html', categories=categories, dataset=dataset)

@app.route('/api/cnn/upload', methods=['POST'])
@roles_required('Admin')
def upload_training_images():
    cat = request.form.get('category')
    files = request.files.getlist('files') # Supports multiple files
    if files and cat:
        target_dir = os.path.join(app.config['TRAIN_FOLDER'], cat)
        os.makedirs(target_dir, exist_ok=True)
        for file in files:
            if file.filename:
                file.save(os.path.join(target_dir, secure_filename(file.filename)))
        flash(f"Uploaded {len(files)} images to {cat}", "success")
    return redirect(url_for('cnn_admin'))

@app.route('/api/incident/report', methods=['POST'])
@login_required
def report_incident():
    file = request.files.get('file')
    lat, lng = request.form.get('latitude'), request.form.get('longitude')
    if file:
        filename = secure_filename(f"{datetime.datetime.now().timestamp()}_{file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Classification
        ptype = "Unclassified"
        if os.path.exists(app.config['MODEL_PATH']):
            model = tf.keras.models.load_model(app.config['MODEL_PATH'])
            img = tf.keras.preprocessing.image.load_img(filepath, target_size=(128,128))
            arr = tf.keras.preprocessing.image.img_to_array(img)/255.0
            pred = model.predict(np.expand_dims(arr, axis=0))
            cats = sorted(os.listdir(app.config['TRAIN_FOLDER']))
            ptype = cats[np.argmax(pred)]

        new_inc = Incident(incident_type=ptype, latitude=float(lat or 0), longitude=float(lng or 0), image_url=filename)
        db.session.add(new_inc); db.session.commit()
        flash(f"Incident reported: {ptype}", "success")
    return redirect(url_for('index'))

# Standard Auth Routes
@app.route('/api/register', methods=['POST'])
def register():
    u, p, r = request.form.get('username'), request.form.get('password'), request.form.get('role')
    db.session.add(User(username=u, password=generate_password_hash(p), role=r))
    db.session.commit(); return redirect(url_for('login_page'))

@app.route('/api/login', methods=['POST'])
def login():
    user = User.query.filter_by(username=request.form.get('username')).first()
    if user and check_password_hash(user.password, request.form.get('password')):
        login_user(user); return redirect(url_for('index'))
    return redirect(url_for('login_page'))

@app.route('/login')
def login_page(): return render_template('login.html')
@app.route('/register')
def register_page(): return render_template('register.html')
@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login_page'))

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
