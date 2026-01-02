import os
import datetime
import shutil
import gc
import threading
import numpy as np
import tensorflow as tf
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, abort, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Force TensorFlow to use minimal memory
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' 

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
app = Flask(__name__, root_path=base_dir, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'sjdm_safe_city_2026'

db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///' + os.path.join(base_dir, 'local.db')

app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, 'static/uploads')
app.config['TRAIN_FOLDER'] = os.path.join(base_dir, 'static/training_data')
app.config['MODEL_PATH'] = os.path.join(base_dir, 'static/incident_model.h5')

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

# --- OPTIMIZED AI TRAINING ---
def run_training_in_background():
    """Ultra-lean training for 512MB RAM environments."""
    with app.app_context():
        try:
            # Using 32x32 images drastically reduces RAM usage
            datagen = tf.keras.preprocessing.image.ImageDataGenerator(rescale=1./255)
            train_gen = datagen.flow_from_directory(
                app.config['TRAIN_FOLDER'], 
                target_size=(32, 32), 
                batch_size=8, 
                class_mode='categorical'
            )
            
            if train_gen.samples == 0: return

            model = tf.keras.Sequential([
                tf.keras.layers.Conv2D(8, (3,3), activation='relu', input_shape=(32, 32, 3)),
                tf.keras.layers.MaxPooling2D(2,2),
                tf.keras.layers.Flatten(),
                tf.keras.layers.Dense(train_gen.num_classes, activation='softmax')
            ])
            
            model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
            model.fit(train_gen, epochs=3, verbose=0)
            model.save(app.config['MODEL_PATH'])
            
            # Explicitly clear memory
            del model
            tf.keras.backend.clear_session()
            gc.collect()
        except Exception as e:
            print(f"Training Error: {e}")

@app.route('/api/cnn/train', methods=['POST'])
@roles_required('Admin')
def train_model():
    thread = threading.Thread(target=run_training_in_background)
    thread.start()
    flash("Training started in background. This may take 2-5 minutes.", "info")
    return redirect(url_for('cnn_admin'))

# --- ROUTES ---
@app.route('/')
@login_required
def index(): 
    return render_template('index.html', categories=Category.query.all())

@app.route('/cnn-admin')
@roles_required('Admin')
def cnn_admin():
    categories = Category.query.all()
    dataset = {cat.name: os.listdir(os.path.join(app.config['TRAIN_FOLDER'], cat.name)) 
               for cat in categories if os.path.exists(os.path.join(app.config['TRAIN_FOLDER'], cat.name))}
    return render_template('cnn_admin.html', categories=categories, dataset=dataset)

@app.route('/api/cnn/upload', methods=['POST'])
@roles_required('Admin')
def upload_training_images():
    cat = request.form.get('category')
    files = request.files.getlist('files')
    if files and cat:
        path = os.path.join(app.config['TRAIN_FOLDER'], cat)
        os.makedirs(path, exist_ok=True)
        for f in files:
            if f.filename:
                f.save(os.path.join(path, secure_filename(f.filename)))
    return redirect(url_for('cnn_admin'))

# Auth and other basic routes remain as defined in your source...
@app.route('/login')
def login_page(): return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def login():
    user = User.query.filter_by(username=request.form.get('username')).first()
    if user and check_password_hash(user.password, request.form.get('password')):
        login_user(user)
        return redirect(url_for('index'))
    return redirect(url_for('login_page'))

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
