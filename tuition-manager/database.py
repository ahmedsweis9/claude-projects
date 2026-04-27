import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'tuition.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS students (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                name             TEXT    NOT NULL,
                grade            INTEGER NOT NULL CHECK(grade BETWEEN 5 AND 12),
                section          TEXT    CHECK(section IN ('boys','girls') OR section IS NULL),
                phone            TEXT,
                whatsapp         TEXT,
                parent_name      TEXT,
                parent_phone     TEXT,
                parent_whatsapp  TEXT,
                enrollment_date  TEXT    NOT NULL,
                active           INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS payments (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id   INTEGER NOT NULL REFERENCES students(id),
                month        TEXT    NOT NULL,
                amount_due   REAL    NOT NULL,
                amount_paid  REAL    NOT NULL DEFAULT 0,
                payment_date TEXT,
                notes        TEXT
            );

            CREATE TABLE IF NOT EXISTS attendance (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id     INTEGER NOT NULL REFERENCES students(id),
                session_date   TEXT    NOT NULL,
                session_number INTEGER NOT NULL DEFAULT 1,
                duration_hours REAL    NOT NULL DEFAULT 2,
                status         TEXT    NOT NULL DEFAULT 'present'
                                       CHECK(status IN ('present','absent','excused'))
            );
        """)


def monthly_fee(grade: int) -> float:
    return 50.0 if grade <= 8 else 60.0


def row_to_dict(row):
    return dict(row) if row else None


def rows_to_list(rows):
    return [dict(r) for r in rows]
