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

# --- CNN ENGINE ---
def init_cnn_model():
    if not os.path.exists(app.config['MODEL_PATH']):
        categories = Category.query.all()
        num_classes = len(categories) if categories else 3
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
        model.save(app.config['MODEL_PATH'])

def process_and_classify(image_path):
    if not os.path.exists(app.config['MODEL_PATH']): return None, None
    try:
        model = tf.keras.models.load_model(app.config['MODEL_PATH'])
        img = cv2.imread(image_path)
        img = cv2.resize(img, (150, 150))
        img = np.expand_dims(img.astype('float32') / 255.0, axis=0)
        res = model.predict(img)
        idx = np.argmax(res)
        all_cats = Category.query.order_by(Category.id).all()
        if idx < len(all_cats): return all_cats[idx].name, all_cats[idx].severity
    except: pass
    return None, None

# --- TRAINING API ---
@app.route('/api/train', methods=['POST'])
@login_required
def train_model():
    if current_user.role != 'Admin': return jsonify({"status": "error"}), 403
    
    incidents = Incident.query.filter(Incident.image_url != None).all()
    categories = Category.query.order_by(Category.id).all()
    cat_map = {cat.name: i for i, cat in enumerate(categories)}
    
    X, y = [], []
    for inc in incidents:
        img_path = os.path.join(app.config['UPLOAD_FOLDER'], inc.image_url)
        if os.path.exists(img_path):
            img = cv2.imread(img_path)
            img = cv2.resize(img, (150, 150))
            X.append(img)
            y.append(cat_map.get(inc.incident_type, 0))
    
    if len(X) < 5: # Minimum samples to start training
        return jsonify({"status": "error", "message": "Need at least 5 images to train."}), 400
        
    X = np.array(X).astype('float32') / 255.0
    y = np.array(y)
    
    model = tf.keras.models.load_model(app.config['MODEL_PATH'])
    model.fit(X, y, epochs=5)
    model.save(app.config['MODEL_PATH'])
    
    return jsonify({"status": "success", "message": "AI Training Complete!"})

# --- ROUTES ---
@app.route('/')
@login_required
def index(): return render_template('index.html', categories=Category.query.all())

@app.route('/login')
def login_page(): return render_template('login.html')

@app.route('/reports')
@login_required
def reports():
    if current_user.role == 'Resident': return redirect(url_for('index'))
    return render_template('reports.html', incidents=Incident.query.order_by(Incident.created_at.desc()).all())

@app.route('/heatmap')
@login_required
def heatmap():
    if current_user.role not in ['Admin', 'Police', 'Official']: return redirect(url_for('index'))
    return render_template('heatmap.html', categories=Category.query.all())

@app.route('/cnn-admin')
@login_required
def cnn_admin():
    if current_user.role != 'Admin': return redirect(url_for('index'))
    return render_template('cnn_admin.html', categories=Category.query.order_by(Category.id).all())

# --- API HELPERS ---
@app.route('/api/register', methods=['POST'])
def register():
    hashed = generate_password_hash(request.form.get('password'))
    new_user = User(username=request.form.get('username'), password=hashed, role=request.form.get('role'))
    db.session.add(new_user); db.session.commit()
    return jsonify({"status": "success"})

@app.route('/api/login', methods=['POST'])
def login():
    user = User.query.filter_by(username=request.form.get('username')).first()
    if user and check_password_hash(user.password, request.form.get('password')):
        login_user(user); return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 401

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
    return jsonify({"status": "success"})

@app.route('/api/incidents', methods=['GET'])
def get_incidents():
    incidents = Incident.query.all()
    return jsonify([{"lat": i.latitude, "lng": i.longitude, "type": i.incident_type, "severity": i.severity} for i in incidents])

@app.route('/api/categories', methods=['POST'])
def categories_api():
    db.session.add(Category(name=request.form.get('name'), severity=request.form.get('severity')))
    db.session.commit()
    return redirect(url_for('cnn_admin'))

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login_page'))

@app.route('/reset-db')
def reset_db():
    db.session.remove(); db.session.execute(text('DROP TABLE IF EXISTS incidents CASCADE;'))
    db.session.execute(text('DROP TABLE IF EXISTS "user" CASCADE;')); db.session.execute(text('DROP TABLE IF EXISTS category CASCADE;'))
    db.session.commit(); db.create_all()
    for n, s in [('Theft','Medium'), ('Fire','Critical'), ('Vandalism','Low')]: db.session.add(Category(name=n, severity=s))
    db.session.commit(); init_cnn_model()
    return "Reset Success"

if __name__ == '__main__':
    with app.app_context(): db.create_all(); init_cnn_model()
    app.run(debug=True)
