import os

from flask import Flask, render_template, request, redirect, session, send_from_directory, jsonify, flash
import sqlite3
import math
import bcrypt
from dotenv import load_dotenv
load_dotenv()  # loads .env file if present
from werkzeug.utils import secure_filename
from ai.classifier import predict_complaint
from datetime import datetime, timedelta
from models.department_mapping import CATEGORY_MAPPING
from ai.duplicate_detector import DuplicateComplaintDetector
from ai.cv_comparator import check_image_consistency, calculate_resolution_score
from utils.priority_queue import PriorityQueueManager
import csv
import io
from flask_mail import Mail, Message as MailMessage
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from db import get_db, q
from storage import save_image, get_image_url
priority_queue = PriorityQueueManager()
# ------------------------------------
# AI Similarity Engine
# ------------------------------------

duplicate_detector = DuplicateComplaintDetector()



app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "secret123")

# ── Flask-Mail config (uses env vars — set in .env for production) ──
app.config['MAIL_SERVER']   = os.environ.get('MAIL_SERVER',   'smtp.gmail.com')
app.config['MAIL_PORT']     = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS']  = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME', 'noreply@scs.local')
mail = Mail(app)

MAIL_ENABLED = bool(os.environ.get('MAIL_USERNAME', ''))

# ── Rate Limiter ──
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://"
)

# ── SLA deadlines per category (days) ──
SLA_DAYS = {
    "Road Damage":       7,
    "Water Supply":      3,
    "Electricity":       2,
    "Street Light":      3,
    "Garbage":           2,
    "Drainage":          4,
    "Animal":            1,
    "Traffic":           3,
    "Public Property":   5,
    "Others":            7,
}

# PostgreSQL column migration helper (adds missing columns safely)
def _pg_migrate(cur, conn):
    """Add any new columns to existing Supabase tables without breaking anything."""
    migrations = [
        "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS feedback            TEXT",
        "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS rating              INTEGER",
        "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS rejection_reason    TEXT",
        "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS resolution_score    REAL DEFAULT 0",
        "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS verification_status TEXT DEFAULT 'Pending'",
        "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS needs_verification  INTEGER DEFAULT 0",
        "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS updated_at          TEXT",
        "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS sla_deadline        TEXT",
        "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS escalated           INTEGER DEFAULT 0",
        "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS assigned_to         TEXT",
        "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS officer_remark      TEXT",
        "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS is_emergency        INTEGER DEFAULT 0",
        "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS upvotes             INTEGER DEFAULT 0",
        "ALTER TABLE users      ADD COLUMN IF NOT EXISTS email               TEXT",
        "ALTER TABLE users      ADD COLUMN IF NOT EXISTS phone               TEXT",
    ]
    for sql in migrations:
        try:
            cur.execute(sql)
        except Exception:
            pass
    try:
        conn.commit()
    except Exception:
        pass


# Database Creation
def create_db():
    from db import USE_POSTGRES
    conn = get_db()
    cur = conn.cursor()

    # PostgreSQL (Supabase) — tables already created by migrate_supabase.py
    # Just run ALTER TABLE migrations to add any missing columns, then return
    if USE_POSTGRES:
        _pg_migrate(cur, conn)
        conn.close()
        return

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
       username TEXT PRIMARY KEY,
       password TEXT,
       role TEXT DEFAULT 'Citizen',
       department TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS complaints(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT,
      category TEXT,
      description TEXT,
      status TEXT,
      address TEXT,
      image_path TEXT,
      latitude REAL,
      longitude REAL,
      priority TEXT,

      department TEXT,

      officer_remark TEXT,

      resolution_image TEXT,

      created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS notifications(

      id INTEGER PRIMARY KEY AUTOINCREMENT,

      username TEXT,

      message TEXT,

      is_read INTEGER DEFAULT 0,

      created_at TEXT

    )
    """)

# 👇 Then your ALTER TABLE blocks continue here

    # --- migrate: add columns if they don't exist ---
    for col_sql in [
        "ALTER TABLE complaints ADD COLUMN feedback            TEXT",
        "ALTER TABLE complaints ADD COLUMN rating              INTEGER",
        "ALTER TABLE complaints ADD COLUMN rejection_reason    TEXT",
        "ALTER TABLE complaints ADD COLUMN resolution_score    REAL DEFAULT 0",
        "ALTER TABLE complaints ADD COLUMN verification_status TEXT DEFAULT 'Pending'",
        "ALTER TABLE complaints ADD COLUMN needs_verification  INTEGER DEFAULT 0",
        "ALTER TABLE complaints ADD COLUMN updated_at          TEXT",
        "ALTER TABLE complaints ADD COLUMN sla_deadline        TEXT",
        "ALTER TABLE complaints ADD COLUMN escalated           INTEGER DEFAULT 0",
        "ALTER TABLE complaints ADD COLUMN assigned_to         TEXT",
        "ALTER TABLE complaints ADD COLUMN officer_remark      TEXT",
        "ALTER TABLE complaints ADD COLUMN is_emergency        INTEGER DEFAULT 0",
        "ALTER TABLE complaints ADD COLUMN upvotes             INTEGER DEFAULT 0",
        "ALTER TABLE users      ADD COLUMN email               TEXT",
        "ALTER TABLE users      ADD COLUMN phone               TEXT",
    ]:
        try:
            cur.execute(col_sql)
        except:
            pass

    # Complaint timeline table (status history)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS complaint_timeline(
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint_id INTEGER,
        actor       TEXT,
        action      TEXT,
        note        TEXT,
        timestamp   TEXT
    )
    """)

    # Announcements table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS announcements(
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT NOT NULL,
        body        TEXT NOT NULL,
        created_by  TEXT DEFAULT 'admin',
        created_at  TEXT,
        expires_at  TEXT,
        is_active   INTEGER DEFAULT 1
    )
    """)

    # Complaint votes table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS complaint_votes(
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint_id INTEGER,
        username     TEXT,
        UNIQUE(complaint_id, username)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS community_settings(
        id INTEGER PRIMARY KEY,
        community_name TEXT,
        latitude REAL,
        longitude REAL,
        radius REAL
    )
    """)

    cur.execute("""
    INSERT OR IGNORE INTO community_settings
    (id, community_name, latitude, longitude, radius)
    VALUES
    (1, 'Rasapudipalem', 17.6868, 83.2185, 5)
    """)

    _admin_pw = bcrypt.hashpw(b'admin123', bcrypt.gensalt()).decode()
    cur.execute("""
    INSERT OR IGNORE INTO users
    (username,password,role,department)
    VALUES (?,?,?,?)
    """, ('admin', _admin_pw, 'Admin', None))
    
    # ==========================
# Default Department Officers
# ==========================

    officers = [

        ("roads", "roads123", "Officer", "Roads & Infrastructure"),

        ("water", "water123", "Officer", "Water Supply"),

        ("electricity", "electricity123", "Officer", "Electricity & Street Lighting"),

        ("sanitation", "sanitation123", "Officer", "Sanitation & Waste Management"),

        ("drainage", "drainage123", "Officer", "Drainage & Sewage"),

        ("parks", "parks123", "Officer", "Parks & Green Spaces"),

        ("property", "property123", "Officer", "Public Property Maintenance"),

        ("animal", "animal123", "Officer", "Animal Control"),

        ("traffic", "traffic123", "Officer", "Traffic & Public Safety"),

         ("others", "others123", "Officer", "Others")

    ]

    for uname, pw, role, dept in officers:
        hashed = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
        cur.execute("""
        INSERT OR IGNORE INTO users
        (username,password,role,department)
        VALUES (?,?,?,?)
        """, (uname, hashed, role, dept))

    conn.commit()
    conn.close()

def calculate_distance(lat1, lon1, lat2, lon2):

    lat1 = float(lat1)
    lon1 = float(lon1)
    lat2 = float(lat2)
    lon2 = float(lon2)

    return math.sqrt(
        (lat1 - lat2)**2 +
        (lon1 - lon2)**2
    ) * 111
   
