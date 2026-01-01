import os
import datetime
import numpy as np
import cv2
import tensorflow as tf
import threading
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import text
from tensorflow.keras import backend as K

# --- DIRECTORY SETUP ---
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

# Global Status for Training
training_info = {"status": "Idle", "last_run": None}

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

# --- HELPERS ---
def get_dataset_counts():
    counts = {}
    if os.path.exists(app.config['TRAIN_FOLDER']):
        for cat_dir in os.listdir(app.config['TRAIN_FOLDER']):
            path = os.path.join(app.config['TRAIN_FOLDER'], cat_dir)
            if os.path.isdir(path):
                counts[cat_dir] = len(os.listdir(path))
    return counts

# --- AI THREADED TRAINING ENGINE ---
def run_training_task(app_context, categories):
    global training_info
    try:
        with app_context:
            training_info["status"] = "Processing Data..."
            K.clear_session()
            X, y = [], []
            for i, cat in enumerate(categories):
                cat_path = os.path.join(app.config['TRAIN_FOLDER'], cat.name)
                if not os.path.exists(cat_path): continue
                for img_name in os.listdir(cat_path):
                    img = cv2.imread(os.path.join(cat_path, img_name))
                    if img is not None:
                        X.append(cv2.resize(img, (150, 150)))
                        y.append(i)

            if len(X) < 2:
                training_info["status"] = "Error: Not enough data"
                return

            X = np.array(X).astype('float32') / 255.0
            y = np.array(y)

            training_info["status"] = "Fitting Neural Network..."
            model = tf.keras.models.Sequential([
                tf.keras.layers.Conv2D(16, (3,3), activation='relu', input_shape=(150, 150, 3)),
                tf.keras.layers.MaxPooling2D(2,2),
                tf.keras.layers.Flatten(),
                tf.keras.layers.Dense(32, activation='relu'),
                tf.keras.layers.Dense(len(categories), activation='softmax')
            ])
            model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
            
            # epochs set to 5 for faster training on limited resources
            model.fit(X, y, epochs=5, batch_size=4, verbose=0)
            model.save(app.config['MODEL_PATH'])
            
            K.clear_session()
            training_info["status"] = "Success"
            training_info["last_run"] = datetime.datetime.now().strftime("%I:%M %p")
    except Exception as e:
        training_info["status"] = f"Failed: {str(e)}"

# --- ADMIN API ---
@app.route('/api/admin/train-model', methods=['POST'])
@login_required
def train_model():
    if current_user.role != 'Admin': return jsonify({"status": "error"}), 403
    if training_info["status"] in ["Processing Data...", "Fitting Neural Network..."]:
        return jsonify({"status": "busy", "message": "Training already in progress."})
    
    categories = Category.query.order_by(Category.id).all()
    # Start background thread
    thread = threading.Thread(target=run_training_task, args=(app.app_context(), categories))
    thread.start()
    return jsonify({"status": "started", "message": "Training started in background."})

@app.route('/api/admin/train-status')
@login_required
def train_status():
    return jsonify(training_info)

@app.route('/api/admin/add-category', methods=['POST'])
@login_required
def add_category():
    if current_user.role != 'Admin': return jsonify({"status": "error"}), 403
    name, sev = request.form.get('name'), request.form.get('severity')
    if not Category.query.filter_by(name=name).first():
        db.session.add(Category(name=name, severity=sev))
        db.session.commit()
        os.makedirs(os.path.join(app.config['TRAIN_FOLDER'], name), exist_ok=True)
    return redirect(url_for('cnn_admin'))

@app.route('/api/admin/upload-training', methods=['POST'])
@login_required
def upload_training():
    if current_user.role != 'Admin': return jsonify({"status": "error"}), 403
    cat_name = request.form.get('category')
    files = request.files.getlist('images')
    cat_path = os.path.join(app.config['TRAIN_FOLDER'], cat_name)
    os.makedirs(cat_path, exist_ok=True)
    saved = 0
    for f in files:
        if f and f.filename != '':
            filename = secure_filename(f"{datetime.datetime.now().timestamp()}_{f.filename}")
            f.save(os.path.join(cat_path, filename))
            saved += 1
    return jsonify({"status": "success", "message": f"Saved {saved} images."})

@app.route('/api/admin/gallery/<category_name>')
@login_required
def get_gallery(category_name):
    if current_user.role != 'Admin': return jsonify([]), 403
    cat_path = os.path.join(app.config['TRAIN_FOLDER'], category_name)
    if not os.path.exists(cat_path): return jsonify([])
    images = [img for img in os.listdir(cat_path) if img.lower().endswith(('.png', '.jpg', '.jpeg'))]
    return jsonify(images)

@app.route('/api/admin/delete-training-image', methods=['POST'])
@login_required
def delete_training_image():
    if current_user.role != 'Admin': return jsonify({"status": "error"}), 403
    data = request.json
    file_path = os.path.join(app.config['TRAIN_FOLDER'], data.get('category'), data.get('filename'))
    if os.path.exists(file_path):
        os.remove(file_path)
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404

# --- RESIDENT ACTIONS ---
def process_and_classify(image_path):
    if not os.path.exists(app.config['MODEL_PATH']): return None, None
    try:
        K.clear_session()
        model = tf.keras.models.load_model(app.config['MODEL_PATH'])
        img = cv2.resize(cv2.imread(image_path), (150, 150))
        img = np.expand_dims(img.astype('float32') / 255.0, axis=0)
        res = model.predict(img)
        idx = np.argmax(res)
        all_cats = Category.query.order_by(Category.id).all()
        K.clear_session()
        if idx < len(all_cats): return all_cats[idx].name, all_cats[idx].severity
    except: pass
    return None, None

@app.route('/api/report', methods=['POST'])
@login_required
def create_report():
    img = request.files.get('image')
    lat, lng = request.form.get('lat'), request.form.get('lng')
    final_type = request.form.get('type')
    cat = Category.query.filter_by(name=final_type).first()
    final_sev = cat.severity if cat else "Low"
    filename = None
    if img:
        filename = secure_filename(f"{datetime.datetime.now().timestamp()}_{img.filename}")
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        img.save(path)
        ai_t, ai_s = process_and_classify(path)
        if ai_t: final_type, final_sev = ai_t, ai_s
    new_inc = Incident(incident_type=final_type, description=request.form.get('description'),
                       latitude=float(lat), longitude=float(lng), image_url=filename,
                       severity=final_sev, user_id=current_user.id)
    db.session.add(new_inc); db.session.commit()
    return jsonify({"status": "success", "classified_as": final_type})

# --- PAGE ROUTES ---
@app.route('/')
@login_required
def index(): return render_template('index.html', categories=Category.query.all())

@app.route('/reports')
@login_required
def reports():
    if current_user.role == 'Resident': return redirect(url_for('index'))
    return render_template('reports.html', incidents=Incident.query.order_by(Incident.created_at.desc()).all())

@app.route('/cnn-admin')
@login_required
def cnn_admin():
    if current_user.role != 'Admin': return redirect(url_for('index'))
    return render_template('cnn_admin.html', categories=Category.query.all(), counts=get_dataset_counts())

# --- AUTH ---
@app.route('/login')
def login_page(): return render_template('login.html')

@app.route('/api/register', methods=['POST'])
def register():
    hashed = generate_password_hash(request.form.get('password'))
    user = User(username=request.form.get('username'), password=hashed, role=request.form.get('role'))
    db.session.add(user); db.session.commit()
    return jsonify({"status": "success"})

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
