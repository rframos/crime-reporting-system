import os
import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# Setup directories
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

app = Flask(__name__, 
            root_path=base_dir,
            template_folder='templates',
            static_folder='static')

# Configs
uri = os.environ.get('DATABASE_URL')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri or 'sqlite:///local.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'dev_secret_key_123' 

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login_page'

# --- MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='Resident') # Admin, Official, Resident, Police

class Incident(db.Model):
    __tablename__ = 'incidents'
    id = db.Column(db.Integer, primary_key=True)
    incident_type = db.Column(db.String(50))
    description = db.Column(db.Text)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    status = db.Column(db.String(20), default='Pending')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- AUTH ROUTES ---
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.form
        if User.query.filter_by(username=data.get('username')).first():
            return jsonify({"status": "error", "message": "User already exists"}), 400
        
        hashed_pw = generate_password_hash(data.get('password'))
        new_user = User(
            username=data.get('username'),
            password=hashed_pw,
            role=data.get('role', 'Resident')
        )
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"status": "success", "message": "Registered! You can now login."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/login', methods=['POST'])
def login():
    data = request.form
    user = User.query.filter_by(username=data.get('username')).first()
    if user and check_password_hash(user.password, data.get('password')):
        login_user(user)
        return jsonify({"status": "success", "role": user.role})
    return jsonify({"status": "error", "message": "Invalid credentials"}), 401

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- APP ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/incidents', methods=['GET'])
def get_incidents():
    incidents = Incident.query.all()
    return jsonify([{
        "id": i.id, "type": i.incident_type, "description": i.description,
        "lat": i.latitude, "lng": i.longitude, "status": i.status,
        "date": i.created_at.strftime("%Y-%m-%d %H:%M")
    } for i in incidents])

@app.route('/api/report', methods=['POST'])
@login_required
def create_report():
    try:
        data = request.form
        new_incident = Incident(
            incident_type=data.get('type'),
            description=data.get('description', ''),
            latitude=float(data.get('lat')),
            longitude=float(data.get('lng')),
            user_id=current_user.id
        )
        db.session.add(new_incident)
        db.session.commit()
        return jsonify({"status": "success"}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/reset-db')
def reset_db():
    db.drop_all()
    db.create_all()
    return "Database updated with User authentication!"

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
