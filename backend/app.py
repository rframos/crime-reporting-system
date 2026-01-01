import os
import datetime
import numpy as np
import tensorflow as tf
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from PIL import Image

# 1. INITIALIZE FLASK
# We point to the parent directory for templates and static folders
app = Flask(__name__, 
            template_folder='../templates', 
            static_folder='../static')

# 2. DATABASE CONFIGURATION
uri = os.environ.get('DATABASE_URL')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri or 'sqlite:///local.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('..', 'static', 'uploads')

db = SQLAlchemy(app)

# 3. DATABASE MODEL
class Incident(db.Model):
    __tablename__ = 'incidents'
    id = db.Column(db.Integer, primary_key=True)
    incident_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    image_filename = db.Column(db.String(200))
    status = db.Column(db.String(20), default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# 4. CNN MODEL LOADING
# Paths are relative to the 'backend' folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, '..', 'model', 'cnn_model.h5')

# Define your classification labels (update these to match your training)
CLASSES = ['Theft', 'Vandalism', 'Assault', 'Accident', 'Fire']

cnn_model = None
if os.path.exists(MODEL_PATH):
    try:
        cnn_model = tf.keras.models.load_model(MODEL_PATH)
        print("CNN Model loaded successfully.")
    except Exception as e:
        print(f"Error loading model: {e}")

# 5. ROUTES
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/report', methods=['POST'])
def create_report():
    try:
        # Get basic form data
        description = request.form.get('description')
        lat = float(request.form.get('lat'))
        lng = float(request.form.get('lng'))
        manual_type = request.form.get('type') # Fallback type
        
        # Handle Image and CNN Classification
        file = request.files.get('image')
        final_type = manual_type
        saved_filename = None

        if file:
            filename = secure_filename(file.filename)
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(upload_path)
            saved_filename = filename

            # CNN Inference Logic
            if cnn_model:
                img = Image.open(upload_path).convert('RGB').resize((224, 224))
                img_array = np.array(img) / 255.0
                img_array = np.expand_dims(img_array, axis=0)
                
                prediction = cnn_model.predict(img_array)
                final_type = CLASSES[np.argmax(prediction)]

        # Save to Database
        new_incident = Incident(
            incident_type=final_type,
            description=description,
            latitude=lat,
            longitude=lng,
            image_filename=saved_filename
        )
        db.session.add(new_incident)
        db.session.commit()

        return jsonify({
            "status": "success", 
            "message": "Report submitted successfully",
            "detected_type": final_type
        }), 201

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/incidents', methods=['GET'])
def get_incidents():
    # Returns all incidents for the Heatmap visualization
    incidents = Incident.query.all()
    data = [{
        "lat": i.latitude,
        "lng": i.longitude,
        "type": i.incident_type,
        "status": i.status
    } for i in incidents]
    return jsonify(data)

# 6. INITIALIZE DB & START APP
if __name__ == '__main__':
    # Ensure upload directory exists
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
        
    with app.app_context():
        db.create_all()
    app.run(debug=True)
