"""
db.py — Database abstraction layer
Supports SQLite (local dev) and PostgreSQL (Supabase production).

Usage:
    from db import get_db, q
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(q("SELECT * FROM users WHERE username=?"), ("admin",))

Set DATABASE_URL in .env for PostgreSQL:
    DATABASE_URL=postgresql://postgres:password@db.xxx.supabase.co:5432/postgres
"""

import os
import re

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Detect database backend
USE_POSTGRES = DATABASE_URL.startswith("postgres")


def q(sql: str) -> str:
    """
    Normalize SQL for the current backend.
    - Converts ? → %s for PostgreSQL
    - Converts INSERT OR IGNORE → INSERT ... ON CONFLICT DO NOTHING
    - Converts AUTOINCREMENT → nothing (PostgreSQL uses SERIAL)
    """
    if not USE_POSTGRES:
        return sql  # SQLite — return as-is

    # Placeholder conversion: ? → %s
    sql = sql.replace("?", "%s")

    # INSERT OR IGNORE → INSERT ... ON CONFLICT DO NOTHING
    sql = re.sub(
        r'INSERT\s+OR\s+IGNORE\s+INTO',
        'INSERT INTO', sql, flags=re.IGNORECASE
    )
    # Append ON CONFLICT DO NOTHING if we changed it
    if 'INSERT INTO' in sql and 'ON CONFLICT' not in sql.upper() and re.search(r'INSERT\s+OR\s+IGNORE', sql, re.IGNORECASE) is None:
        pass  # only add for converted queries (handled below)

    sql = re.sub(
        r'INSERT\s+INTO\s+([\w]+)\s*\(',
        lambda m: m.group(0),  # keep as-is, handled by caller pattern
        sql
    )

    # Re-apply ON CONFLICT for converted INSERT OR IGNORE
    if 'ON CONFLICT DO NOTHING' not in sql.upper():
        sql = re.sub(
            r'(INSERT INTO .*?VALUES\s*\([^)]+\))',
            r'\1 ON CONFLICT DO NOTHING',
            sql, flags=re.DOTALL | re.IGNORECASE
        )

    # AUTOINCREMENT → remove (PostgreSQL uses SERIAL)
    sql = sql.replace("AUTOINCREMENT", "")

    # INTEGER PRIMARY KEY → SERIAL PRIMARY KEY
    sql = re.sub(
        r'INTEGER\s+PRIMARY\s+KEY',
        'SERIAL PRIMARY KEY',
        sql, flags=re.IGNORECASE
    )

    return sql


def get_db():
    """
    Return a database connection.
    - SQLite connection if DATABASE_URL is not set
    - psycopg2 connection to Supabase if DATABASE_URL is set
    """
    if USE_POSTGRES:
        import psycopg2
        import psycopg2.extras
        url = DATABASE_URL
        # Heroku-style postgres:// → postgresql://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(url)
        conn.autocommit = False
        return conn
    else:
        import sqlite3
        conn = sqlite3.connect("complaints.db")
        conn.row_factory = sqlite3.Row
        return conn


# Tell the app which backend is active
BACKEND = "postgresql" if USE_POSTGRES else "sqlite"
