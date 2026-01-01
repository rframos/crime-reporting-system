import os
import datetime
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy

# INITIALIZE FLASK (Standard Folders)
app = Flask(__name__, 
            template_folder='../templates', 
            static_folder='../static')

# DATABASE CONFIG
uri = os.environ.get('DATABASE_URL')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri or 'sqlite:///local.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Incident(db.Model):
    __tablename__ = 'incidents'
    id = db.Column(db.Integer, primary_key=True)
    incident_type = db.Column(db.String(50))
    description = db.Column(db.Text)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/report', methods=['POST'])
def create_report():
    try:
        data = request.form
        new_incident = Incident(
            incident_type=f"Test_{data.get('type')}",
            description=data.get('description'),
            latitude=float(data.get('lat')),
            longitude=float(data.get('lng'))
        )
        db.session.add(new_incident)
        db.session.commit()
        return jsonify({"status": "success", "detected_type": new_incident.incident_type}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/incidents', methods=['GET'])
def get_incidents():
    incidents = Incident.query.all()
    return jsonify([{"lat": i.latitude, "lng": i.longitude, "count": 1} for i in incidents])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
