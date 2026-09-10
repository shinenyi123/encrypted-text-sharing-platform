import os
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import sqlite3
from datetime import datetime, date

# Try importing psycopg2 for PostgreSQL
try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

# Database Config from Environment
DATABASE_URL = os.environ.get("DATABASE_URL")

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "habit_tracker_db")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASS", "")
DB_PORT = os.environ.get("DB_PORT", "5432")

# If DATABASE_URL is present, we force PostgreSQL usage.
USE_POSTGRES = bool(DATABASE_URL) or (os.environ.get("USE_POSTGRES", "false").lower() == "true" and PSYCOPG2_AVAILABLE)

SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), "habit_tracker.db")


def get_db():
    """Connect to PostgreSQL (Production/Local) or fallback to SQLite (Local only)."""
    
    # 1. Production PostgreSQL via DATABASE_URL
    if DATABASE_URL:
        if not PSYCOPG2_AVAILABLE:
            raise RuntimeError("DATABASE_URL is set but psycopg2 is not installed.")
        try:
            conn = psycopg2.connect(
                DATABASE_URL, 
                cursor_factory=psycopg2.extras.RealDictCursor
            )
            return conn, "postgres"
        except Exception as e:
            # Raise exception immediately. DO NOT fall back to SQLite.
            # Masking full URL in logs to prevent password leak.
            print(f"[Database] CRITICAL: Production PostgreSQL connection failed. Error: {e}")
            raise Exception("Failed to connect to production database. Check deployment logs.")

    # 2. Local PostgreSQL via DB_ environment variables
    if USE_POSTGRES:
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASS,
                port=DB_PORT,
                cursor_factory=psycopg2.extras.RealDictCursor
            )
            return conn, "postgres"
        except Exception as e:
            print(f"[Database] CRITICAL: Local PostgreSQL connection failed. Error: {e}")
            raise Exception("Failed to connect to local PostgreSQL database. No SQLite fallback permitted when USE_POSTGRES is true.")

    # 3. Local SQLite Fallback (Only if explicitly not using Postgres)
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn, "sqlite"

def _normalize_row(row, cursor=None):
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    if cursor is not None and getattr(cursor, "description", None):
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))
    return row


def connect_db():
    if DATABASE_URL:
        return psycopg2.connect(
            DATABASE_URL,
            cursor_factory=RealDictCursor,
        )
    else:
        return psycopg2.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            port=os.environ.get("DB_PORT", "5432"),
            database=os.environ.get("DB_NAME", "encrypt_text_web_db"),
            user=os.environ.get("DB_USER", "postgres"),
            password=os.environ.get("DB_PASSWORD"),
            cursor_factory=RealDictCursor,
        )


