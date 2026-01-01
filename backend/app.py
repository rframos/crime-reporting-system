import os
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import tensorflow as tf
import numpy as np
from PIL import Image
import datetime

app = Flask(__name__)

# --- CONFIGURATION ---
# Replace with your Render Environment Variable later
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://username:password@localhost/crime_db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit

db = SQLAlchemy(app)

# --- DATABASE MODEL ---
class Incident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    incident_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    image_path = db.Column(db.String(200))
    status = db.Column(db.String(20), default='Pending') # Pending, Verified, Escalated
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# --- CNN MODEL LOADING ---
# Load model once when server starts to save memory/time
MODEL_PATH = 'model/cnn_model.h5'
if os.path.exists(MODEL_PATH):
    cnn_model = tf.keras.models.load_model(MODEL_PATH)
    # Define your classes based on how you trained your model
    CLASSES = ['Theft', 'Vandalism', 'Assault', 'Accident'] 
else:
    cnn_model = None
    print("Warning: CNN model file not found.")

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/report', methods=['POST'])
def submit_report():
    try:
        # 1. Get Form Data
        incident_type = request.form.get('type')
        description = request.form.get('description')
        lat = float(request.form.get('lat'))
        lng = float(request.form.get('lng'))
        
        # 2. Handle Image & CNN Classification
        file = request.files.get('image')
        ai_suggestion = "Unknown"
        
        if file and cnn_model:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # CNN Inference
            img = Image.open(filepath).resize((224, 224)) # Adjust to your model's input size
            img_array = np.array(img) / 255.0
            img_array = np.expand_dims(img_array, axis=0)
            
            predictions = cnn_model.predict(img_array)
            ai_suggestion = CLASSES[np.argmax(predictions)]

        # 3. Save to PostgreSQL
        new_report = Incident(
            incident_type=ai_suggestion if ai_suggestion != "Unknown" else incident_type,
            description=description,
            latitude=lat,
            longitude=lng,
            image_path=filepath if file else None
        )
        db.session.add(new_report)
        db.session.commit()

        return jsonify({"status": "success", "message": "Report submitted", "ai_classification": ai_suggestion})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/incidents')
def get_incidents():
    # This route will feed the Heatmap.js on your frontend
    incidents = Incident.query.all()
    output = []
    for i in incidents:
        output.append({
            "lat": i.latitude,
            "lng": i.longitude,
            "type": i.incident_type,
            "status": i.status
        })
    return jsonify(output)

if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Creates tables if they don't exist
    app.run(debug=True)
