import os
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import tensorflow as tf
import numpy as np
from PIL import Image
import datetime

app = Flask(__name__)

# --- DATABASE FIX FOR RENDER ---
uri = os.environ.get('DATABASE_URL')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri or 'sqlite:///local.db' # Defaults to local sqlite if no DB found
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'

db = SQLAlchemy(app)

# --- DATABASE MODEL ---
class Incident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    incident_type = db.Column(db.String(50))
    description = db.Column(db.Text)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# --- CNN MODEL LOADING ---
# Ensure your model is at 'model/cnn_model.h5' in your GitHub repo
MODEL_PATH = os.path.join('model', 'cnn_model.h5')
cnn_model = None
if os.path.exists(MODEL_PATH):
    cnn_model = tf.keras.models.load_model(MODEL_PATH)

@app.route('/')
def index():
    return render_template('index.html')

# API to provide data for the Leaflet Heatmap
@app.route('/api/incidents')
def get_incidents():
    incidents = Incident.query.all()
    return jsonify([{
        "lat": i.latitude, 
        "lng": i.longitude, 
        "type": i.incident_type
    } for i in incidents])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
