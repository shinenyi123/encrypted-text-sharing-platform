import os
import psycopg2
from psycopg2.extras import RealDictCursor


def connect_db():
    return psycopg2.connect(
        os.environ.get("DATABASE_URL"),
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
                CREATE TABLE IF NOT EXISTS files (
                    id SERIAL PRIMARY KEY,
                    owner_id INTEGER NOT NULL,
                    file_name TEXT NOT NULL,
                    encrypted_content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(owner_id, file_name),
                    FOREIGN KEY(owner_id) REFERENCES users(id) ON DELETE CASCADE
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
                    UNIQUE(receiver_id, file_name),
                    FOREIGN KEY(receiver_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY(sender_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
        conn.commit()


def execute_query(query, values=()):
    postgres_query = query.replace("?", "%s")
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(postgres_query, values)
            conn.commit()
            return cursor


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


def fetch_user_by_id(user_id):
    return fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))


def insert_user(data):
    execute_query("INSERT INTO users (email, password_hash) VALUES (?, ?)", data)


def insert_file(data):
    cursor = execute_query(
        "INSERT INTO files (owner_id, file_name, encrypted_content) VALUES (?, ?, ?) RETURNING id",
        data,
    )
    row = cursor.fetchone()
    return row["id"] if row else None


def get_user_files(user_id):
    return fetch_all("SELECT * FROM files WHERE owner_id = ? ORDER BY id DESC", (user_id,))


def fetch_file_by_id(file_id, user_id=None):
    if user_id is None:
        return fetch_one("SELECT * FROM files WHERE id = ?", (file_id,))
    return fetch_one("SELECT * FROM files WHERE id = ? AND owner_id = ?", (file_id, user_id))


def fetch_received_file_by_id(file_id, user_id=None):
    if user_id is None:
        return fetch_one("SELECT * FROM received_files WHERE id = ?", (file_id,))
    return fetch_one("SELECT * FROM received_files WHERE id = ? AND receiver_id = ?", (file_id, user_id))


def insert_received_file(data):
    cursor = execute_query(
        "INSERT INTO received_files (receiver_id, sender_id, file_name, encrypted_content) VALUES (?, ?, ?, ?) RETURNING id",
        data,
    )
    row = cursor.fetchone()
    return row["id"] if row else None


def get_received_files(user_id):
    return fetch_all("SELECT * FROM received_files WHERE receiver_id = ? ORDER BY id DESC", (user_id,))


def get_decrypted_file_content(file_id, user_id):
    file_row = fetch_file_by_id(file_id, user_id)

    if file_row:
        return file_row["encrypted_content"]
    return None


def delete_save_file(file_id, user_id):
    execute_query("DELETE FROM files WHERE id = ? AND owner_id = ?", (file_id, user_id))


def delete_transfer_file(file_id, user_id):
    execute_query("DELETE FROM received_files WHERE id = ? AND receiver_id = ?", (file_id, user_id))


init_db()