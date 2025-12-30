from flask import Flask, request, jsonify
import psycopg2
import os

app = Flask(__name__)

# Load connection string from environment variable
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    """Create a new database connection using psycopg2."""
    return psycopg2.connect(DATABASE_URL)

@app.route("/")
def home():
    return "Crime Reporting System backend is running!"

@app.route("/testdb")
def testdb():
    """Check if the database connection works."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT NOW();")
        result = cur.fetchone()
        cur.close()
        conn.close()
        return jsonify({"status": "connected", "time": str(result[0])})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/report", methods=["POST"])
def report_incident():
    """Insert a new incident report into the database."""
    data = request.json
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO incidents (type, description, latitude, longitude, image_url, classification, confidence)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (
            data["type"],
            data["description"],
            data["latitude"],
            data["longitude"],
            data.get("image_url", None),
            data.get("classification", None),
            data.get("confidence", None)
        ))
        incident_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "success", "incident_id": incident_id})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/heatmap", methods=["GET"])
def heatmap_data():
    """Fetch all incidents for heatmap visualization."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT latitude, longitude, 1.0 FROM incidents;")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == "__main__":
    # For local testing only; Render uses Gunicorn
    app.run(host="0.0.0.0", port=5000, debug=True)
