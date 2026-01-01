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
app.config['MODEL_PATH'] = os.path.join(base_dir, 'crime_model.h5')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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

# --- CNN LOGIC (ADMIN CONTROLLED) ---

def process_and_classify(image_path):
    """
    Used by Residents. 
    Compares the uploaded photo to the Admin's created CNN model.
    """
    if not os.path.exists(app.config['MODEL_PATH']):
        return None, None # No model created by Admin yet
        
    try:
        # Load the existing static model
        model = tf.keras.models.load_model(app.config['MODEL_PATH'])
        
        # Pre-process image for comparison
        img = cv2.imread(image_path)
        img = cv2.resize(img, (150, 150))
        img = np.expand_dims(img.astype('float32') / 255.0, axis=0)
        
        # Classify
        prediction = model.predict(img)
        class_idx = np.argmax(prediction)
        
        # Map back to Database Categories
        categories = Category.query.order_by(Category.id).all()
        if class_idx < len(categories):
            return categories[class_idx].name, categories[class_idx].severity
    except Exception as e:
        print(f"Classification Error: {e}")
    return None, None

# --- ROUTES ---

@app.route('/')
@login_required
def index():
    return render_template('index.html', categories=Category.query.all())

@app.route('/reports')
@login_required
def reports():
    if current_user.role == 'Resident': return redirect(url_for('index'))
    return render_template('reports.html', incidents=Incident.query.order_by(Incident.created_at.desc()).all())

@app.route('/cnn-admin')
@login_required
def cnn_admin():
    if current_user.role != 'Admin': return redirect(url_for('index'))
    model_exists = os.path.exists(app.config['MODEL_PATH'])
    return render_template('cnn_admin.html', categories=Category.query.all(), model_exists=model_exists)

# --- API ENDPOINTS ---

@app.route('/api/report', methods=['POST'])
@login_required
def create_report():
    img = request.files.get('image')
    lat = request.form.get('lat')
    lng = request.form.get('lng')
    
    # Default values from user input
    final_type = request.form.get('type')
    cat = Category.query.filter_by(name=final_type).first()
    final_sev = cat.severity if cat else "Low"
    filename = None
    
    if img:
        filename = secure_filename(f"{datetime.datetime.now().timestamp()}_{img.filename}")
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        img.save(path)
        
        # AI AUTOMATIC CLASSIFICATION (Comparing to Admin's Model)
        ai_label, ai_severity = process_and_classify(path)
        if ai_label:
            final_type = ai_label
            final_sev = ai_severity

    new_inc = Incident(
        incident_type=final_type,
        description=request.form.get('description'),
        latitude=float(lat),
        longitude=float(lng),
        image_url=filename,
        severity=final_sev,
        user_id=current_user.id
    )
    db.session.add(new_inc)
    db.session.commit()
    return jsonify({"status": "success", "classified_as": final_type})

@app.route('/api/admin/create-model', methods=['POST'])
@login_required
def create_cnn_model():
    """Builds and saves the CNN .h5 file for the first time or as an update."""
    if current_user.role != 'Admin': return jsonify({"status": "error"}), 403
    
    try:
        categories = Category.query.all()
        num_classes = len(categories)
        
        model = tf.keras.models.Sequential([
            tf.keras.layers.Conv2D(32, (3,3), activation='relu', input_shape=(150, 150, 3)),
            tf.keras.layers.MaxPooling2D(2,2),
            tf.keras.layers.Conv2D(64, (3,3), activation='relu'),
            tf.keras.layers.MaxPooling2D(2,2),
            tf.keras.layers.Flatten(),
            tf.keras.layers.Dense(128, activation='relu'),
            tf.keras.layers.Dense(num_classes, activation='softmax')
        ])
        model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
        
        # Save the model file
        model.save(app.config['MODEL_PATH'])
        return jsonify({"status": "success", "message": "CNN Model Created & Published for users!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Other Auth Routes... (Login/Register/Reset-DB)
