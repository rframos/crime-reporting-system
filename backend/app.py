import os
import datetime
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy

# 1. INITIALIZE FLASK
app = Flask(__name__, 
            template_folder='../frontend', 
            static_folder='../frontend')

# 2. DATABASE CONFIGURATION
uri = os.environ.get('DATABASE_URL')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri or 'sqlite:///local.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 3. DATABASE MODEL
class Incident(db.Model):
    __tablename__ = 'incidents'
    id = db.Column(db.Integer, primary_key=True)
    incident_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# 4. ROUTES
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/report', methods=['POST'])
def create_report():
    try:
        # Get data from the form
        description = request.form.get('description')
        lat = float(request.form.get('lat'))
        lng = float(request.form.get('lng'))
        manual_type = request.form.get('type')
        
        # --- MOCK CNN LOGIC ---
        # Instead of running a real model, we just pretend for now
        print("Testing Connection: Received image and data...")
        detected_type = f"Mock_{manual_type}" # Just to show it processed
        
        # Save to Database
        new_incident = Incident(
            incident_type=detected_type,
            description=description,
            latitude=lat,
            longitude=lng
        )
        db.session.add(new_incident)
        db.session.commit()

        return jsonify({
            "status": "success", 
            "message": "Connection working! Database saved.",
            "detected_type": detected_type
        }), 201

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/incidents', methods=['GET'])
def get_incidents():
    incidents = Incident.query.all()
    return jsonify([{
        "lat": i.latitude, "lng": i.longitude, 
        "type": i.incident_type, "status": i.status
    } for i in incidents])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
