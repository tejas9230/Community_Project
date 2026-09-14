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

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Detect database backend
USE_POSTGRES = DATABASE_URL.startswith("postgres")


def q(sql: str) -> str:
    """
    Normalize SQL for PostgreSQL backend.
    - Converts ? → %s
    - Converts INSERT OR IGNORE → INSERT INTO ... ON CONFLICT DO NOTHING
    - Converts AUTOINCREMENT → empty string
    - Converts INTEGER PRIMARY KEY → SERIAL PRIMARY KEY
    """
    if not USE_POSTGRES:
        return sql

    # Replace ? with %s
    sql = sql.replace("?", "%s")

    # INSERT OR IGNORE INTO -> INSERT INTO ... ON CONFLICT DO NOTHING
    if "INSERT OR IGNORE" in sql.upper():
        sql = re.sub(r'INSERT\s+OR\s+IGNORE\s+INTO', 'INSERT INTO', sql, flags=re.IGNORECASE)
        if "ON CONFLICT" not in sql.upper():
            sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"

    # AUTOINCREMENT -> remove
    sql = re.sub(r'\bAUTOINCREMENT\b', '', sql, flags=re.IGNORECASE)

    # INTEGER PRIMARY KEY -> SERIAL PRIMARY KEY
    sql = re.sub(r'\bINTEGER\s+PRIMARY\s+KEY\b', 'SERIAL PRIMARY KEY', sql, flags=re.IGNORECASE)

    return sql


class PostgresRow:
    """A row object that supports both dict key lookup (row['col']) and integer index lookup (row[0])."""
    def __init__(self, description, tuple_vals):
        self._vals = tuple_vals
        self._keys = [col[0].lower() for col in description] if description else []
        self._mapping = {k: v for k, v in zip(self._keys, tuple_vals)}

    def __getitem__(self, item):
        if isinstance(item, int):
            return self._vals[item]
        if isinstance(item, str):
            val = self._mapping.get(item.lower())
            if val is None and item in self._mapping:
                val = self._mapping[item]
            return val
        return self._vals[item]

    def get(self, key, default=None):
        if isinstance(key, str):
            return self._mapping.get(key.lower(), self._mapping.get(key, default))
        try:
            return self._vals[key]
        except (IndexError, TypeError):
            return default

    def keys(self):
        return self._keys

    def values(self):
        return self._vals

    def items(self):
        return self._mapping.items()

    def __iter__(self):
        return iter(self._vals)

    def __len__(self):
        return len(self._vals)

    def __repr__(self):
        return f"<PostgresRow {self._mapping}>"


class PostgresCursorWrapper:
    def __init__(self, real_cursor):
        self._cur = real_cursor

    def execute(self, sql, params=None):
        norm_sql = q(sql)
        if params is not None:
            return self._cur.execute(norm_sql, params)
        return self._cur.execute(norm_sql)

    def executemany(self, sql, seq_of_params):
        norm_sql = q(sql)
        return self._cur.executemany(norm_sql, seq_of_params)

    def _wrap_row(self, row_tuple):
        if row_tuple is None:
            return None
        if isinstance(row_tuple, PostgresRow):
            return row_tuple
        return PostgresRow(self._cur.description, row_tuple)

    def fetchone(self):
        row = self._cur.fetchone()
        return self._wrap_row(row)

    def fetchall(self):
        rows = self._cur.fetchall()
        if not rows:
            return []
        return [self._wrap_row(r) for r in rows]

    def fetchmany(self, size=None):
        rows = self._cur.fetchmany(size) if size is not None else self._cur.fetchmany()
        if not rows:
            return []
        return [self._wrap_row(r) for r in rows]

    def __getattr__(self, name):
        return getattr(self._cur, name)


class PostgresConnectionWrapper:
    def __init__(self, real_conn):
        self._conn = real_conn

    def cursor(self, *args, **kwargs):
        real_cur = self._conn.cursor(*args, **kwargs)
        return PostgresCursorWrapper(real_cur)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_db():
    """
    Return a database connection.
    - Wrapped psycopg2 connection to Supabase if DATABASE_URL is set
    - Falls back to SQLite if network connection fails or DATABASE_URL is missing
    """
    if USE_POSTGRES:
        import psycopg2
        import psycopg2.extras
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        try:
            conn = psycopg2.connect(url, connect_timeout=5)
            conn.autocommit = False
            return PostgresConnectionWrapper(conn)
        except Exception as e:
            print(f"[DB] PostgreSQL connection failed: {e}")
            print("[DB] Falling back to local SQLite database (complaints.db)...")
            import sqlite3
            conn = sqlite3.connect("complaints.db")
            conn.row_factory = sqlite3.Row
            return conn
    else:
        import sqlite3
        conn = sqlite3.connect("complaints.db")
        conn.row_factory = sqlite3.Row
        return conn


# Tell the app which backend is active
BACKEND = "postgresql" if USE_POSTGRES else "sqlite"