# debug route removed

# ============================================================
# Helper — Add timeline entry
# ============================================================
def add_timeline(complaint_id, actor, action, note=""):
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO complaint_timeline
        (complaint_id, actor, action, note, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (complaint_id, actor, action, note,
          datetime.now().strftime("%d-%m-%Y %H:%M")))
    conn.commit()
    conn.close()


# ============================================================
# Helper — Send email notification (graceful fail if not configured)
# ============================================================
def send_email_notification(to_username, subject, body_html):
    """
    Send an email to a user. Looks up their email from the users table.
    Silently skips if MAIL_ENABLED is False or user has no email.
    """
    if not MAIL_ENABLED:
        return  # Email not configured — skip silently

    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("SELECT email FROM users WHERE username=?", (to_username,))
        row = cur.fetchone()
        conn.close()

        if not row or not row[0]:
            return  # No email on file

        msg = MailMessage(
            subject=f"[SCS] {subject}",
            recipients=[row[0]],
            html=body_html
        )
        mail.send(msg)
    except Exception:
        pass  # Never crash the app because of email failure



# ============================================================
# Helper — Calculate SLA deadline
# ============================================================
def get_sla_deadline(category):
    days = SLA_DAYS.get(category, 7)
    from datetime import timedelta
    deadline = datetime.now() + timedelta(days=days)
    return deadline.strftime("%d-%m-%Y")


# ============================================================
# Helper — GPS-based complaint count (radius in km)
# ============================================================
def count_nearby_complaints(lat, lon, category, radius_km=0.2):
    """Count DISTINCT users who reported same category within radius_km."""
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        SELECT username, latitude, longitude
        FROM complaints
        WHERE category = ?
        AND latitude IS NOT NULL
        AND longitude IS NOT NULL
    """, (category,))
    rows = cur.fetchall()
    conn.close()

    nearby_users = set()
    for uname, r_lat, r_lon in rows:
        if r_lat and r_lon:
            d = calculate_distance(lat, lon, r_lat, r_lon)
            if d <= radius_km:
                nearby_users.add(uname)
    return len(nearby_users)


# ============================================================
# Helper — Check if same user is spamming same complaint
# ============================================================
def user_recent_duplicate(username, description, category, days=7):
    """Returns True if this user filed a very similar complaint recently."""
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        SELECT description FROM complaints
        WHERE username = ?
        AND category   = ?
        AND created_at >= date('now', ?)
    """, (username, category, f"-{days} days"))
    rows = cur.fetchall()
    conn.close()

    for (existing_desc,) in rows:
        result = duplicate_detector.check_duplicate(description, [existing_desc])
        if result and result.get("similarity", 0) >= 0.80:
            return True
    return False


# ============================================================
# Helper — Detect hotspot (3+ diff users in 200m, same cat)
# ============================================================
def is_hotspot(lat, lon, category, threshold=3):
    return count_nearby_complaints(lat, lon, category, radius_km=0.2) >= threshold


# ============================================================
# Auto-escalation — called on admin dashboard load
# ============================================================
def run_auto_escalation():
    """Escalate complaints pending 5+ days without action."""
    try:
        conn = get_db()
        cur  = conn.cursor()
        if USE_POSTGRES:
            cur.execute("""
                UPDATE complaints
                SET priority = CASE
                        WHEN priority = 'Low'    THEN 'Medium'
                        WHEN priority = 'Medium' THEN 'High'
                        WHEN priority = 'High'   THEN 'Critical'
                        ELSE priority
                    END,
                    escalated = 1
                WHERE status IN ('Pending', 'In Progress')
                AND (escalated = 0 OR escalated IS NULL)
                AND (NOW() - TO_TIMESTAMP(created_at, 'DD-MM-YYYY HH24:MI')) >= INTERVAL '5 days'
            """)
        else:
            cur.execute("""
                UPDATE complaints
                SET priority = CASE
                        WHEN priority = 'Low'    THEN 'Medium'
                        WHEN priority = 'Medium' THEN 'High'
                        WHEN priority = 'High'   THEN 'Critical'
                        ELSE priority
                    END,
                    escalated = 1
                WHERE status IN ('Pending', 'In Progress')
                AND (escalated = 0 OR escalated IS NULL)
                AND julianday('now') - julianday(
                    substr(created_at,7,4)||'-'||
                    substr(created_at,4,2)||'-'||
                    substr(created_at,1,2)
                ) >= 5
            """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[AutoEscalation Warning] {e}")


create_db()


# ============================
# Notification Helper
# ============================
# ============================
# Notification Helper
# ============================

def add_notification(username, message):

    conn = get_db()
    cur = conn.cursor()

    from datetime import datetime

    current_time = datetime.now().strftime("%d-%m-%Y %H:%M")

    cur.execute("""
        INSERT INTO notifications
        (username, message, created_at)
        VALUES (?, ?, ?)
    """, (username, message, current_time))

    conn.commit()
    conn.close()

# Home Page
@app.route('/')
def home():
    return render_template('home.html')

# Register
@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("60 per hour")
def register():

    if request.method == 'POST':

        username = request.form['username'].strip()
        raw_pw   = request.form['password'].strip()
        password = bcrypt.hashpw(raw_pw.encode(), bcrypt.gensalt()).decode()

        conn = get_db()
        cur = conn.cursor()

        # Check if username already exists case-insensitively
        cur.execute("SELECT username FROM users WHERE LOWER(username) = LOWER(?)", (username,))
        if cur.fetchone() is not None:
            conn.close()
            flash("Username already taken. Please choose a different one.", "error")
            return redirect('/register')

        try:
            cur.execute(
                """
               INSERT INTO users
               (username, password, role, department)
               VALUES (?, ?, ?, ?)
               """,
            (username, password, "Citizen", None))
            conn.commit()
        except Exception as e:
            conn.close()
            print(f"[Register Error] {e}")
            flash("Could not create account. Please try again.", "error")
            return redirect('/register')

        conn.close()

        flash("Account created successfully! Please log in.", "success")
        return redirect('/login')

    return render_template('register.html')

# Login
@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("60 per minute")
def login():

    if request.method == 'POST':

        username = request.form['username'].strip()
        password = request.form['password'].strip()

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT username, password, role, department
            FROM users
            WHERE LOWER(username)=LOWER(?)
        """, (username,))

        user = cur.fetchone()
        conn.close()

        if user is None:
            flash("Invalid username or password. Please try again.", "error")
            return redirect('/login')

        # Safely extract user fields (handles dict, DictRow, sqlite3.Row, and tuple)
        def _get_field(row, key, idx):
            try:
                return row[key]
            except (TypeError, KeyError, IndexError):
                try:
                    return row[idx]
                except (TypeError, KeyError, IndexError):
                    return None

        u_name = _get_field(user, 'username', 0)
        u_pass = _get_field(user, 'password', 1)
        u_role = _get_field(user, 'role', 2)
        u_dept = _get_field(user, 'department', 3)

        # Safe password check (handles both bcrypt hashes and plain text fallback)
        is_valid = False
        if u_pass:
            stored_pw = str(u_pass)
            if stored_pw.startswith("$2b$") or stored_pw.startswith("$2a$"):
                try:
                    is_valid = bcrypt.checkpw(password.encode('utf-8'), stored_pw.encode('utf-8'))
                except Exception:
                    is_valid = (password == stored_pw)
            else:
                is_valid = (password == stored_pw)

        if not is_valid:
            flash("Invalid username or password. Please try again.", "error")
            return redirect('/login')

        # -----------------------------
        # Save Session
        # -----------------------------

        session["username"] = u_name
        session["role"] = u_role
        session["department"] = u_dept

        # -----------------------------
        # Redirect
        # -----------------------------

        if u_role == "Admin":
            return redirect("/admin")

        elif u_role == "Officer":
            return redirect("/department_dashboard")

        else:
            return redirect("/user_dashboard")

    return render_template("login.html")

# User Dashboard

@app.route('/user_dashboard')
def user_dashboard():

    if 'username' not in session:
        return redirect('/login')

    username = session['username']

    conn = get_db()
    cur = conn.cursor()

    # ---------------------------------
    # Dashboard Statistics
    # ---------------------------------

    cur.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE username=?
    """, (username,))
    total = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE username=?
        AND status='Pending'
    """, (username,))
    pending = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE username=?
        AND status='In Progress'
    """, (username,))
    in_progress = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE username=?
        AND status='Resolved'
    """, (username,))
    resolved = cur.fetchone()[0]

    # ---------------------------------
    # Recent Notifications
    # ---------------------------------

    cur.execute("""
        SELECT
            message,
            created_at
        FROM notifications
        WHERE username=?
        ORDER BY id DESC
        LIMIT 5
    """, (username,))

    notifications = cur.fetchall()

    conn.close()

    return render_template(

        "user_dashboard.html",

        username=username,

        total=total,

        pending=pending,

        in_progress=in_progress,

        resolved=resolved,

        notifications=notifications

    )

# Logout
@app.route('/logout')
def logout():

    session.pop('username', None)

    return redirect('/')

@app.route('/help')
def help_page():

    if 'username' not in session:
        return redirect('/login')

    return render_template("help.html")

# NEW ROUTE 1

@app.route("/analyze_complaint", methods=["POST"])
def analyze_complaint():

    data = request.get_json()

    description = data.get("description", "").strip()

    if not description:

        return jsonify({
            "success": False,
            "message": "Please enter a complaint description."
        })

    result = predict_complaint(description)

    return jsonify(result)

@app.route("/check_duplicate", methods=["POST"])
def check_duplicate():

    data = request.get_json()

    description = data.get("description", "")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT description
        FROM complaints
    """)

    existing_complaints = [
        row[0]
        for row in cur.fetchall()
    ]

    conn.close()

    result = duplicate_detector.check_duplicate(
        description,
        existing_complaints
    )

    if result is None:

        return jsonify({

            "duplicate": False

        })

    return jsonify({

        "duplicate": bool(result["duplicate"]),

        "similarity": round(
            result["similarity"] * 100,
            2
        ),

        "matched_complaint":
            result["matched_complaint"]

    })


