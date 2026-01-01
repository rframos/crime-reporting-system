import os
import datetime
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy

# 1. INITIALIZE FLASK
# Points to your /frontend folder for HTML/CSS/JS
app = Flask(__name__, 
            template_folder='../frontend', 
            static_folder='../frontend')

# 2. DATABASE CONFIGURATION (Render PostgreSQL Fix)
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
    # Looks for /frontend/index.html
    return render_template('index.html')

@app.route('/api/report', methods=['POST'])
def create_report():
    try:
        # Get data from the frontend form
        description = request.form.get('description')
        lat = float(request.form.get('lat'))
        lng = float(request.form.get('lng'))
        manual_type = request.form.get('type')
        
        # MOCK LOGIC for Connection Testing
        # This bypasses the CNN for now to ensure DB connectivity works
        detected_type = f"Test_{manual_type}"
        
        # Save to PostgreSQL
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
            "message": "Connection working! Data saved to PostgreSQL.",
            "detected_type": detected_type
        }), 201

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/incidents', methods=['GET'])
def get_incidents():
    # Returns all incidents for the Heatmap.js visualization
    incidents = Incident.query.all()
    return jsonify([{
        "lat": i.latitude, 
        "lng": i.longitude, 
        "type": i.incident_type, 
        "status": i.status
    } for i in incidents])

# 5. INITIALIZE DATABASE
if __name__ == '__main__':
    with app.app_context():
        # This creates the 'incidents' table in PostgreSQL automatically
        db.create_all()
    app.run(debug=True)
