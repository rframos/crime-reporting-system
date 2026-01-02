import os
import datetime
import shutil
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# --- CONFIG ---
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
app = Flask(__name__, root_path=base_dir, template_folder='templates', static_folder='static')

app.config['SECRET_KEY'] = 'sjdm_safe_city_2026_prod'
# Use a specific path for the DB to avoid permission issues
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'local.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['TRAIN_FOLDER'] = os.path.join(base_dir, 'static/training_data')

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login_page'

# --- MODELS (Ensure they match previous versions) ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='Resident')

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    severity = db.Column(db.String(20), default='Low')

class Incident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    incident_type = db.Column(db.String(50))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    status = db.Column(db.String(20), default='Pending')
    severity = db.Column(db.String(20), default='Low')
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))

# --- THE FIX: ROBUST RESET ROUTE ---
@app.route('/reset-db')
def reset_db():
    try:
        # 1. Clear Database
        db.reflect()
        db.drop_all()
        db.create_all()
        
        # 2. Re-populate Essentials
        default_cats = [
            Category(name="Theft", severity="Medium"),
            Category(name="Assault", severity="High"),
            Category(name="Vandalism", severity="Low")
        ]
        db.session.add_all(default_cats)
        db.session.commit()
        
        # 3. Fix Training Folders
        if os.path.exists(app.config['TRAIN_FOLDER']):
            shutil.rmtree(app.config['TRAIN_FOLDER'])
        os.makedirs(app.config['TRAIN_FOLDER'], exist_ok=True)
        for cat in default_cats:
            os.makedirs(os.path.join(app.config['TRAIN_FOLDER'], cat.name), exist_ok=True)
            
        return "SUCCESS: Database and folders reset. <a href='/register'>Go Register Admin</a>"
    except Exception as e:
        return f"ERROR: {str(e)}", 500

@app.route('/')
@login_required
def index():
    return render_template('index.html', categories=Category.query.all())

# (Other routes like /heatmap, /reports, /contacts go here...)

if __name__ == '__main__':
    # Render requires host 0.0.0.0 and dynamic port
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