@app.route('/predict_preview', methods=['POST'])
def predict_preview():
    data = request.get_json(silent=True) or {}
    description = data.get('description', '').strip()
    if not description:
        return jsonify({"success": False, "message": "Description cannot be empty."})
    result = predict_complaint(description)
    return jsonify(result)


@app.route('/submit_complaint', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def submit_complaint():

    if 'username' not in session:
        return redirect('/login')

    if request.method == 'POST':

        # ------------------------------------
        # Complaint Details
        # ------------------------------------

        description = request.form['description']
        address = request.form['address']
        latitude = request.form['latitude']
        longitude = request.form['longitude']

        image = request.files.get('image')   # safe read – checked properly below

        # ------------------------------------
        # Validate Location
        # ------------------------------------

        if not latitude or not longitude:
            flash('Please pick your location on the map before submitting.', 'error')
            return redirect('/submit_complaint')

        # ------------------------------------
        # AI Prediction
        # ------------------------------------

        ai_result = predict_complaint(description)

        if not ai_result["success"]:
            return ai_result["message"]

        category = ai_result["category"]
        department = ai_result["department"]
        priority = ai_result["priority"]
        confidence = ai_result["confidence"]

        # Check if citizen confirmed a department during ambiguity prompt
        confirmed_category = request.form.get('confirmed_category', '').strip()
        if confirmed_category and confirmed_category in CATEGORY_MAPPING:
            category = confirmed_category
            department = CATEGORY_MAPPING[category]["department"]
            priority = CATEGORY_MAPPING[category]["priority"]

        # Check if Civic SOS Emergency Override was selected
        is_emergency = 1 if request.form.get('is_emergency') in ('1', 'true', 'True') else 0

        print("\n========== AI Prediction ==========")
        print(f"Category   : {category}")
        print(f"Department : {department}")
        print(f"Priority   : {priority}")
        print(f"Confidence : {confidence}%")
        print(f"Emergency  : {'YES' if is_emergency else 'NO'}")
        print("===================================\n")

        # ------------------------------------
        # Community Radius Validation
        # ------------------------------------

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT latitude, longitude, radius
            FROM community_settings
            WHERE id = 1
        """)

        community = cur.fetchone()

        if community and community[0] is not None:
            c_lat, c_lon, c_rad = float(community[0]), float(community[1]), float(community[2])
            distance = calculate_distance(latitude, longitude, c_lat, c_lon)
            if distance > c_rad:
                conn.close()
                flash(
                    f'Your location is {round(distance, 2)} KM from the community '
                    f'({c_rad} KM radius allowed). Please raise the issue with your local authority.',
                    'error'
                )
                return redirect('/submit_complaint')

        # ------------------------------------
        # Same-user Duplicate Block (spam prevention)
        # ------------------------------------
        conn.close()

        if user_recent_duplicate(session['username'], description, category, days=7):
            flash(
                "You already submitted a very similar complaint recently. "
                "Please track your existing complaint instead.",
                "warning"
            )
            return redirect('/view_complaints')

        # ------------------------------------
        # GPS-based nearby complaint count
        # ------------------------------------
        nearby_count = count_nearby_complaints(
            float(latitude), float(longitude), category, radius_km=0.2
        )

        # ------------------------------------
        # Smart GPS Priority Escalation
        # ------------------------------------
        if is_emergency:
            priority = "Critical"
        elif nearby_count >= 7:
            priority = "Critical"
        elif nearby_count >= 5:
            priority = "Critical" if priority in ("High", "Critical") else "High"
        elif nearby_count >= 3:
            if priority == "Low":      priority = "Medium"
            elif priority == "Medium": priority = "High"
            elif priority == "High":   priority = "Critical"

        hotspot = is_hotspot(float(latitude), float(longitude), category, threshold=3)

        # ------------------------------------
        # Image — MANDATORY
        # ------------------------------------

        image = request.files.get("image")

        if not image or image.filename == "":
            flash("An image of the issue is required. Please upload a photo.", "error")
            return redirect('/submit_complaint')

        # Save image — local or Cloudinary depending on environment
        image_path = save_image(image, prefix="complaint")
        if not image_path:
            flash("Invalid image format. Please upload a JPG or PNG.", "error")
            return redirect('/submit_complaint')

        # For CV check, we need a local path — download if Cloudinary URL
        if image_path.startswith("http"):
            full_image_path = None
        else:
            full_image_path = os.path.join(app.root_path, "static", image_path)

        # ------------------------------------
        # CV — Image Consistency Check
        # ------------------------------------
        if full_image_path:
            cv_check = check_image_consistency(full_image_path, category)
            needs_verification = 1 if cv_check.get("needs_flag") else 0
        else:
            cv_check = {}
            needs_verification = 0

        # ------------------------------------
        # SLA Deadline
        # ------------------------------------
        if is_emergency:
            # Life-Safety Civic SOS: 6-Hour Emergency SLA
            sla_deadline = (datetime.now() + timedelta(hours=6)).strftime("%d-%m-%Y %H:%M")
        else:
            sla_deadline = get_sla_deadline(category)
        created_at   = datetime.now().strftime("%d-%m-%Y %H:%M")

        # ------------------------------------
        # Save Complaint
        # ------------------------------------
        conn = get_db()
        cur  = conn.cursor()

        if USE_POSTGRES:
            cur.execute("""
            INSERT INTO complaints
            (
                username, category, priority, department,
                address, latitude, longitude, description,
                status, image_path, created_at, needs_verification,
                sla_deadline, updated_at, is_emergency
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """, (
                session['username'], category, priority, department,
                address, latitude, longitude, description,
                "Pending", image_path, created_at, needs_verification,
                sla_deadline, created_at, is_emergency
            ))
            row = cur.fetchone()
            complaint_id = row[0] if row else None
        else:
            cur.execute("""
            INSERT INTO complaints
            (
                username, category, priority, department,
                address, latitude, longitude, description,
                status, image_path, created_at, needs_verification,
                sla_deadline, updated_at, is_emergency
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session['username'], category, priority, department,
                address, latitude, longitude, description,
                "Pending", image_path, created_at, needs_verification,
                sla_deadline, created_at, is_emergency
            ))
            complaint_id = cur.lastrowid

        conn.commit()
        conn.close()

        # ------------------------------------
        # Timeline entry
        # ------------------------------------
        if is_emergency:
            add_timeline(complaint_id, session['username'], "🚨 Civic SOS Emergency",
                         f"EMERGENCY OVERRIDE: Category: {category} | Priority: Critical | Emergency SLA: 6 Hours ({sla_deadline})")
        else:
            add_timeline(complaint_id, session['username'], "Submitted",
                         f"Category: {category} | Priority: {priority} | SLA: {sla_deadline}")

        # ------------------------------------
        # Notifications
        # ------------------------------------
        if hotspot:
            add_notification("admin",
                f"Hotspot Alert: {nearby_count} users reported '{category}' near {address[:40]}")

        if needs_verification:
            add_notification(session['username'],
                f"Your complaint was submitted but flagged for admin review: {cv_check.get('message', '')}")
        else:
            add_notification(session['username'],
                f"Complaint submitted. SLA deadline: {sla_deadline}.")

        return redirect('/view_complaints')

    return render_template("submit_complaint.html")


# --------------------------------------------------
# Submit Anyway (Duplicate Warning bypass)
# --------------------------------------------------

@app.route('/submit_anyway', methods=['POST'])
def submit_anyway():
    """
    Called from duplicate_warning.html when the citizen chooses to submit
    despite a duplicate being detected. Since file data cannot be preserved
    across redirects, we redirect back to the complaint form with a notice.
    """
    if 'username' not in session:
        return redirect('/login')
    flash('Please re-submit your complaint — image uploads cannot be preserved across redirects.', 'info')
    return redirect('/submit_complaint')


# --------------------------------------------------
# AI Similar Complaint Helper
# --------------------------------------------------

# --------------------------------------------------
# AI Related Complaint Helper (GPS Aware)
# --------------------------------------------------

def get_similar_complaints(description,
                           category,
                           latitude,
                           longitude):

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""

        SELECT

            id,

            description,

            latitude,

            longitude,

            status

        FROM complaints

        WHERE category=?

        AND status IN ('Pending','In Progress')

    """, (category,))

    rows = cur.fetchall()

    conn.close()

    related = []

    for row in rows:

        # Skip current complaint

        if row["description"] == description:
            continue

        # Distance

        distance = calculate_distance(

            latitude,

            longitude,

            row["latitude"],

            row["longitude"]

        )

        # Ignore if farther than 500 meters

        if distance > 0.5:
            continue

        result = duplicate_detector.check_duplicate(

            description,

            [row["description"]]

        )

        if result and result["duplicate"]:

            related.append({

                "id": row["id"],

                "description": row["description"],

                "status": row["status"],

                "distance": round(distance,2),

                "similarity": round(
                    result["similarity"]*100,
                    2
                )

            })

    return related

# NEW ROUTE 2
@app.route('/view_complaints')
def view_complaints():

    if 'username' not in session:
        return redirect('/login')

    username = session['username']

    search = request.args.get('search', '').strip()
    category = request.args.get('category', '')
    status = request.args.get('status', '')

    conn = get_db()
    cur = conn.cursor()

    query = """
    SELECT
        id,
        category,
        priority,
        address,
        latitude,
        longitude,
        description,
        status,
        image_path,
        feedback,
        rating,
        rejection_reason,
        sla_deadline,
        resolution_image,
        resolution_score,
        officer_remark,
        needs_verification,
        is_emergency
    FROM complaints
    WHERE username=?
    """

    params = [username]

    # Search Complaint ID
    if search:

        if search.upper().startswith("SCS-"):
            search = search[4:]

        query += " AND CAST(id AS TEXT) LIKE ?"
        params.append(f"%{search}%")

    # Category Filter
    if category:

        query += " AND category=?"
        params.append(category)

    # Status Filter
    if status:

        query += " AND status=?"
        params.append(status)

    query += " ORDER BY id DESC"

    cur.execute(query, params)

    complaints = cur.fetchall()

    # Dashboard Cards
    cur.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE username=?
    """,(username,))
    total = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE username=?
        AND status='Pending'
    """,(username,))
    pending = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE username=?
        AND status='Resolved'
    """,(username,))
    resolved = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE username=?
        AND status='Rejected'
    """,(username,))
    rejected = cur.fetchone()[0]

    conn.close()

    return render_template(

        "view_complaints.html",

        complaints=complaints,

        total=total,

        pending=pending,

        resolved=resolved,

        rejected=rejected

    )

@app.route('/feedback/<int:id>', methods=['GET', 'POST'])
def feedback(id):

    if 'username' not in session:
        return redirect('/login')

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":

        rating = request.form["rating"]

        feedback = request.form["feedback"]

        cur.execute("""
        UPDATE complaints
        SET
            rating=?,
            feedback=?
        WHERE
            id=?
            AND username=?
        """,
        (
            rating,
            feedback,
            id,
            session['username']
        ))

        conn.commit()

        conn.close()

        return redirect("/view_complaints")

    conn.close()

    return render_template("feedback.html")


@app.route('/verify_resolution/<int:complaint_id>', methods=['POST'])
def verify_resolution(complaint_id):
    if 'username' not in session:
        return jsonify({"success": False, "message": "Please log in first."}), 401

    username = session['username']
    action = request.form.get('action') or (request.get_json(silent=True) or {}).get('action')
    remarks = request.form.get('remarks') or (request.get_json(silent=True) or {}).get('remarks') or ''

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id, username, status, category FROM complaints WHERE id=?", (complaint_id,))
    comp = cur.fetchone()
    if not comp:
        conn.close()
        return jsonify({"success": False, "message": "Complaint not found."}), 404

    comp_user = comp[1]
    if comp_user != username and session.get('role') != 'Admin' and username != 'admin':
        conn.close()
        return jsonify({"success": False, "message": "Unauthorized."}), 403

    now_str = datetime.now().strftime("%d-%m-%Y %H:%M")

    if action == 'confirm':
        cur.execute("""
            UPDATE complaints
            SET status = 'Closed', verification_status = 'Verified by Citizen', updated_at = ?
            WHERE id = ?
        """, (now_str, complaint_id))
        conn.commit()
        conn.close()

        add_timeline(complaint_id, username, "Citizen Confirmed", "Citizen verified the resolution. Ticket permanently closed.")
        add_notification("admin", f"Complaint SCS-{complaint_id:04d} was verified and permanently closed by citizen {username}.")
        flash(f"Thank you! Resolution for SCS-{complaint_id:04d} verified and ticket closed.", "success")
        return jsonify({"success": True, "status": "Closed", "message": "Resolution confirmed."})

    elif action == 'dispute':
        dispute_note = f"Disputed by citizen: {remarks}" if remarks else "Disputed by citizen (unresolved)."
        cur.execute("""
            UPDATE complaints
            SET status = 'Reopened', verification_status = 'Disputed', officer_remark = ?, updated_at = ?
            WHERE id = ?
        """, (dispute_note, now_str, complaint_id))
        conn.commit()
        conn.close()

        add_timeline(complaint_id, username, "Citizen Disputed", dispute_note)
        add_notification("admin", f"⚠️ Dispute Alert: Complaint SCS-{complaint_id:04d} was marked as unresolved by {username}. Reason: {remarks}")
        flash(f"Complaint SCS-{complaint_id:04d} has been reopened and escalated for re-inspection.", "warning")
        return jsonify({"success": True, "status": "Reopened", "message": "Complaint reopened."})

    conn.close()
    return jsonify({"success": False, "message": "Invalid action."}), 400


@app.route('/impact_wall')
def impact_wall():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, category, department, address, description,
               image_path, resolution_image, resolution_score,
               created_at, updated_at, upvotes
        FROM complaints
        WHERE status IN ('Resolved', 'Closed')
          AND resolution_image IS NOT NULL
          AND resolution_image != ''
        ORDER BY id DESC
        LIMIT 30
    """)
    records = cur.fetchall()
    conn.close()

    wall_items = []
    for r in records:
        wall_items.append({
            "id": r[0],
            "category": r[1],
            "department": r[2],
            "address": r[3],
            "description": r[4],
            "image_path": r[5],
            "resolution_image": r[6],
            "resolution_score": r[7] or 85,
            "created_at": r[8],
            "updated_at": r[9],
            "upvotes": r[10] or 0
        })

    return render_template("impact_wall.html", items=wall_items)


