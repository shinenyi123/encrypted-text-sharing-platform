import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL")

def connect_db():
    if DATABASE_URL:
        return psycopg2.connect(
            DATABASE_URL,
            cursor_factory=RealDictCursor,
        )
    else:
        return psycopg2.connect(
            host="localhost",
            database="encrypt_text_web_db",
            user="postgres",
            password="12345678",
            cursor_factory=RealDictCursor,
        )


def init_db():
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

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
            return row


def fetch_one(query, values=()):
    postgres_query = query.replace("?", "%s")
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(postgres_query, values)
            return cursor.fetchone()


def fetch_all(query, values=()):
    postgres_query = query.replace("?", "%s")
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(postgres_query, values)
            return cursor.fetchall()


def fetch_user(email):
    return fetch_one("SELECT * FROM users WHERE email = ?", (email,))


def insert_user(data):
    execute_query("INSERT INTO users (email, password_hash) VALUES (?, ?)", data)


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

            return cur.fetchall()


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
