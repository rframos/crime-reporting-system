import os
import datetime
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy

# Identify the root directory (one level up from /backend)
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

app = Flask(__name__, 
            root_path=base_dir,
            template_folder='templates',
            static_folder='static')

# DATABASE CONFIGURATION
uri = os.environ.get('DATABASE_URL')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri or 'sqlite:///local.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# INCIDENT MODEL
class Incident(db.Model):
    __tablename__ = 'incidents'
    id = db.Column(db.Integer, primary_key=True)
    incident_type = db.Column(db.String(50))
    description = db.Column(db.Text)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# ROUTES
@app.route('/')
def index():
    return render_template('index.html')

# API: Report an Incident (POST)
@app.route('/api/report', methods=['POST'])
def create_report():
    try:
        data = request.form if request.form else request.get_json()
        
        # Log data to Render Console
        print(f"--- Incoming Report ---")
        print(f"Type: {data.get('type')}")

        if not all([data.get('type'), data.get('lat'), data.get('lng')]):
            return jsonify({"status": "error", "message": "Missing required fields"}), 400

        new_incident = Incident(
            incident_type=data.get('type'),
            description=data.get('description', ''),
            latitude=float(data.get('lat')),
            longitude=float(data.get('lng'))
        )
        
        db.session.add(new_incident)
        db.session.commit()
        return jsonify({"status": "success", "message": "Reported!"}), 201
    
    except Exception as e:
        print(f"DB Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

# API: Get All Incidents (GET) - NEW!
@app.route('/api/incidents', methods=['GET'])
def get_incidents():
    try:
        incidents = Incident.query.all()
        data = []
        for i in incidents:
            data.append({
                "id": i.id,
                "type": i.incident_type,
                "description": i.description,
                "lat": i.latitude,
                "lng": i.longitude,
                "date": i.created_at.strftime("%Y-%m-%d %H:%M")
            })
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# TEMPORARY DATABASE RESET ROUTE
@app.route('/reset-db')
def reset_db():
    try:
        db.drop_all()
        db.create_all()
        return "Database has been reset! The 'incidents' table is now fresh."
    except Exception as e:
        return f"Error resetting database: {str(e)}"

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