@app.route('/thank_resolution/<int:complaint_id>', methods=['POST'])
def thank_resolution(complaint_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE complaints SET upvotes = COALESCE(upvotes, 0) + 1 WHERE id = ?", (complaint_id,))
    conn.commit()
    cur.execute("SELECT COALESCE(upvotes, 0) FROM complaints WHERE id = ?", (complaint_id,))
    row = cur.fetchone()
    conn.close()
    count = row[0] if row else 1
    return jsonify({"success": True, "upvotes": count})


@app.route('/admin')
def admin():

    if 'username' not in session:
        return redirect('/login')

    if session['username'] != 'admin':
        return "Access Denied"

    # Run auto-escalation every time admin opens dashboard
    run_auto_escalation()

    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    priority = request.args.get('priority', '').strip()

    conn = get_db()
    cur = conn.cursor()

    query = """
    SELECT
        c.id,
        c.username,
        c.category,
        c.priority,
        c.address,
        c.status,
        c.image_path,
        (
            SELECT COUNT(*)
            FROM complaints
            WHERE category = c.category
            AND address = c.address
        ) AS area_reports,
        c.created_at,
        c.sla_deadline,
        c.escalated

    FROM complaints c

    WHERE c.status IN ('Pending','In Progress')
    """

    params = []

    if search:

        query += """
        AND (
            CAST(c.id AS TEXT) LIKE ?
            OR c.username LIKE ?
            OR c.address LIKE ?
        )
        """

        keyword = "%" + search + "%"

        params.extend([
            keyword,
            keyword,
            keyword
        ])

    if category:

        query += " AND c.category=?"
        params.append(category)

    if priority:

        query += " AND c.priority=?"
        params.append(priority)

    query += """
    ORDER BY
        CASE c.priority
            WHEN 'Critical' THEN 1
            WHEN 'High' THEN 2
            WHEN 'Medium' THEN 3
            ELSE 4
        END,
        c.id DESC
    """

    cur.execute(query, params)
    complaints = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM complaints")
    total = cur.fetchone()[0]

    cur.execute("""
    SELECT COUNT(*)
    FROM complaints
    WHERE status IN ('Pending','In Progress')
    """)
    active = cur.fetchone()[0]

    cur.execute("""
    SELECT COUNT(*)
    FROM complaints
    WHERE status='Pending'
    """)
    pending = cur.fetchone()[0]

    cur.execute("""
    SELECT COUNT(*)
    FROM complaints
    WHERE status='In Progress'
    """)
    in_progress = cur.fetchone()[0]

    cur.execute("""
    SELECT COUNT(*)
    FROM complaints
    WHERE status='Resolved'
    """)
    resolved = cur.fetchone()[0]

    cur.execute("""
    SELECT COUNT(*)
    FROM complaints
    WHERE status='Rejected'
    """)
    rejected = cur.fetchone()[0]

    conn.close()

    return render_template(
        "admin_dashboard.html",
        complaints=complaints,
        total=total,
        active=active,
        pending=pending,
        in_progress=in_progress,
        resolved=resolved,
        rejected=rejected,
        now=datetime.now().strftime("%d-%m-%Y")
    )
@app.route("/department_dashboard")
def department_dashboard():

    # ------------------------------------
    # Authentication
    # ------------------------------------

    if 'username' not in session:
        return redirect('/login')

    if session.get("role") != "Officer":
        return "Access Denied"

    department = session.get("department")

    # ------------------------------------
    # Database
    # ------------------------------------

    conn = get_db()
    cur = conn.cursor()

    # ------------------------------------
    # Load Active Complaints
    # ------------------------------------

    dept_prefix = department.split()[0] if department else ""
    cur.execute("""
        SELECT
            id,
            category,
            priority,
            address,
            latitude,
            longitude,
            description,
            status,
            image_path
        FROM complaints
        WHERE (
            department=?
            OR department LIKE ?
            OR category LIKE ?
            OR ? LIKE '%' || category || '%'
        )
        AND status IN ('Pending','In Progress')
        ORDER BY id DESC
    """, (department, f"%{dept_prefix}%", f"%{dept_prefix}%", department))

    rows = cur.fetchall()

    conn.close()

    complaints = []

    # ------------------------------------
    # Calculate Related Reports
    # ------------------------------------

    for row in rows:

        related_reports = count_related_active_complaints(
            row["description"],
            row["category"],
            row["latitude"],
            row["longitude"]
        )

        complaints.append({

            "id": row["id"],

            "category": row["category"],

            # AI Predicted Priority
            "priority": row["priority"],

            # Final Priority (will change below)
            "effective_priority": row["priority"],

            "related_reports": related_reports,

            "address": row["address"],

            "latitude": row["latitude"],

            "longitude": row["longitude"],

            "description": row["description"],

            "status": row["status"],

            "image_path": row["image_path"]

        })

    # ------------------------------------
    # Priority Escalation
    # ------------------------------------

    for complaint in complaints:

        reports = complaint["related_reports"]

        if reports >= 5:

            complaint["effective_priority"] = "Critical"

        elif reports >= 3:

            if complaint["priority"] == "Medium":

                complaint["effective_priority"] = "High"

            elif complaint["priority"] == "High":

                complaint["effective_priority"] = "Critical"

    # ------------------------------------
    # Sort Using Priority Queue
    # ------------------------------------

    complaints = priority_queue.build_priority_queue(
        complaints
    )

    # ------------------------------------
    # Render
    # ------------------------------------

    return render_template(

        "department_dashboard.html",

        username=session["username"],

        department=department,

        complaints=complaints

    )

@app.route('/update_status/<int:id>', methods=['GET', 'POST'])
def update_status(id):

    conn = get_db()
    cur = conn.cursor()

    # -----------------------------
    # Save Changes
    # -----------------------------
    if request.method == "POST":

        status = request.form["status"]

        rejection_reason = request.form.get("rejection_reason", "")
        assigned_to      = request.form.get("assigned_to", "").strip()
        officer_remark   = request.form.get("officer_remark", "").strip()

        # Get username before updating
        cur.execute("SELECT username FROM complaints WHERE id=?", (id,))
        username = cur.fetchone()[0]

        # Update complaint (include assigned_to + officer_remark + updated_at)
        cur.execute("""
        UPDATE complaints
        SET
            status=?,
            rejection_reason=?,
            assigned_to=CASE WHEN ? != '' THEN ? ELSE assigned_to END,
            officer_remark=CASE WHEN ? != '' THEN ? ELSE officer_remark END,
            updated_at=?
        WHERE id=?
        """, (
            status,
            rejection_reason,
            assigned_to, assigned_to,
            officer_remark, officer_remark,
            datetime.now().strftime("%d-%m-%Y %H:%M"),
            id
        ))

        # Notify assigned officer if changed
        if assigned_to:
            add_notification(assigned_to,
                f"You have been assigned complaint SCS-{id:04d} ({status}).")


        conn.commit()

        # -----------------------------
        # Notifications
        # -----------------------------

        if status == "Pending":
            add_notification(username, f"Complaint SCS-{id:04d} is pending review.")
        elif status == "In Progress":
            add_notification(username, f"Complaint SCS-{id:04d} is now In Progress.")
            send_email_notification(username,
                f"Complaint SCS-{id:04d} is now In Progress",
                f"""<div style="font-family:sans-serif;max-width:520px;margin:auto;background:#f8fafc;border-radius:12px;overflow:hidden;">
                <div style="background:linear-gradient(135deg,#1e40af,#7c3aed);padding:24px;text-align:center;">
                  <h2 style="color:#fff;margin:0;">🔵 Complaint Under Review</h2>
                </div>
                <div style="padding:24px;">
                  <p style="color:#334155;">Your complaint <strong>SCS-{id:04d}</strong> is now being reviewed by our team.</p>
                  <div style="background:#e0e7ff;border-radius:8px;padding:12px 16px;margin:16px 0;">
                    <p style="margin:0;color:#1e40af;font-weight:600;">Status: In Progress</p>
                  </div>
                  <p style="color:#64748b;font-size:13px;">Login to your portal to track real-time updates.</p>
                </div></div>""")
        elif status == "Resolved":
            add_notification(username, f"Complaint SCS-{id:04d} has been resolved.")
            send_email_notification(username,
                f"Complaint SCS-{id:04d} Resolved ✅",
                f"""<div style="font-family:sans-serif;max-width:520px;margin:auto;background:#f8fafc;border-radius:12px;overflow:hidden;">
                <div style="background:linear-gradient(135deg,#166534,#15803d);padding:24px;text-align:center;">
                  <h2 style="color:#fff;margin:0;">✅ Complaint Resolved!</h2>
                </div>
                <div style="padding:24px;">
                  <p style="color:#334155;">Your complaint <strong>SCS-{id:04d}</strong> has been successfully resolved.</p>
                  <p style="color:#64748b;font-size:13px;">Please log in and rate our service — your feedback helps us improve!</p>
                </div></div>""")
        elif status == "Rejected":
            add_notification(username, f"Complaint SCS-{id:04d} has been rejected.")
            send_email_notification(username,
                f"Complaint SCS-{id:04d} Update",
                f"""<div style="font-family:sans-serif;max-width:520px;margin:auto;background:#f8fafc;border-radius:12px;overflow:hidden;">
                <div style="background:linear-gradient(135deg,#991b1b,#b91c1c);padding:24px;text-align:center;">
                  <h2 style="color:#fff;margin:0;">❌ Complaint Status Update</h2>
                </div>
                <div style="padding:24px;">
                  <p style="color:#334155;">Your complaint <strong>SCS-{id:04d}</strong> has been reviewed.</p>
                  {f'<div style="background:#fee2e2;border-radius:8px;padding:12px;"><p style="margin:0;color:#991b1b;"><strong>Reason:</strong> {rejection_reason}</p></div>' if rejection_reason else ''}
                  <p style="color:#64748b;font-size:13px;margin-top:12px;">Log in to view details or re-submit.</p>
                </div></div>""")

        conn.close()

        # Log to complaint timeline
        add_timeline(id, session['username'], status,
                     officer_remark or rejection_reason or "")

        return redirect("/admin")

    # -----------------------------
    # Complaint Details
    # -----------------------------

    cur.execute("""
    SELECT
        id, username, category, priority, address,
        description, status, image_path, created_at,
        rejection_reason, feedback, rating,
        assigned_to, officer_remark
    FROM complaints
    WHERE id=?
    """, (id,))

    complaint = cur.fetchone()

    # Fetch all officers for assignment dropdown
    cur.execute("SELECT username, department FROM users WHERE role='Officer' ORDER BY department")
    officers = cur.fetchall()

    conn.close()

    return render_template(
        "update_status.html",
        complaint=complaint,
        officers=officers
    )

# ==========================================
# SPRINT 1 - OFFICER MODULE START
# ==========================================
@app.route('/officer_action/<int:id>', methods=['GET', 'POST'])
def officer_action(id):

    # ------------------------------------
    # Authentication
    # ------------------------------------

    if 'username' not in session:
        return redirect('/login')

    if session.get("role") != "Officer":
        return "Access Denied"

    department = session.get("department")
    officer_username = session.get("username")

    conn = get_db()
    cur = conn.cursor()

    # ------------------------------------
    # Load Complaint
    # ------------------------------------

    cur.execute("""
        SELECT *
        FROM complaints
        WHERE id=?
    """, (id,))

    complaint = cur.fetchone()

    if complaint is None:
        conn.close()
        return "Complaint not found or access denied."

    # ------------------------------------
    # Officer Update
    # ------------------------------------

    if request.method == "POST":

        old_status = complaint["status"]
        new_status = request.form["status"]
        officer_remark = request.form["officer_remark"]

        resolution_image = complaint["resolution_image"]
        resolution_score = 0
        verification_status = "Pending"

        image = request.files.get("resolution_image")

        # ------------------------------------
        # Resolution Image — MANDATORY when marking Resolved
        # ------------------------------------

        if new_status == "Resolved" and (not image or not image.filename):
            flash(
                "A resolution image (After photo) is required when marking a complaint as Resolved.",
                "error"
            )
            conn.close()
            return redirect(f'/officer_action/{id}')

        if image and image.filename:
            resolution_image = save_image(image, prefix="resolution")
            if resolution_image and not resolution_image.startswith("http"):
                saved_path = os.path.join(app.root_path, "static", resolution_image)
            else:
                saved_path = None

            # ------------------------------------
            # CV — Before vs After Comparison
            # ------------------------------------
            try:
                before_img = complaint["image_path"]
                if before_img and saved_path and not str(before_img).startswith("http"):
                    before_path = os.path.join(app.root_path, "static", before_img)
                    if os.path.exists(before_path) and os.path.exists(saved_path):
                        cv_result = calculate_resolution_score(before_path, saved_path)
                        resolution_score = cv_result.get("score", 0)
                        verification_status = cv_result.get("verdict", "Verified")

                        # Override status based on CV score
                        if new_status == "Resolved":
                            new_status = cv_result.get("new_status", "Resolved")
            except Exception as cv_e:
                print(f"[CV Score Warning] {cv_e}")

        # ------------------------------------
        # Update Complaint
        # ------------------------------------

        cur.execute("""
            UPDATE complaints
            SET
                status=?,
                officer_remark=?,
                resolution_image=?,
                resolution_score=?,
                verification_status=?
            WHERE id=?
        """,
        (
            new_status,
            officer_remark,
            resolution_image,
            resolution_score,
            verification_status,
            id
        ))

        # ------------------------------------
        # Complaint History
        # ------------------------------------

        cur.execute("""
            INSERT INTO complaint_history
            (
                complaint_id,
                officer_username,
                old_status,
                new_status,
                remarks
            )
            VALUES (?, ?, ?, ?, ?)
        """,
        (
            id,
            officer_username,
            old_status,
            new_status,
            officer_remark
        ))

        conn.commit()
        conn.close()

        # ------------------------------------
        # Notification with CV Score
        # ------------------------------------

        if resolution_score > 0:
            add_notification(
                complaint["username"],
                f"🤖 AI verified your complaint SCS-{id:04d}: "
                f"{verification_status} (Score: {resolution_score}%). "
                f"Status: {new_status}."
            )
        else:
            add_notification(
                complaint["username"],
                f"📢 Your complaint SCS-{id:04d} has been updated to '{new_status}'."
            )

        return redirect("/department_dashboard")

    # ------------------------------------
    # Complaint History
    # ------------------------------------

    cur.execute("""
        SELECT
            officer_username,
            old_status,
            new_status,
            remarks,
            action_time
        FROM complaint_history
        WHERE complaint_id=?
        ORDER BY action_time ASC
    """, (id,))

    history = cur.fetchall()

    conn.close()

    # ------------------------------------
    # Related Complaints
    # ------------------------------------

    similar_complaints = get_similar_complaints(
        complaint["description"],
        complaint["category"],
        complaint["latitude"],
        complaint["longitude"]
    )

    # ------------------------------------
    # Render Page
    # ------------------------------------

    return render_template(
        "officer_action.html",
        complaint=complaint,
        history=history,
        similar_complaints=similar_complaints
    )


# --------------------------------------------------
# Count Active Related Complaints (GPS Aware)
# --------------------------------------------------

def count_related_active_complaints(
        description,
        category,
        latitude,
        longitude
):

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT
            description,
            latitude,
            longitude,
            status
        FROM complaints
        WHERE category=?
        AND status IN ('Pending','In Progress')
    """, (category,))

    rows = cur.fetchall()

    conn.close()

    related_reports = 0

    for row in rows:

        # Skip the current complaint
        if row["description"] == description:
            continue

        # Skip invalid locations
        if row["latitude"] is None or row["longitude"] is None:
            continue

        # Calculate distance
        distance = calculate_distance(
            latitude,
            longitude,
            row["latitude"],
            row["longitude"]
        )

        # Ignore complaints farther than 500 m
        if distance > 0.5:
            continue

        # Check semantic similarity
        result = duplicate_detector.check_duplicate(
            description,
            [row["description"]]
        )

        if result and result["duplicate"]:
            related_reports += 1

    return related_reports

@app.route('/admin_settings', methods=['GET', 'POST'])
def admin_settings():

    if 'username' not in session or session.get('role') != 'Admin':
        return redirect('/login')

    conn = get_db()
    cur = conn.cursor()

    if request.method == 'POST':

        community_name = request.form['community_name']
        latitude       = request.form['latitude']
        longitude      = request.form['longitude']
        radius         = request.form['radius']

        cur.execute(
            """
            UPDATE community_settings
            SET community_name=?,
                latitude=?,
                longitude=?,
                radius=?
            WHERE id=1
            """,
            (community_name, latitude, longitude, radius)
        )

        conn.commit()
        conn.close()

        flash('\u2705 Community settings saved successfully!', 'success')
        return redirect('/admin_settings')   # PRG pattern — prevents re-submit on refresh

    cur.execute(
        "SELECT * FROM community_settings WHERE id=1"
    )

    settings = cur.fetchone()
    conn.close()

    return render_template(
        'admin_settings.html',
        settings=settings
    )

@app.route('/analytics')
def analytics():

    # -------------------------------------
    # Authentication
    # -------------------------------------

    if 'username' not in session:
        return redirect('/login')

    if session.get("role") != "Admin":
        return "Access Denied"

    # -------------------------------------
    # Database Connection
    # -------------------------------------

    conn = get_db()
    cur = conn.cursor()

    # =====================================
    # Dashboard Cards
    # =====================================

    cur.execute("SELECT COUNT(*) FROM complaints")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending'")
    pending = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='In Progress'")
    in_progress = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'")
    resolved = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='Rejected'")
    rejected = cur.fetchone()[0]

    # =====================================
    # Resolution Rate
    # =====================================

    if total == 0:
        resolution_rate = 0
    else:
        resolution_rate = round((resolved / total) * 100, 1)

    # =====================================
    # Community Health
    # =====================================

    if pending >= 15:
        health_status = "Needs Immediate Attention"

    elif pending >= 8:
        health_status = "Moderate"

    else:
        health_status = "Good"

    # =====================================
    # Category Statistics
    # =====================================

    cur.execute("""
        SELECT
            category,
            COUNT(*) AS total
        FROM complaints
        GROUP BY category
        ORDER BY total DESC
    """)

    category_data = cur.fetchall()

    if category_data:
        most_reported = category_data[0]["category"]
    else:
        most_reported = "No Data"

    # =====================================
    # Department Statistics
    # =====================================

    cur.execute("""
        SELECT
            department,
            COUNT(*) AS total
        FROM complaints
        GROUP BY department
        ORDER BY total DESC
    """)

    department_data = cur.fetchall()

    # =====================================
    # Top 5 Affected Areas
    # =====================================

    cur.execute("""
        SELECT
            address,
            COUNT(*) AS total
        FROM complaints
        GROUP BY address
        ORDER BY total DESC
        LIMIT 5
    """)

    top_areas = cur.fetchall()

    if top_areas:

        top_area_name = top_areas[0]["address"]

        if top_area_name:
            top_area_name = top_area_name.split(",")[0]

        top_area_count = top_areas[0]["total"]

    else:

        top_area_name = "No Data"
        top_area_count = 0

    # =====================================
    # Highest Priority Complaints
    # =====================================

    cur.execute("""
        SELECT
            id,
            category,
            priority,
            address,
            status
        FROM complaints
        WHERE status IN ('Pending','In Progress')
        ORDER BY
            CASE priority
                WHEN 'Critical' THEN 1
                WHEN 'High' THEN 2
                WHEN 'Medium' THEN 3
                ELSE 4
            END,
            id DESC
        LIMIT 10
    """)

    priority_complaints = cur.fetchall()

    # =====================================
    # Recent Complaints
    # =====================================

    cur.execute("""
        SELECT
            id,
            username,
            category,
            status,
            created_at
        FROM complaints
        ORDER BY id DESC
        LIMIT 10
    """)

    recent_complaints = cur.fetchall()

    conn.close()

    # =====================================
    # Render Dashboard
    # =====================================

    return render_template(

        "analytics.html",

        total=total,
        pending=pending,
        in_progress=in_progress,
        resolved=resolved,
        rejected=rejected,

        resolution_rate=resolution_rate,

        health_status=health_status,

        most_reported=most_reported,

        top_area_name=top_area_name,
        top_area_count=top_area_count,

        category_data=category_data,

        department_data=department_data,

        top_areas=top_areas,

        priority_complaints=priority_complaints,

        recent_complaints=recent_complaints

    )


@app.route('/complaint_map')
def complaint_map():

    conn = get_db()
    cur = conn.cursor()

    # -------------------------------
    # Complaint locations
    # -------------------------------
    cur.execute("""
    SELECT
        id,
        username,
        category,
        priority,
        address,
        latitude,
        longitude,
        status
    FROM complaints
    WHERE latitude IS NOT NULL
      AND longitude IS NOT NULL
    """)

    complaints = cur.fetchall()
    

    # -------------------------------
    # Dashboard Statistics
    # -------------------------------
    cur.execute("SELECT COUNT(*) FROM complaints")
    total = cur.fetchone()[0]

    cur.execute("""
    SELECT COUNT(*)
    FROM complaints
    WHERE status='Pending'
    """)
    pending = cur.fetchone()[0]

    cur.execute("""
    SELECT COUNT(*)
    FROM complaints
    WHERE status='In Progress'
    """)
    in_progress = cur.fetchone()[0]

    cur.execute("""
    SELECT COUNT(*)
    FROM complaints
    WHERE status='Resolved'
    """)
    resolved = cur.fetchone()[0]

    # -------------------------------
    # Community Settings
    # -------------------------------
    cur.execute("""
    SELECT
        community_name,
        latitude,
        longitude,
        radius
    FROM community_settings
    WHERE id=1
    """)

    community = cur.fetchone()

    conn.close()

    return render_template(
        "complaint_map.html",
        complaints=complaints,
        total=total,
        pending=pending,
        in_progress=in_progress,
        resolved=resolved,
        community=community
    )

@app.route("/complaint_history")
def complaint_history():

    if 'username' not in session:
        return redirect('/login')

    if session['username'] != 'admin':
        return "Access Denied"

    search = request.args.get("search", "").strip()
    category = request.args.get("category")
    status = request.args.get("status")

    conn = get_db()
    cur = conn.cursor()

    query = """
    SELECT
        id,
        username,
        category,
        priority,
        address,
        status,
        image_path,
        rejection_reason,
        feedback,
        rating,
        created_at
    FROM complaints
    WHERE status IN ('Resolved','Rejected')
    """

    params = []

    # ---------------- Search ----------------

    if search:
        query += """
        AND (
            CAST(id AS TEXT) LIKE ?
            OR username LIKE ?
            OR address LIKE ?
        )
        """
        keyword = "%" + search + "%"
        params.extend([keyword, keyword, keyword])

    # ---------------- Category ----------------

    if category:
        query += " AND category=?"
        params.append(category)

    # ---------------- Status ----------------

    if status:
        query += " AND status=?"
        params.append(status)

    query += " ORDER BY id DESC"

    cur.execute(query, params)
    complaints = cur.fetchall()

    # ---------------- Statistics ----------------

    cur.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status='Resolved'
    """)
    resolved = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status='Rejected'
    """)
    rejected = cur.fetchone()[0]

    cur.execute("""
        SELECT ROUND(AVG(rating),1)
        FROM complaints
        WHERE rating IS NOT NULL
    """)
    avg_rating = cur.fetchone()[0]

    if avg_rating is None:
        avg_rating = 0

    cur.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE feedback IS NOT NULL
        AND feedback!=''
    """)
    feedback_count = cur.fetchone()[0]

    conn.close()

    return render_template(
        "complaint_history.html",
        complaints=complaints,
        resolved=resolved,
        rejected=rejected,
        avg_rating=avg_rating,
        feedback_count=feedback_count
    )



