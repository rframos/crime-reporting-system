import os
import datetime
import shutil
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# --- INITIALIZATION ---
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
app = Flask(__name__, root_path=base_dir, template_folder='templates', static_folder='static')

app.config['SECRET_KEY'] = 'sjdm_safe_city_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'local.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['TRAIN_FOLDER'] = os.path.join(base_dir, 'static/training_data')

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
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    status = db.Column(db.String(20), default='Pending')
    severity = db.Column(db.String(20), default='Low')
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

# --- CRITICAL ROUTES ---

@app.route('/reset-db')
def reset_db():
    """Forces database recreation and folder setup."""
    db.drop_all()
    db.create_all()
    
    # Default SJDM Categories
    cats = [
        Category(name="Theft", severity="Medium"),
        Category(name="Assault", severity="High"),
        Category(name="Vandalism", severity="Low")
    ]
    db.session.add_all(cats)
    db.session.commit()
    
    # Ensure training folders exist
    if os.path.exists(app.config['TRAIN_FOLDER']):
        shutil.rmtree(app.config['TRAIN_FOLDER'])
    os.makedirs(app.config['TRAIN_FOLDER'], exist_ok=True)
    for c in cats:
        os.makedirs(os.path.join(app.config['TRAIN_FOLDER'], c.name), exist_ok=True)
        
    return "Database Reset Success! <a href='/register'>Register Admin</a>"

@app.route('/')
def home_redirect():
    if current_user.is_authenticated:
        return render_template('index.html', categories=Category.query.all())
    return redirect(url_for('login_page'))

@app.route('/heatmap')
@login_required
def heatmap():
    return render_template('heatmap.html', categories=Category.query.all())

@app.route('/reports')
@login_required
def reports():
    items = Incident.query.order_by(Incident.created_at.desc()).all()
    return render_template('reports.html', incidents=items)

@app.route('/contacts')
@login_required
def contacts():
    return render_template('contacts.html')

@app.route('/cnn-admin')
@roles_required('Admin')
def cnn_admin():
    categories = Category.query.all()
    dataset = {}
    for cat in categories:
        path = os.path.join(app.config['TRAIN_FOLDER'], cat.name)
        dataset[cat.name] = os.listdir(path) if os.path.exists(path) else []
    return render_template('cnn_admin.html', categories=categories, dataset=dataset)

# --- API ---

@app.route('/api/incidents')
def get_incidents():
    t = request.args.get('type')
    s = request.args.get('severity')
    q = Incident.query
    if t and t != 'All': q = q.filter_by(incident_type=t)
    if s and s != 'All': q = q.filter_by(severity=s)
    return jsonify([{"lat": i.latitude, "lng": i.longitude} for i in q.all()])

@app.route('/api/register', methods=['POST'])
def register():
    u = request.form.get('username')
    p = request.form.get('password')
    r = request.form.get('role')
    if User.query.filter_by(username=u).first(): return "Exists", 400
    db.session.add(User(username=u, password=generate_password_hash(p), role=r))
    db.session.commit()
    return jsonify({"status": "success"})

@app.route('/api/login', methods=['POST'])
def login():
    user = User.query.filter_by(username=request.form.get('username')).first()
    if user and check_password_hash(user.password, request.form.get('password')):
        login_user(user)
        return jsonify({"status": "success"})
    return "Unauthorized", 401

@app.route('/login')
def login_page(): return render_template('login.html')

@app.route('/register')
def register_page(): return render_template('register.html')

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login_page'))

if __name__ == '__main__':
    # Render binding
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