def init_db():
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS received_files (
                id SERIAL PRIMARY KEY,
                receiver_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                encrypted_content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(sender_id, receiver_id, file_name),

                FOREIGN KEY(receiver_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(sender_id) REFERENCES users(id) ON DELETE CASCADE
            );
                """
            )
        conn.commit()


def execute_query(query, values=()):
    postgres_query = query.replace("?", "%s")
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(postgres_query, values)

            row = None
            if cursor.description:
                row = cursor.fetchone()

            conn.commit()
            return _normalize_row(row, cursor)


def fetch_one(query, values=()):
    postgres_query = query.replace("?", "%s")
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(postgres_query, values)
            return _normalize_row(cursor.fetchone(), cursor)


def fetch_all(query, values=()):
    postgres_query = query.replace("?", "%s")
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(postgres_query, values)
            rows = cursor.fetchall()
            return [_normalize_row(row, cursor) for row in rows]


def fetch_user(email):
    return fetch_one("SELECT * FROM users WHERE email = ?", (email,))


def fetch_login_user(email):
    return fetch_one(
        """
        SELECT id, email, password_hash, is_verified
        FROM users
        WHERE email = ?
        """,
        (email,),
    )

def get_user_by_email(email):
    """Fetch the verified identity record from the Auth Service users table."""
    conn, db_type = get_db()
    cursor = conn.cursor()

    try:
        placeholder = "%s" if db_type == "postgres" else "?"
        cursor.execute(
            f'SELECT id, email, password_hash, is_verified FROM users WHERE email = {placeholder};',
            (email,)
        )
        row = cursor.fetchone()
        if row and db_type == "sqlite":
            row = dict(row)
        return row
    finally:
        cursor.close()
        conn.close()


def get_admin_users():
    return fetch_all(
        "SELECT id, email, created_at FROM users ORDER BY created_at DESC, id DESC"
    )


def get_admin_user(user_id):
    return fetch_one(
        "SELECT id, email, created_at FROM users WHERE id = ?", (user_id,)
    )


def get_admin_user_files(user_id, page=1, per_page=50):
    offset = (page - 1) * per_page
    return fetch_all(
        """
        SELECT
            rf.file_name,
            rf.created_at,
            sender.email AS sender_email,
            recipient.email AS recipient_email,
            CASE
                WHEN rf.sender_id = ? THEN 'sent'
                ELSE 'received'
            END AS direction
        FROM received_files rf
        JOIN users sender ON sender.id = rf.sender_id
        JOIN users recipient ON recipient.id = rf.receiver_id
        WHERE rf.sender_id = ? OR rf.receiver_id = ?
        ORDER BY rf.created_at DESC, rf.id DESC
        LIMIT ? OFFSET ?
        """,
        (user_id, user_id, user_id, per_page, offset),
    )


def count_admin_user_files(user_id):
    row = fetch_one(
        "SELECT COUNT(*) AS total FROM received_files WHERE sender_id = ? OR receiver_id = ?",
        (user_id, user_id),
    )
    return int(row["total"] if row else 0)


def get_contacts(user_id):
    with connect_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT
                    u.id,
                    u.email
                FROM users u
                JOIN (
                    SELECT sender_id AS contact_id
                    FROM received_files
                    WHERE receiver_id = %s

                    UNION

                    SELECT receiver_id AS contact_id
                    FROM received_files
                    WHERE sender_id = %s
                ) c
                ON u.id = c.contact_id
                ORDER BY u.email;
            """, (user_id, user_id))

            rows = cur.fetchall()
            return [_normalize_row(row, cur) for row in rows]


def get_received_files_list(user_id):
    with connect_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    rf.id,
                    rf.file_name,
                    rf.encrypted_content,
                    rf.created_at,
                    u.email AS sender_email,
                    u.id AS sender_id
                FROM received_files rf
                JOIN users u ON rf.sender_id = u.id
                WHERE rf.receiver_id = %s
                ORDER BY rf.created_at DESC;
            """, (user_id,))

            return cur.fetchall()


def insert_received_file(data):
    row = execute_query(
        "INSERT INTO received_files (receiver_id, sender_id, file_name, encrypted_content) VALUES (?, ?, ?, ?) RETURNING id",
        data,
    )
    return row["id"] if row else None


def get_received_files(user_id, sender_id=None):
    if sender_id is None:
        return fetch_all("SELECT * FROM received_files WHERE receiver_id = ? ORDER BY id DESC", (user_id,))
    return fetch_all(
        "SELECT * FROM received_files WHERE receiver_id = ? AND sender_id = ? ORDER BY id DESC",
        (user_id, sender_id),
    )


def get_sent_files(user_id, receiver_id=None):
    if receiver_id is None:
        return fetch_all("SELECT * FROM received_files WHERE sender_id = ? ORDER BY id DESC", (user_id,))
    return fetch_all(
        "SELECT * FROM received_files WHERE sender_id = ? AND receiver_id = ? ORDER BY id DESC",
        (user_id, receiver_id),
    )

def all_files(user_id):
    return fetch_all("SELECT * FROM received_files WHERE receiver_id = ? OR sender_id = ? ORDER BY id DESC", (user_id, user_id))


def delete_file(file_id):
    execute_query("DELETE FROM received_files WHERE id = ?", (file_id,))


def received_file_exists(sender_id, receiver_id, file_name):
    return fetch_one(
        """
        SELECT id
        FROM received_files
        WHERE sender_id = ?
          AND receiver_id = ?
          AND file_name = ?
        """,
        (sender_id, receiver_id, file_name),
    )

init_db()