# ============================
# Error Handlers
# ============================

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


# ============================
# Live Sync Poll API
# ============================

@app.route('/api/poll')
def api_poll():
    """
    Lightweight endpoint polled by admin/officer dashboards every 15s.
    Returns the latest complaint update timestamp + counts so the
    browser can detect changes without a full page reload.
    """
    if 'username' not in session:
        return jsonify({"error": "unauthenticated"}), 401

    conn = get_db()
    cur  = conn.cursor()

    # Latest activity marker
    cur.execute("""
        SELECT MAX(created_at) FROM complaints
    """)
    latest_created = cur.fetchone()[0] or ""

    cur.execute("""
        SELECT MAX(action_time) FROM complaint_history
    """)
    latest_action = cur.fetchone()[0] or ""

    # Per-status counts
    cur.execute("""
        SELECT status, COUNT(*) FROM complaints GROUP BY status
    """)
    counts = {row[0]: row[1] for row in cur.fetchall()}

    # Department-specific counts (for officers)
    dept = session.get("department")
    dept_pending = 0
    if dept:
        cur.execute("""
            SELECT COUNT(*) FROM complaints
            WHERE department=? AND status IN ('Pending','In Progress')
        """, (dept,))
        dept_pending = cur.fetchone()[0]

    conn.close()

    # Use latest of both timestamps as the change marker
    marker = max(latest_created, latest_action)

    return jsonify({
        "marker":      marker,
        "pending":     counts.get("Pending", 0),
        "in_progress": counts.get("In Progress", 0),
        "resolved":    counts.get("Resolved", 0),
        "rejected":    counts.get("Rejected", 0),
        "dept_pending": dept_pending
    })


