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

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
app = Flask(__name__, root_path=base_dir, template_folder='templates', static_folder='static')

# --- CONFIG ---
app.config['SECRET_KEY'] = 'safecity_sjdm_2026_ai'
app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, 'static/uploads')
app.config['MODEL_PATH'] = os.path.join(base_dir, 'crime_model.h5')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database
uri = os.environ.get('DATABASE_URL', 'sqlite:///local.db').replace("postgres://", "postgresql://", 1)
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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))

# --- SERVER-SIDE TRAINING LOGIC ---
@app.route('/api/train', methods=['POST'])
@login_required
def train_model_on_server():
    if current_user.role != 'Admin': return jsonify({"status": "error"}), 403
    
    try:
        # 1. Prepare Data from Database & Uploads
        incidents = Incident.query.filter(Incident.image_url != None).all()
        categories = [c.name for c in Category.query.order_by(Category.id).all()]
        
        if len(incidents) < 5:
            return jsonify({"status": "error", "message": "Need at least 5 images to train."})

        X, y = [], []
        for inc in incidents:
            img_path = os.path.join(app.config['UPLOAD_FOLDER'], inc.image_url)
            if os.path.exists(img_path):
                img = cv2.imread(img_path)
                img = cv2.resize(img, (150, 150)) # Smaller size for server RAM
                X.append(img)
                y.append(categories.index(inc.incident_type))

        X = np.array(X).astype('float32') / 255.0
        y = np.array(y)

        # 2. Build Simple CNN
        model = tf.keras.models.Sequential([
            tf.keras.layers.Conv2D(16, (3,3), activation='relu', input_shape=(150, 150, 3)),
            tf.keras.layers.MaxPooling2D(2,2),
            tf.keras.layers.Flatten(),
            tf.keras.layers.Dense(32, activation='relu'),
            tf.keras.layers.Dense(len(categories), activation='softmax')
        ])
        
        model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
        
        # 3. Train (Small epochs to prevent server timeout)
        model.fit(X, y, epochs=5, batch_size=4)
        
        # 4. Save to Server Storage
        model.save(app.config['MODEL_PATH'])
        
        return jsonify({"status": "success", "message": "Model trained and saved on server!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# --- PREDICTION LOGIC ---
def process_and_classify(image_path):
    if not os.path.exists(app.config['MODEL_PATH']): return None, None
    try:
        model = tf.keras.models.load_model(app.config['MODEL_PATH'])
        img = cv2.imread(image_path)
        img = cv2.resize(img, (150, 150))
        img = np.expand_dims(img.astype('float32') / 255.0, axis=0)
        res = model.predict(img)
        idx = np.argmax(res)
        cat = Category.query.order_by(Category.id).all()[idx]
        return cat.name, cat.severity
    except: return None, None

# --- REST OF ROUTES (Login, Reports, Heatmap, etc.) ---
@app.route('/')
@login_required
def index():
    return render_template('index.html', categories=Category.query.all())

@app.route('/login')
def login_page(): return render_template('login.html')

@app.route('/reports')
@login_required
def reports():
    incidents = Incident.query.order_by(Incident.created_at.desc()).all()
    return render_template('reports.html', incidents=incidents)

@app.route('/cnn-admin')
@login_required
def cnn_admin():
    return render_template('cnn_admin.html', categories=Category.query.all())

@app.route('/api/report', methods=['POST'])
@login_required
def create_report():
    image_file = request.files.get('image')
    lat, lng = request.form.get('lat'), request.form.get('lng')
    final_type = request.form.get('type')
    cat = Category.query.filter_by(name=final_type).first()
    final_sev = cat.severity if cat else "Low"
    filename = None

    if image_file:
        filename = secure_filename(f"{datetime.datetime.now().timestamp()}_{image_file.filename}")
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image_file.save(path)
        ai_t, ai_s = process_and_classify(path)
        if ai_t: final_type, final_sev = ai_t, ai_s

    new_inc = Incident(incident_type=final_type, description=request.form.get('description'),
                       latitude=float(lat), longitude=float(lng), image_url=filename,
                       severity=final_sev, user_id=current_user.id)
    db.session.add(new_inc)
    db.session.commit()
    return jsonify({"status": "success"})

@app.route('/api/register', methods=['POST'])
def register():
    hashed = generate_password_hash(request.form.get('password'))
    db.session.add(User(username=request.form.get('username'), password=hashed, role=request.form.get('role')))
    db.session.commit()
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
