import sqlite3
import os

DB_NAME = "users.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists(DB_NAME):
        conn = get_db_connection()
        conn.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT,
                email TEXT UNIQUE,
                password TEXT
            );
        ''')
        # Legg inn adminbruker
        conn.execute('''
            INSERT INTO users (company_name, email, password)
            VALUES (?, ?, ?)
        ''', ("Admin", "admin@klimaregnskap.no", "hemmeligadmin"))
        conn.commit()
        conn.close()
