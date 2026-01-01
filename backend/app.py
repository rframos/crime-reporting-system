import os
import datetime
import numpy as np
import cv2
import tensorflow as tf
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import text

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
app = Flask(__name__, root_path=base_dir, template_folder='templates', static_folder='static')

# --- CONFIG ---
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
    description = db.Column(db.Text)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    status = db.Column(db.String(20), default='Pending')
    severity = db.Column(db.String(20), default='Low')
    image_url = db.Column(db.String(255), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))

# --- CNN TRAINING ENGINE ---

@app.route('/api/admin/add-category', methods=['POST'])
@login_required
def add_category():
    if current_user.role != 'Admin': return jsonify({"status": "error"}), 403
    name = request.form.get('name')
    sev = request.form.get('severity')
    if not Category.query.filter_by(name=name).first():
        db.session.add(Category(name=name, severity=sev))
        db.session.commit()
        # Create folder for training images
        os.makedirs(os.path.join(app.config['TRAIN_FOLDER'], name), exist_ok=True)
    return redirect(url_for('cnn_admin'))

@app.route('/api/admin/upload-training', methods=['POST'])
@login_required
def upload_training_images():
    if current_user.role != 'Admin': return jsonify({"status": "error"}), 403
    category_name = request.form.get('category')
    files = request.files.getlist('images')
    
    cat_path = os.path.join(app.config['TRAIN_FOLDER'], category_name)
    for file in files:
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(cat_path, filename))
            
    return jsonify({"status": "success", "message": f"Uploaded {len(files)} images to {category_name}"})

@app.route('/api/admin/train-model', methods=['POST'])
@login_required
def train_model():
    if current_user.role != 'Admin': return jsonify({"status": "error"}), 403
    
    categories = Category.query.order_by(Category.id).all()
    X, y = [], []
    
    for i, cat in enumerate(categories):
        cat_path = os.path.join(app.config['TRAIN_FOLDER'], cat.name)
        if not os.path.exists(cat_path): continue
        
        for img_name in os.listdir(cat_path):
            img_p = os.path.join(cat_path, img_name)
            img = cv2.imread(img_p)
            if img is not None:
                img = cv2.resize(img, (150, 150))
                X.append(img)
                y.append(i)

    if len(X) < 1: return jsonify({"status": "error", "message": "No training images found."}), 400

    X = np.array(X).astype('float32') / 255.0
    y = np.array(y)

    model = tf.keras.models.Sequential([
        tf.keras.layers.Conv2D(32, (3,3), activation='relu', input_shape=(150, 150, 3)),
        tf.keras.layers.MaxPooling2D(2,2),
        tf.keras.layers.Conv2D(64, (3,3), activation='relu'),
        tf.keras.layers.MaxPooling2D(2,2),
        tf.keras.layers.Flatten(),
        tf.keras.layers.Dense(128, activation='relu'),
        tf.keras.layers.Dense(len(categories), activation='softmax')
    ])
    model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
    model.fit(X, y, epochs=10) # 10 epochs for better learning
    model.save(app.config['MODEL_PATH'])
    
    return jsonify({"status": "success", "message": "CNN Trained Successfully!"})

# Classification logic (same as previous)
def process_and_classify(image_path):
    if not os.path.exists(app.config['MODEL_PATH']): return None, None
    try:
        model = tf.keras.models.load_model(app.config['MODEL_PATH'])
        img = cv2.resize(cv2.imread(image_path), (150, 150))
        img = np.expand_dims(img.astype('float32') / 255.0, axis=0)
        idx = np.argmax(model.predict(img))
        cats = Category.query.order_by(Category.id).all()
        return (cats[idx].name, cats[idx].severity) if idx < len(cats) else (None, None)
    except: return None, None

@app.route('/cnn-admin')
@login_required
def cnn_admin():
    if current_user.role != 'Admin': return redirect(url_for('index'))
    return render_template('cnn_admin.html', categories=Category.query.all())

# Auth/Reset routes...
if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True)
