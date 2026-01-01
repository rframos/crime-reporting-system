import os
import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

app = Flask(__name__, 
            root_path=base_dir,
            template_folder='templates',
            static_folder='static')

# --- CONFIGURATION ---
app.config['SECRET_KEY'] = 'safecity_sjdm_2026_ai'
app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, 'static/uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

uri = os.environ.get('DATABASE_URL')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri or 'sqlite:///local.db'
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
    severity = db.Column(db.String(20), default='Low') # Admin can now edit this

class Incident(db.Model):
    __tablename__ = 'incidents'
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
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROUTES ---
@app.route('/')
@login_required
def index():
    categories = Category.query.all()
    return render_template('index.html', categories=categories)

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/reports')
@login_required
def reports():
    if current_user.role == 'Resident': return "Access Denied", 403
    incidents = Incident.query.order_by(Incident.created_at.desc()).all()
    return render_template('reports.html', incidents=incidents)

@app.route('/heatmap')
@login_required
def heatmap():
    if current_user.role not in ['Police', 'Admin']: return "Access Denied", 403
    categories = Category.query.all()
    return render_template('heatmap.html', categories=categories)

@app.route('/contacts')
@login_required
def contacts():
    return render_template('contacts.html')

@app.route('/cnn-admin')
@login_required
def cnn_admin():
    if current_user.role != 'Admin': return "Access Denied", 403
    categories = Category.query.all()
    return render_template('cnn_admin.html', categories=categories)

# --- API ---
@app.route('/api/categories', methods=['POST'])
@login_required
def add_category():
    if current_user.role == 'Admin':
        name = request.form.get('name')
        sev = request.form.get('severity')
        if name:
            cat = Category.query.filter_by(name=name).first()
            if cat: # Update existing
                cat.severity = sev
            else: # Create new
                db.session.add(Category(name=name, severity=sev))
            db.session.commit()
    return redirect(url_for('cnn_admin'))

@app.route('/api/report', methods=['POST'])
@login_required
def create_report():
    try:
        image_file = request.files.get('image')
        selected_type = request.form.get('type')
        
        # Determine Severity based on Admin settings for that type
        cat_info = Category.query.filter_by(name=selected_type).first()
        severity = cat_info.severity if cat_info else "Low"

        filename = None
        if image_file:
            filename = secure_filename(f"{datetime.datetime.now().timestamp()}_{image_file.filename}")
            image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        new_inc = Incident(
            incident_type=selected_type,
            description=request.form.get('description'),
            latitude=float(request.form.get('lat')),
            longitude=float(request.form.get('lng')),
            image_url=filename,
            severity=severity,
            user_id=current_user.id
        )
        db.session.add(new_inc)
        db.session.commit()
        return jsonify({"status": "success", "severity": severity})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/incidents', methods=['GET'])
@login_required
def get_incidents():
    incidents = Incident.query.all()
    return jsonify([{
        "id": i.id, "type": i.incident_type, "lat": i.latitude, 
        "lng": i.longitude, "status": i.status, "severity": i.severity
    } for i in incidents])

@app.route('/api/login', methods=['POST'])
def login():
    user = User.query.filter_by(username=request.form.get('username')).first()
    if user and check_password_hash(user.password, request.form.get('password')):
        login_user(user)
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 401

@app.route('/logout')
def logout():
    logout_user(); return redirect(url_for('login_page'))

@app.route('/reset-db')
def reset_db():
    db.drop_all(); db.create_all()
    defaults = [('Theft', 'Medium'), ('Vandalism', 'Low'), ('Assault', 'High')]
    for n, s in defaults: db.session.add(Category(name=n, severity=s))
    db.session.commit()
    return "Database Reset with Severity Settings!"

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True)
