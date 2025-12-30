from flask import Flask, request, jsonify
import psycopg2

app = Flask(__name__)

# Directly hard-coded connection string
DATABASE_URL = "postgresql://crime_reporting_db_user:GqW6mueutFfUporhXErLZNPaItYZKATy@dpg-d5a4ojeuk2gs73ei1an0-a/crime_reporting_db"

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

@app.route("/report", methods=["POST"])
def report_incident():
    data = request.json
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

@app.route("/heatmap", methods=["GET"])
def heatmap_data():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT latitude, longitude, 1.0 FROM incidents;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(rows)
