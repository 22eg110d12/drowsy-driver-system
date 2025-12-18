import time
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash, jsonify
import sqlite3, os, json

# ---------------- CONFIG ---------------- #

DB_PATH = "/tmp/drivers.db"   # ✅ REQUIRED FOR RENDER
ACTIVE_FILE = "/tmp/current_driver.json"
RECORDS_DIR = "/tmp/records"

app = Flask(__name__)
app.secret_key = "change-me"

os.makedirs(RECORDS_DIR, exist_ok=True)

# ---------------- DATABASE ---------------- #

def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS drivers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            license_number TEXT UNIQUE,
            email TEXT
        );
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_id INTEGER,
            event_type TEXT,
            ts TEXT,
            image_path TEXT
        );
    """)
    conn.commit()
    conn.close()

# ✅ SAFE INITIALIZATION FOR GUNICORN
init_db()

# ---------------- SESSION HELPERS ---------------- #

def set_active_driver(driver_id):
    with open(ACTIVE_FILE, "w", encoding="utf-8") as f:
        json.dump({"driver_id": driver_id}, f)

def clear_active_driver():
    if os.path.exists(ACTIVE_FILE):
        os.remove(ACTIVE_FILE)

# ---------------- ROUTES ---------------- #

@app.route("/")
def home():
    if "driver_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        license_number = request.form["license_number"].strip()
        email = request.form["email"].strip()

        conn = db()
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO drivers(name, license_number, email) VALUES (?,?,?)",
                (name, license_number, email)
            )
            conn.commit()
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("License number already exists.", "error")
        finally:
            conn.close()

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        license_number = request.form["license_number"].strip()
        conn = db()
        c = conn.cursor()
        c.execute("SELECT * FROM drivers WHERE license_number = ?", (license_number,))
        row = c.fetchone()
        conn.close()

        if row:
            session["driver_id"] = row["id"]
            session["driver_name"] = row["name"]
            set_active_driver(row["id"])
            return redirect(url_for("dashboard"))

        flash("Driver not found. Please register.", "error")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    clear_active_driver()
    return redirect(url_for("login"))

# ---------------- DASHBOARD ---------------- #

@app.route("/dashboard")
def dashboard():
    if "driver_id" not in session:
        return redirect(url_for("login"))

    driver_id = session["driver_id"]
    driver_name = session.get("driver_name", "Driver")

    conn = db()
    c = conn.cursor()
    c.execute("SELECT * FROM events WHERE driver_id=? ORDER BY id DESC LIMIT 50", (driver_id,))
    events = c.fetchall()
    conn.close()

    return render_template("dashboard.html", name=driver_name, events=events)

# ---------------- API ---------------- #

@app.route("/api/event", methods=["POST"])
def api_event():
    data = request.json
    conn = db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO events(driver_id, event_type, ts, image_path) VALUES (?,?,?,?)",
        (data["driver_id"], data["event_type"], data["ts"], data.get("image_path"))
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

# ---------------- LOCAL RUN ---------------- #

if __name__ == "__main__":
    app.run(debug=True)
