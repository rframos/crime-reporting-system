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
    role = db.Column(db.String(20), default='Resident') # Admin, Police, Official, Resident

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

# --- AI LOGIC ---
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

# --- PAGE ROUTES ---
@app.route('/')
@login_required
def index():
    return render_template('index.html', categories=Category.query.all())

@app.route('/login')
def login_page(): return render_template('login.html')

@app.route('/reports')
@login_required
def reports():
    if current_user.role == 'Resident': return redirect(url_for('index'))
    incidents = Incident.query.order_by(Incident.created_at.desc()).all()
    return render_template('reports.html', incidents=incidents)

@app.route('/heatmap')
@login_required
def heatmap():
    if current_user.role not in ['Admin', 'Police', 'Official']: return redirect(url_for('index'))
    return render_template('heatmap.html')

@app.route('/cnn-admin')
@login_required
def cnn_admin():
    if current_user.role != 'Admin': return redirect(url_for('index'))
    return render_template('cnn_admin.html', categories=Category.query.order_by(Category.id).all())

# --- API ROUTES ---
@app.route('/api/register', methods=['POST'])
def register():
    try:
        username = request.form.get('username')
        if User.query.filter_by(username=username).first():
            return jsonify({"status": "error", "message": "User already exists"}), 400
        hashed = generate_password_hash(request.form.get('password'))
        new_user = User(username=username, password=hashed, role=request.form.get('role'))
        db.session.add(new_user); db.session.commit()
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/login', methods=['POST'])
def login():
    user = User.query.filter_by(username=request.form.get('username')).first()
    if user and check_password_hash(user.password, request.form.get('password')):
        login_user(user); return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 401

@app.route('/api/report', methods=['POST'])
@login_required
def create_report():
    try:
        img = request.files.get('image')
        lat, lng = request.form.get('lat'), request.form.get('lng')
        if not lat or not lng: return jsonify({"status": "error", "message": "Pin location"}), 400
        
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
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/categories', methods=['POST'])
@login_required
def manage_categories():
    if current_user.role == 'Admin':
        name, sev = request.form.get('name'), request.form.get('severity')
        cat = Category.query.filter_by(name=name).first()
        if cat: cat.severity = sev
        else: db.session.add(Category(name=name, severity=sev))
        db.session.commit()
    return redirect(url_for('cnn_admin'))

@app.route('/api/incidents', methods=['GET'])
@login_required
def get_incidents():
    incidents = Incident.query.all()
    return jsonify([{"lat": i.latitude, "lng": i.longitude, "type": i.incident_type, "severity": i.severity} for i in incidents])

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login_page'))

@app.route('/reset-db')
def reset_db():
    try:
        db.session.remove()
        db.drop_all()
        db.create_all()
        for n, s in [('Theft','Medium'), ('Fire','Critical'), ('Vandalism','Low')]:
            db.session.add(Category(name=n, severity=s))
        db.session.commit()
        return "Database Ready! Tables recreated and default categories added."
    except Exception as e:
        return f"Error resetting database: {str(e)}"

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True)