# ============================
# Timeline API
# ============================

@app.route('/api/timeline/<int:complaint_id>')
def api_timeline(complaint_id):
    """Return timeline entries for a complaint as JSON."""
    if 'username' not in session:
        return jsonify({"error": "unauthenticated"}), 401

    conn = get_db()
    cur  = conn.cursor()

    # Security: citizen can only see their own complaint timeline
    if session.get('role') == 'Citizen':
        cur.execute("SELECT username FROM complaints WHERE id=?", (complaint_id,))
        row = cur.fetchone()
        if not row or row[0] != session['username']:
            conn.close()
            return jsonify({"error": "forbidden"}), 403

    cur.execute("""
        SELECT actor, action, note, timestamp
        FROM complaint_timeline
        WHERE complaint_id=?
        ORDER BY id ASC
    """, (complaint_id,))

    entries = [
        {"actor": r[0], "action": r[1], "note": r[2], "timestamp": r[3]}
        for r in cur.fetchall()
    ]
    conn.close()
    return jsonify({"entries": entries})


# ============================
# Officer Performance Page
# ============================

@app.route('/officer_performance')
def officer_performance():
    if 'username' not in session or session.get('username') != 'admin':
        return redirect('/login')

    conn = get_db()
    cur  = conn.cursor()

    cur.execute("""
        SELECT
            assigned_to                          AS officer,
            COUNT(*)                             AS total,
            SUM(CASE WHEN status='Resolved' THEN 1 ELSE 0 END) AS resolved,
            ROUND(AVG(CASE WHEN rating IS NOT NULL THEN rating END), 1) AS avg_rating,
            SUM(CASE WHEN status IN ('Pending','In Progress') THEN 1 ELSE 0 END) AS pending
        FROM complaints
        WHERE assigned_to IS NOT NULL AND assigned_to != ''
        GROUP BY assigned_to
        ORDER BY resolved DESC
    """)
    stats = cur.fetchall()
    conn.close()
    return render_template('officer_performance.html', stats=stats)


