import os

DATABASE_URL = os.environ.get('DATABASE_URL')
IS_PG = bool(DATABASE_URL)

# ── PostgreSQL mode (Railway) ─────────────────────────────────────────────────
if IS_PG:
    import psycopg2
    import psycopg2.extras

    IGNORE = ''
    CONFLICT_IGNORE = 'ON CONFLICT DO NOTHING'

    class _Conn:
        def __init__(self, conn):
            self._conn = conn

        def execute(self, sql, params=()):
            cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql.replace('?', '%s'), params)
            return cur

        def __enter__(self):
            return self

        def __exit__(self, exc_type, *_):
            (self._conn.rollback if exc_type else self._conn.commit)()
            self._conn.close()

    def get_db():
        return _Conn(psycopg2.connect(DATABASE_URL))

    def init_db():
        with get_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id         SERIAL PRIMARY KEY,
                    name       TEXT   NOT NULL,
                    email      TEXT   NOT NULL UNIQUE,
                    password   TEXT   NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    id              SERIAL PRIMARY KEY,
                    user_id         INTEGER REFERENCES users(id),
                    name            TEXT    NOT NULL,
                    grade           INTEGER NOT NULL CHECK(grade BETWEEN 5 AND 12),
                    section         TEXT    CHECK(section IN ('boys','girls') OR section IS NULL),
                    phone           TEXT,
                    whatsapp        TEXT,
                    parent_name     TEXT,
                    parent_phone    TEXT,
                    parent_whatsapp TEXT,
                    enrollment_date TEXT    NOT NULL,
                    active          INTEGER NOT NULL DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id           SERIAL PRIMARY KEY,
                    student_id   INTEGER NOT NULL REFERENCES students(id),
                    month        TEXT    NOT NULL,
                    amount_due   FLOAT   NOT NULL,
                    amount_paid  FLOAT   NOT NULL DEFAULT 0,
                    payment_date TEXT,
                    notes        TEXT,
                    UNIQUE(student_id, month)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS attendance (
                    id             SERIAL PRIMARY KEY,
                    student_id     INTEGER NOT NULL REFERENCES students(id),
                    session_date   TEXT    NOT NULL,
                    session_number INTEGER NOT NULL DEFAULT 1,
                    duration_hours FLOAT   NOT NULL DEFAULT 2,
                    status         TEXT    NOT NULL DEFAULT 'present'
                                   CHECK(status IN ('present','absent','excused')),
                    UNIQUE(student_id, session_date, session_number)
                )
            """)

    def insert_returning_id(conn, sql, params):
        return conn.execute(sql + ' RETURNING id', params).fetchone()['id']

# ── SQLite mode (local dev) ───────────────────────────────────────────────────
else:
    import sqlite3

    IGNORE = 'OR IGNORE'
    CONFLICT_IGNORE = ''

    _DB_PATH = os.environ.get(
        'DATABASE_PATH',
        os.path.join(os.path.dirname(__file__), 'data', 'tuition.db')
    )

    def get_db():
        conn = sqlite3.connect(_DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        return conn

    def init_db():
        os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
        with get_db() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT    NOT NULL,
                    email       TEXT    NOT NULL UNIQUE,
                    password    TEXT    NOT NULL,
                    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS students (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id          INTEGER REFERENCES users(id),
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
                    notes        TEXT,
                    UNIQUE(student_id, month)
                );
                CREATE TABLE IF NOT EXISTS attendance (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id     INTEGER NOT NULL REFERENCES students(id),
                    session_date   TEXT    NOT NULL,
                    session_number INTEGER NOT NULL DEFAULT 1,
                    duration_hours REAL    NOT NULL DEFAULT 2,
                    status         TEXT    NOT NULL DEFAULT 'present'
                                   CHECK(status IN ('present','absent','excused')),
                    UNIQUE(student_id, session_date, session_number)
                );
            """)
            cols = [row[1] for row in conn.execute('PRAGMA table_info(students)').fetchall()]
            if 'user_id' not in cols:
                conn.execute('ALTER TABLE students ADD COLUMN user_id INTEGER REFERENCES users(id)')

    def insert_returning_id(conn, sql, params):
        return conn.execute(sql, params).lastrowid


# ── Shared helpers ────────────────────────────────────────────────────────────

def monthly_fee(grade: int) -> float:
    return 50.0 if grade <= 8 else 60.0


def row_to_dict(row):
    return dict(row) if row else None


def rows_to_list(rows):
    return [dict(r) for r in rows] if rows else []
