import sys
import threading
import time
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash, jsonify
import sqlite3, os, json, subprocess, signal

DB_PATH = "drivers.db"
ACTIVE_FILE = "current_driver.json"
RECORDS_DIR = "records"

app = Flask(__name__)
app.secret_key = "change-me"  # set a secure key

os.makedirs(RECORDS_DIR, exist_ok=True)

process = None  # To store main.py process

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS drivers(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT,
      license_number TEXT UNIQUE,
      email TEXT
    );""")
    c.execute("""CREATE TABLE IF NOT EXISTS events(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      driver_id INTEGER,
      event_type TEXT,
      ts TEXT,
      image_path TEXT
    );""")
    conn.commit()
    conn.close()

def set_active_driver(driver_id):
    with open(ACTIVE_FILE, "w", encoding="utf-8") as f:
        json.dump({"driver_id": driver_id}, f)

def clear_active_driver():
    if os.path.exists(ACTIVE_FILE):
        os.remove(ACTIVE_FILE)

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
            c.execute("INSERT INTO drivers(name, license_number, email) VALUES (?,?,?)",
                      (name, license_number, email))
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
            print(f"Login success: Driver ID {row['id']}, Name {row['name']}")
            return redirect(url_for("dashboard"))

        flash("Driver not found. Please register.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    global process
    if process:
        try:
            os.kill(process.pid, signal.SIGTERM)
            print("Stopped main.py on logout.")
        except Exception as e:
            print(f"[ERROR] Failed to stop main.py on logout: {e}")
        process = None
    session.clear()
    clear_active_driver()
    return redirect(url_for("login"))

# ✅ Updated safety score function (time-weighted)
def safety_percent_for(driver_id):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT ts FROM events WHERE driver_id=?", (driver_id,))
    timestamps = [row["ts"] for row in c.fetchall()]
    conn.close()

    now = time.time()
    score_raw = 0.0
    for ts in timestamps:
        try:
            event_time = time.mktime(time.strptime(ts, "%Y-%m-%d %H:%M:%S"))
            days_ago = (now - event_time) / (60 * 60 * 24)
            weight = max(0.0, 1.0 - days_ago / 30.0)  # decay over 30 days
            score_raw += weight
        except Exception as e:
            print(f"[WARN] Failed to parse timestamp: {ts} — {e}")
            continue

    max_score = 30.0  # max weighted alerts before score hits 0%
    score = max(0.0, 100.0 * (1.0 - score_raw / max_score))
    return round(score, 1), len(timestamps), round(score_raw, 1)

@app.route("/dashboard")
def dashboard():
    if "driver_id" not in session:
        print("No active session found — redirecting to login")
        return redirect(url_for("login"))

    driver_id = session["driver_id"]
    driver_name = session.get("driver_name", "Driver")
    print(f"Rendering dashboard for Driver ID {driver_id}, Name {driver_name}")

    conn = db()
    c = conn.cursor()
    c.execute("SELECT * FROM events WHERE driver_id=? ORDER BY id DESC LIMIT 50", (driver_id,))
    events = c.fetchall()
    safety, total_events, weighted_events = safety_percent_for(driver_id)
    conn.close()

    return render_template(
        "dashboard.html",
        name=driver_name,
        safety=safety,
        total_events=total_events,
        weighted_events=weighted_events,
        events=events
    )

@app.route("/passenger", methods=["GET", "POST"])
def passenger():
    data = None
    error = None
    conn = db()
    c = conn.cursor()
    c.execute("SELECT id, name FROM drivers")
    all_drivers = c.fetchall()
    if request.method == "POST":
        driver_id = request.form.get("driver_id", "").strip()
        if driver_id.isdigit():
            driver_id = int(driver_id)
            c.execute("SELECT * FROM drivers WHERE id=?", (driver_id,))
            d = c.fetchone()
            if d:
                safety, total_events, weighted_events = safety_percent_for(driver_id)
                data = {"driver": d, "safety": safety, "total": total_events, "avg": weighted_events}
                c.execute("SELECT * FROM events WHERE driver_id=? ORDER BY id DESC LIMIT 5", (driver_id,))
                data["events"] = c.fetchall()
            else:
                error = "Driver ID not found."
        else:
            error = "Enter a numeric Driver ID."
    conn.close()
    return render_template("passenger.html", data=data, error=error, all_drivers=all_drivers)

@app.route("/records/<path:filename>")
def records_static(filename):
    return send_from_directory(RECORDS_DIR, filename)

# --- Drowsiness detection start/stop routes ---
def stream_output(pipe):
    for line in iter(pipe.readline, b''):
        print("[main.py]", line.decode().strip())

@app.route('/start')
def start_detection():
    global process
    if process is not None:
        if process.poll() is None:
            return jsonify({'status': 'already running'})
        else:
            print("Previous process was dead. Restarting...")
            process = None

    try:
        print("Starting main.py...")
        process = subprocess.Popen(
            [sys.executable, 'main.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        threading.Thread(target=stream_output, args=(process.stdout,), daemon=True).start()
        threading.Thread(target=stream_output, args=(process.stderr,), daemon=True).start()
        return jsonify({'status': 'started'})
    except Exception as e:
        print(f"[ERROR] Failed to start main.py: {e}")
        return jsonify({'status': f'error: {e}'})

@app.route('/stop')
def stop_detection():
    global process
    if process is not None:
        try:
            if process.poll() is None:
                os.kill(process.pid, signal.SIGTERM)
                print("Stopped main.py.")
            else:
                print("Process already exited.")
            process = None
            return jsonify({'status': 'stopped'})
        except Exception as e:
            print(f"[ERROR] Failed to stop main.py: {e}")
            return jsonify({'status': f'error: {e}'})
    else:
        return jsonify({'status': 'not running'})

if __name__ == "__main__":
    init_db()
    app.run(debug=True)