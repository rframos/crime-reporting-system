import os
import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

app = Flask(__name__, 
            root_path=base_dir,
            template_folder='templates',
            static_folder='static')

# --- DATABASE CONFIG ---
uri = os.environ.get('DATABASE_URL')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri or 'sqlite:///local.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'safecity_sjdm_secret_2026' 

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

# --- PAGE ROUTES ---
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
    if current_user.role == 'Resident':
        return "Access Denied", 403
    incidents = Incident.query.order_by(Incident.created_at.desc()).all()
    return render_template('reports.html', incidents=incidents)

@app.route('/heatmap')
@login_required
def heatmap():
    if current_user.role not in ['Police', 'Admin']:
        return "Access Denied", 403
    categories = Category.query.all()
    return render_template('heatmap.html', categories=categories)

@app.route('/contacts')
@login_required
def contacts():
    return render_template('contacts.html')

@app.route('/cnn-admin')
@login_required
def cnn_admin():
    if current_user.role != 'Admin':
        return "Access Denied", 403
    categories = Category.query.all()
    return render_template('cnn_admin.html', categories=categories)

# --- API ROUTES ---
@app.route('/api/incident/<int:id>/status', methods=['POST'])
@login_required
def update_status(id):
    if current_user.role == 'Resident':
        return jsonify({"status": "error"}), 403
    incident = Incident.query.get_or_404(id)
    incident.status = request.form.get('status')
    db.session.commit()
    return jsonify({"status": "success"})

@app.route('/api/categories', methods=['POST'])
@login_required
def add_category():
    if current_user.role == 'Admin':
        name = request.form.get('name')
        if name and not Category.query.filter_by(name=name).first():
            db.session.add(Category(name=name))
            db.session.commit()
    return redirect(url_for('cnn_admin'))

@app.route('/api/report', methods=['POST'])
@login_required
def create_report():
    try:
        new_inc = Incident(
            incident_type=request.form.get('type'),
            description=request.form.get('description'),
            latitude=float(request.form.get('lat')),
            longitude=float(request.form.get('lng')),
            user_id=current_user.id
        )
        db.session.add(new_inc)
        db.session.commit()
        return jsonify({"status": "success"})
    except:
        return jsonify({"status": "error"}), 400

@app.route('/api/incidents', methods=['GET'])
@login_required
def get_incidents():
    incidents = Incident.query.all()
    return jsonify([{
        "id": i.id, "type": i.incident_type, "description": i.description,
        "lat": i.latitude, "lng": i.longitude, "status": i.status,
        "date": i.created_at.strftime("%Y-%m-%d %H:%M")
    } for i in incidents])

@app.route('/api/register', methods=['POST'])
def register():
    data = request.form
    hashed = generate_password_hash(data.get('password'))
    new_user = User(username=data.get('username'), password=hashed, role=data.get('role'))
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"status": "success"})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.form
    user = User.query.filter_by(username=data.get('username')).first()
    if user and check_password_hash(user.password, data.get('password')):
        login_user(user)
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 401

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login_page'))

@app.route('/reset-db')
def reset_db():
    db.drop_all()
    db.create_all()
    for n in ['Theft', 'Vandalism', 'Assault']:
        db.session.add(Category(name=n))
    db.session.commit()
    return "Database Reset!"

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