# ============================
# Heatmap API
# ============================

@app.route('/api/heatmap')
def api_heatmap():
    """Return complaint GPS points for Leaflet heatmap."""
    if 'username' not in session or session.get('username') != 'admin':
        return jsonify({"error": "unauthorized"}), 401

    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        SELECT latitude, longitude, category, priority, status, id
        FROM complaints
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """)
    rows = cur.fetchall()
    conn.close()

    weight_map = {"Critical": 1.0, "High": 0.7, "Medium": 0.4, "Low": 0.2}
    points = []
    for lat, lon, cat, pri, status, cid in rows:
        if lat and lon:
            points.append({
                "lat":      lat,
                "lon":      lon,
                "category": cat,
                "priority": pri,
                "status":   status,
                "id":       cid,
                "weight":   weight_map.get(pri, 0.3)
            })
    return jsonify({"points": points})


@app.route('/admin/heatmap')
def admin_heatmap():
    if 'username' not in session or session.get('username') != 'admin':
        return redirect('/login')

    conn = get_db()
    cur  = conn.cursor()
    cur.execute("SELECT latitude, longitude, radius FROM community_settings WHERE id=1")
    community = cur.fetchone()
    conn.close()

    center_lat = community[0] if community else 17.6868
    center_lon = community[1] if community else 83.2185

    return render_template('admin_heatmap.html',
                           center_lat=center_lat,
                           center_lon=center_lon)


# ============================
# CSV Export
# ============================

@app.route('/admin/export')
def admin_export():
    """Download all complaints as a CSV file."""
    if 'username' not in session or session.get('username') != 'admin':
        return redirect('/login')

    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        SELECT
            id, username, category, priority, address, description,
            status, created_at, sla_deadline, assigned_to,
            rejection_reason, rating, feedback, escalated
        FROM complaints
        ORDER BY id DESC
    """)
    rows = cur.fetchall()
    conn.close()

    # Build CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "User", "Category", "Priority", "Address", "Description",
        "Status", "Submitted At", "SLA Deadline", "Assigned To",
        "Rejection Reason", "Rating", "Feedback", "Auto-Escalated"
    ])
    for row in rows:
        writer.writerow([
            f"SCS-{row[0]:04d}", row[1], row[2], row[3], row[4], row[5],
            row[6], row[7], row[8] or "-", row[9] or "Unassigned",
            row[10] or "-", row[11] or "-", row[12] or "-",
            "Yes" if row[13] else "No"
        ])

    output.seek(0)
    from flask import Response
    filename = f"complaints_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


if __name__ == '__main__':
    app.run(debug=True)


