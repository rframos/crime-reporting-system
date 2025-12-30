from flask import Flask, jsonify
import psycopg2

app = Flask(__name__)

def get_db_connection():
    return psycopg2.connect(
        host="your-db-host",
        database="your-db-name",
        user="your-db-user",
        password="your-db-password"
    )

@app.route("/heatmap", methods=["GET"])
def heatmap_data():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT latitude, longitude, 1.0 FROM incidents;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(rows)
