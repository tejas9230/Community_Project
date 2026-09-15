"""
migrate_supabase.py — Run once to create all tables in Supabase PostgreSQL
"""
import os
from dotenv import load_dotenv
load_dotenv()
import psycopg2

db_url = os.environ.get('DATABASE_URL')
if not db_url:
    print("ERROR: DATABASE_URL not set in .env")
    exit(1)

conn = psycopg2.connect(db_url)
cur  = conn.cursor()

print("Connected to Supabase. Creating tables...")

tables = [
    # users
    """
    CREATE TABLE IF NOT EXISTS users (
        username   TEXT PRIMARY KEY,
        password   TEXT NOT NULL,
        role       TEXT NOT NULL,
        department TEXT,
        email      TEXT,
        phone      TEXT
    )
    """,

    # complaints
    """
    CREATE TABLE IF NOT EXISTS complaints (
        id                  SERIAL PRIMARY KEY,
        username            TEXT,
        category            TEXT,
        description         TEXT,
        status              TEXT DEFAULT 'Pending',
        address             TEXT,
        image_path          TEXT,
        latitude            REAL,
        longitude           REAL,
        priority            TEXT DEFAULT 'Low',
        department          TEXT,
        officer_remark      TEXT,
        resolution_image    TEXT,
        created_at          TEXT,
        feedback            TEXT,
        rejection_reason    TEXT,
        rating              INTEGER,
        resolution_score    REAL DEFAULT 0,
        verification_status TEXT DEFAULT 'Pending',
        needs_verification  INTEGER DEFAULT 0,
        updated_at          TEXT,
        sla_deadline        TEXT,
        escalated           INTEGER DEFAULT 0,
        assigned_to         TEXT,
        is_emergency        INTEGER DEFAULT 0,
        upvotes             INTEGER DEFAULT 0
    )
    """,

    # notifications
    """
    CREATE TABLE IF NOT EXISTS notifications (
        id         SERIAL PRIMARY KEY,
        username   TEXT,
        message    TEXT,
        is_read    INTEGER DEFAULT 0,
        created_at TEXT
    )
    """,

    # complaint_timeline
    """
    CREATE TABLE IF NOT EXISTS complaint_timeline (
        id           SERIAL PRIMARY KEY,
        complaint_id INTEGER,
        actor        TEXT,
        action       TEXT,
        note         TEXT,
        timestamp    TEXT
    )
    """,

    # community_settings
    """
    CREATE TABLE IF NOT EXISTS community_settings (
        id             INTEGER PRIMARY KEY,
        community_name TEXT,
        latitude       REAL,
        longitude      REAL,
        radius         REAL
    )
    """,

    # announcements
    """
    CREATE TABLE IF NOT EXISTS announcements (
        id         SERIAL PRIMARY KEY,
        title      TEXT NOT NULL,
        body       TEXT NOT NULL,
        created_by TEXT DEFAULT 'admin',
        created_at TEXT,
        expires_at TEXT,
        is_active  INTEGER DEFAULT 1
    )
    """,

    # complaint_votes
    """
    CREATE TABLE IF NOT EXISTS complaint_votes (
        id           SERIAL PRIMARY KEY,
        complaint_id INTEGER,
        username     TEXT,
        UNIQUE(complaint_id, username)
    )
    """,

    # complaint_history
    """
    CREATE TABLE IF NOT EXISTS complaint_history (
        id               SERIAL PRIMARY KEY,
        complaint_id     INTEGER,
        officer_username TEXT,
        old_status       TEXT,
        new_status       TEXT,
        remarks          TEXT,
        action_time      TEXT DEFAULT (to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'))
    )
    """,

    # admin_directives
    """
    CREATE TABLE IF NOT EXISTS admin_directives (
        id            SERIAL PRIMARY KEY,
        from_user     TEXT,
        to_department TEXT,
        priority      TEXT DEFAULT 'High',
        message       TEXT,
        status        TEXT DEFAULT 'Dispatched',
        response_note TEXT DEFAULT '',
        created_at    TEXT,
        updated_at    TEXT
    )
    """,
]

for sql in tables:
    table_name = [l.strip() for l in sql.strip().splitlines() if 'TABLE' in l][0]
    try:
        cur.execute(sql)
        print(f"  ✅ {table_name}")
    except Exception as e:
        print(f"  ⚠️  {table_name} — {e}")
        conn.rollback()

# Seed community settings
try:
    cur.execute("""
        INSERT INTO community_settings (id, community_name, latitude, longitude, radius)
        VALUES (1, 'Rasapudipalem', 17.6868, 83.2185, 5)
        ON CONFLICT DO NOTHING
    """)
    print("  ✅ community_settings seeded")
except Exception as e:
    print(f"  ⚠️  seed — {e}")

# Seed default admin user
import bcrypt
admin_pw = bcrypt.hashpw(b'admin123', bcrypt.gensalt()).decode()
try:
    cur.execute("""
        INSERT INTO users (username, password, role, department)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """, ('admin', admin_pw, 'Admin', None))
    print("  ✅ admin user seeded")
except Exception as e:
    print(f"  ⚠️  admin seed — {e}")

# Seed default officers
officers = [
    ("roads",       "roads123",       "Roads & Infrastructure"),
    ("water",       "water123",       "Water Supply"),
    ("electricity", "electricity123", "Electricity & Street Lighting"),
    ("sanitation",  "sanitation123",  "Sanitation & Waste Management"),
    ("drainage",    "drainage123",    "Drainage & Sewage"),
    ("parks",       "parks123",       "Parks & Recreation"),
    ("health",      "health123",      "Public Health"),
    ("animals",     "animals123",     "Animal Control"),
]
for uname, pw, dept in officers:
    hashed = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    try:
        cur.execute("""
            INSERT INTO users (username, password, role, department)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (uname, hashed, 'Officer', dept))
    except Exception as e:
        print(f"  ⚠️  officer {uname} — {e}")
print("  ✅ officers seeded")

conn.commit()
conn.close()
print("\n✅ Migration complete! Supabase is ready.")
