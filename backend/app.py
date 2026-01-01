import os
import datetime
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

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
app.config['SECRET_KEY'] = 'your_secret_key_here' # Required for sessions

db = SQLAlchemy(app)
login_manager = LoginManager(app)

# USER MODEL (For Phase 1: Roles)
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='Resident') # Admin, Official, Resident, Police

# UPDATED INCIDENT MODEL (Added image field for Phase 2)
class Incident(db.Model):
    __tablename__ = 'incidents'
    id = db.Column(db.Integer, primary_key=True)
    incident_type = db.Column(db.String(50))
    description = db.Column(db.Text)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    image_path = db.Column(db.String(255), nullable=True) # Path to uploaded file
    status = db.Column(db.String(20), default='Pending') # Pending, Responded, Closed
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ROUTES
@app.route('/')
def index():
    return render_template('index.html')

# API: Fetch all for Heatmap/Markers
@app.route('/api/incidents', methods=['GET'])
def get_incidents():
    incidents = Incident.query.all()
    return jsonify([{
        "id": i.id, "type": i.incident_type, "description": i.description,
        "lat": i.latitude, "lng": i.longitude, "status": i.status,
        "date": i.created_at.strftime("%Y-%m-%d %H:%M")
    } for i in incidents])

# API: Report Incident
@app.route('/api/report', methods=['POST'])
def create_report():
    try:
        data = request.form
        new_incident = Incident(
            incident_type=data.get('type'),
            description=data.get('description', ''),
            latitude=float(data.get('lat')),
            longitude=float(data.get('lng'))
        )
        db.session.add(new_incident)
        db.session.commit()
        return jsonify({"status": "success"}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

# TEMPORARY: Reset DB to apply new columns
@app.route('/reset-db')
def reset_db():
    db.drop_all()
    db.create_all()
    return "Database updated with User roles and Incident status fields!"

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
