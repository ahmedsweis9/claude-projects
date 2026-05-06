import hmac
import os
import calendar
import webbrowser
from datetime import date
from flask import Flask, jsonify, request, send_from_directory, session, redirect, Response
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, init_db, monthly_fee, row_to_dict, rows_to_list, insert_returning_id, IGNORE, CONFLICT_IGNORE

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def calc_due_day(enrollment_date_str: str, year: int, month: int) -> int:
    enroll_day = int(enrollment_date_str.split('-')[2])
    last_day = calendar.monthrange(year, month)[1]
    return min(enroll_day, last_day)


def annotate_due(students: list, month_str: str) -> list:
    today = date.today()
    current_month = today.strftime('%Y-%m')
    y, m = map(int, month_str.split('-'))
    for s in students:
        dd = calc_due_day(s['enrollment_date'], y, m)
        s['due_day'] = dd
        s['due_date'] = f"{month_str}-{str(dd).zfill(2)}"
        s['not_yet_due'] = (month_str == current_month) and (today.day < dd)
    return students


def uid():
    return session.get('user_id')


app = Flask(__name__, static_folder='public', static_url_path='')
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')

init_db()

_OPEN_PREFIXES = ('/login.html', '/signup.html', '/api/login', '/api/signup', '/css/', '/js/auth.js')


@app.before_request
def require_login():
    if any(request.path == p or request.path.startswith(p) for p in _OPEN_PREFIXES):
        return
    if not session.get('user_id'):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Unauthorized'}), 401
        return redirect('/login.html')


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route('/api/signup', methods=['POST'])
def signup():
    d = request.json or {}
    name     = d.get('name', '').strip()
    email    = d.get('email', '').strip().lower()
    password = d.get('password', '')
    if not name or not email or not password:
        return jsonify({'error': 'All fields are required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    pw_hash = generate_password_hash(password)
    with get_db() as conn:
        if conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
            return jsonify({'error': 'Email already registered'}), 400
        user_id = insert_returning_id(conn,
            "INSERT INTO users (name, email, password) VALUES (?,?,?)",
            (name, email, pw_hash)
        )
    session['user_id']   = user_id
    session['user_name'] = name
    return jsonify({'ok': True, 'name': name})


@app.route('/api/login', methods=['POST'])
def login():
    d = request.json or {}
    email    = d.get('email', '').strip().lower()
    password = d.get('password', '')
    with get_db() as conn:
        user = row_to_dict(conn.execute(
            "SELECT * FROM users WHERE email=?", (email,)
        ).fetchone())
    if not user or not check_password_hash(user['password'], password):
        return jsonify({'error': 'Invalid email or password'}), 401
    session['user_id']   = user['id']
    session['user_name'] = user['name']
    return jsonify({'ok': True, 'name': user['name']})


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})


@app.route('/api/me')
def me():
    user = None
    with get_db() as conn:
        user = row_to_dict(conn.execute(
            "SELECT id, name, email FROM users WHERE id=?", (uid(),)
        ).fetchone())
    return jsonify(user or {})


# ── Static pages ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('public', path)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route('/api/dashboard')
def dashboard():
    month   = request.args.get('month', date.today().strftime('%Y-%m'))
    user_id = uid()
    with get_db() as conn:
        total_students = conn.execute(
            "SELECT COUNT(*) FROM students WHERE active=1 AND user_id=?", (user_id,)
        ).fetchone()[0]

        expected = conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN grade<=8 THEN 50 ELSE 60 END),0) "
            "FROM students WHERE active=1 AND user_id=?", (user_id,)
        ).fetchone()[0]

        collected = conn.execute(
            "SELECT COALESCE(SUM(p.amount_paid),0) FROM payments p "
            "JOIN students s ON s.id=p.student_id "
            "WHERE p.month=? AND s.active=1 AND s.user_id=?",
            (month, user_id)
        ).fetchone()[0]

        candidates = rows_to_list(conn.execute("""
            SELECT s.id, s.name, s.grade, s.section,
                   s.enrollment_date, s.parent_phone, s.parent_whatsapp,
                   COALESCE(p.amount_paid, 0) AS amount_paid,
                   CASE WHEN s.grade<=8 THEN 50 ELSE 60 END AS amount_due
            FROM students s
            LEFT JOIN payments p ON p.student_id=s.id AND p.month=?
            WHERE s.active=1 AND s.user_id=?
              AND (p.id IS NULL OR p.amount_paid < (CASE WHEN s.grade<=8 THEN 50 ELSE 60 END))
            ORDER BY s.grade, s.name
        """, (month, user_id)).fetchall())

        annotate_due(candidates, month)
        unpaid = [s for s in candidates if not s['not_yet_due']]

    return jsonify({
        'month': month,
        'total_students': total_students,
        'expected_revenue': expected,
        'collected': collected,
        'outstanding': round(expected - collected, 2),
        'unpaid': unpaid
    })


# ── Students ──────────────────────────────────────────────────────────────────

@app.route('/api/students', methods=['GET'])
def list_students():
    grade   = request.args.get('grade')
    section = request.args.get('section')
    active  = request.args.get('active', '1')
    search  = request.args.get('search', '').strip()
    month   = request.args.get('month', date.today().strftime('%Y-%m'))
    user_id = uid()

    query = """
        SELECT s.*,
               COALESCE(p.amount_paid, 0) AS paid_this_month,
               CASE WHEN s.grade<=8 THEN 50 ELSE 60 END AS amount_due
        FROM students s
        LEFT JOIN payments p ON p.student_id=s.id AND p.month=?
        WHERE s.user_id=?
    """
    params = [month, user_id]

    if active != 'all':
        query += " AND s.active=?"
        params.append(int(active))
    if grade:
        query += " AND s.grade=?"
        params.append(int(grade))
    if section:
        query += " AND s.section=?"
        params.append(section)
    if search:
        query += " AND s.name LIKE ?"
        params.append(f'%{search}%')

    query += " ORDER BY s.grade, s.name"

    with get_db() as conn:
        students = rows_to_list(conn.execute(query, params).fetchall())

    annotate_due(students, month)
    return jsonify(students)


@app.route('/api/students', methods=['POST'])
def create_student():
    d       = request.json
    grade   = int(d['grade'])
    section = d.get('section')
    user_id = uid()
    with get_db() as conn:
        student_id = insert_returning_id(conn, """
            INSERT INTO students
              (user_id, name, grade, section, phone, whatsapp,
               parent_name, parent_phone, parent_whatsapp, enrollment_date, active)
            VALUES (?,?,?,?,?,?,?,?,?,?,1)
        """, (
            user_id, d['name'], grade, section,
            d.get('phone'), d.get('whatsapp'),
            d.get('parent_name'), d.get('parent_phone'), d.get('parent_whatsapp'),
            d.get('enrollment_date', date.today().isoformat())
        ))
        student = row_to_dict(conn.execute(
            "SELECT * FROM students WHERE id=?", (student_id,)
        ).fetchone())
    return jsonify(student), 201


@app.route('/api/students/<int:sid>', methods=['GET'])
def get_student(sid):
    user_id = uid()
    with get_db() as conn:
        student = row_to_dict(conn.execute(
            "SELECT * FROM students WHERE id=? AND user_id=?", (sid, user_id)
        ).fetchone())
    if not student:
        return jsonify({'error': 'Not found'}), 404
    student['amount_due'] = monthly_fee(student['grade'])
    return jsonify(student)


@app.route('/api/students/<int:sid>', methods=['PUT'])
def update_student(sid):
    d       = request.json
    grade   = int(d['grade'])
    section = d.get('section')
    user_id = uid()
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM students WHERE id=? AND user_id=?", (sid, user_id)
        ).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        conn.execute("""
            UPDATE students SET
              name=?, grade=?, section=?, phone=?, whatsapp=?,
              parent_name=?, parent_phone=?, parent_whatsapp=?,
              enrollment_date=?, active=?
            WHERE id=?
        """, (
            d['name'], grade, section,
            d.get('phone'), d.get('whatsapp'),
            d.get('parent_name'), d.get('parent_phone'), d.get('parent_whatsapp'),
            d.get('enrollment_date'), int(d.get('active', 1)),
            sid
        ))
        student = row_to_dict(conn.execute(
            "SELECT * FROM students WHERE id=?", (sid,)
        ).fetchone())
    return jsonify(student)


# ── Payments ──────────────────────────────────────────────────────────────────

@app.route('/api/students/<int:sid>/payments', methods=['GET'])
def student_payments(sid):
    user_id = uid()
    with get_db() as conn:
        if not conn.execute("SELECT id FROM students WHERE id=? AND user_id=?", (sid, user_id)).fetchone():
            return jsonify({'error': 'Not found'}), 404
        rows = rows_to_list(conn.execute(
            "SELECT * FROM payments WHERE student_id=? ORDER BY month DESC", (sid,)
        ).fetchall())
    return jsonify(rows)


@app.route('/api/payments', methods=['GET'])
def list_payments():
    month   = request.args.get('month', date.today().strftime('%Y-%m'))
    user_id = uid()
    with get_db() as conn:
        rows = rows_to_list(conn.execute("""
            SELECT p.*, s.name, s.grade, s.section,
                   CASE WHEN s.grade<=8 THEN 50 ELSE 60 END AS amount_due_calc
            FROM payments p
            JOIN students s ON s.id=p.student_id
            WHERE p.month=? AND s.user_id=?
            ORDER BY s.grade, s.name
        """, (month, user_id)).fetchall())
    return jsonify(rows)


@app.route('/api/payments', methods=['POST'])
def record_payment():
    d       = request.json
    sid     = int(d['student_id'])
    month   = d['month']
    amount_paid = float(d['amount_paid'])
    user_id = uid()

    with get_db() as conn:
        student = conn.execute(
            "SELECT grade FROM students WHERE id=? AND user_id=?", (sid, user_id)
        ).fetchone()
        if not student:
            return jsonify({'error': 'Student not found'}), 404

        fee = monthly_fee(student['grade'])
        existing = conn.execute(
            "SELECT id FROM payments WHERE student_id=? AND month=?", (sid, month)
        ).fetchone()

        if existing:
            conn.execute("""
                UPDATE payments SET amount_paid=?, payment_date=?, notes=? WHERE id=?
            """, (amount_paid, d.get('payment_date', date.today().isoformat()),
                  d.get('notes'), existing['id']))
            payment_id = existing['id']
        else:
            payment_id = insert_returning_id(conn, """
                INSERT INTO payments (student_id, month, amount_due, amount_paid, payment_date, notes)
                VALUES (?,?,?,?,?,?)
            """, (sid, month, fee, amount_paid,
                  d.get('payment_date', date.today().isoformat()), d.get('notes')))

        payment = row_to_dict(conn.execute(
            "SELECT * FROM payments WHERE id=?", (payment_id,)
        ).fetchone())

    return jsonify(payment), 201


# ── Attendance ────────────────────────────────────────────────────────────────

@app.route('/api/students/<int:sid>/attendance', methods=['GET'])
def student_attendance(sid):
    user_id = uid()
    with get_db() as conn:
        if not conn.execute("SELECT id FROM students WHERE id=? AND user_id=?", (sid, user_id)).fetchone():
            return jsonify({'error': 'Not found'}), 404
        rows = rows_to_list(conn.execute(
            "SELECT * FROM attendance WHERE student_id=? ORDER BY session_date DESC, session_number",
            (sid,)
        ).fetchall())
    return jsonify(rows)


@app.route('/api/attendance', methods=['GET'])
def list_attendance():
    session_date = request.args.get('date', date.today().isoformat())
    grade        = request.args.get('grade')
    user_id      = uid()

    query = """
        SELECT a.*, s.name, s.grade, s.section
        FROM attendance a
        JOIN students s ON s.id=a.student_id
        WHERE a.session_date=? AND s.user_id=?
    """
    params = [session_date, user_id]
    if grade:
        query += " AND s.grade=?"
        params.append(int(grade))
    query += " ORDER BY s.name"

    with get_db() as conn:
        rows = rows_to_list(conn.execute(query, params).fetchall())
    return jsonify(rows)


@app.route('/api/attendance', methods=['POST'])
def record_attendance():
    records = request.json
    if not isinstance(records, list):
        records = [records]
    user_id = uid()

    saved = []
    with get_db() as conn:
        for r in records:
            sid   = int(r['student_id'])
            sdate = r['session_date']
            snum  = int(r.get('session_number', 1))

            if not conn.execute("SELECT id FROM students WHERE id=? AND user_id=?", (sid, user_id)).fetchone():
                continue

            existing = conn.execute(
                "SELECT id FROM attendance WHERE student_id=? AND session_date=? AND session_number=?",
                (sid, sdate, snum)
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE attendance SET status=?, duration_hours=? WHERE id=?",
                    (r.get('status', 'present'), float(r.get('duration_hours', 2)), existing['id'])
                )
                aid = existing['id']
            else:
                aid = insert_returning_id(conn, """
                    INSERT INTO attendance (student_id, session_date, session_number, duration_hours, status)
                    VALUES (?,?,?,?,?)
                """, (sid, sdate, snum, float(r.get('duration_hours', 2)), r.get('status', 'present')))

            saved.append(row_to_dict(conn.execute(
                "SELECT * FROM attendance WHERE id=?", (aid,)
            ).fetchone()))

    return jsonify(saved), 201


@app.route('/api/attendance/session', methods=['GET'])
def get_session_students():
    grade          = request.args.get('grade')
    section        = request.args.get('section')
    session_date   = request.args.get('date', date.today().isoformat())
    session_number = request.args.get('session_number', 1)
    user_id        = uid()

    with get_db() as conn:
        if not grade:
            return jsonify([])

        query  = "SELECT id, name, grade, section FROM students WHERE active=1 AND user_id=? AND grade=?"
        params = [user_id, int(grade)]
        if section:
            query += " AND section=?"
            params.append(section)
        query += " ORDER BY name"
        students = rows_to_list(conn.execute(query, params).fetchall())

        if students:
            ids = tuple(s['id'] for s in students)
            placeholders = ','.join('?' * len(ids))
            existing = {
                r['student_id']: r['status']
                for r in rows_to_list(conn.execute(
                    f"SELECT student_id, status FROM attendance "
                    f"WHERE session_date=? AND session_number=? AND student_id IN ({placeholders})",
                    (session_date, int(session_number)) + ids
                ).fetchall())
            }
            for s in students:
                s['existing_status'] = existing.get(s['id'])

    return jsonify(students)


# ── Data export / import ──────────────────────────────────────────────────────

@app.route('/api/admin/export')
def export_data():
    import json
    user_id = uid()
    with get_db() as conn:
        students = rows_to_list(conn.execute(
            "SELECT * FROM students WHERE user_id=?", (user_id,)
        ).fetchall())
        student_ids = [s['id'] for s in students]
        payments = attendance = []
        if student_ids:
            ph = ','.join('?' * len(student_ids))
            payments   = rows_to_list(conn.execute(f"SELECT * FROM payments WHERE student_id IN ({ph})", student_ids).fetchall())
            attendance = rows_to_list(conn.execute(f"SELECT * FROM attendance WHERE student_id IN ({ph})", student_ids).fetchall())
        data = {'students': students, 'payments': payments, 'attendance': attendance}
    return Response(
        json.dumps(data, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': 'attachment; filename=tuition-backup.json'}
    )


@app.route('/api/admin/import', methods=['POST'])
def import_data():
    data    = request.json or {}
    user_id = uid()
    with get_db() as conn:
        id_map = {}
        for s in data.get('students', []):
            existing = conn.execute(
                "SELECT id FROM students WHERE user_id=? AND name=? AND enrollment_date=?",
                (user_id, s['name'], s['enrollment_date'])
            ).fetchone()
            if existing:
                id_map[s['id']] = existing['id']
                continue
            id_map[s['id']] = insert_returning_id(conn, """
                INSERT INTO students
                  (user_id, name, grade, section, phone, whatsapp,
                   parent_name, parent_phone, parent_whatsapp, enrollment_date, active)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (user_id, s['name'], s['grade'], s.get('section'),
                  s.get('phone'), s.get('whatsapp'), s.get('parent_name'),
                  s.get('parent_phone'), s.get('parent_whatsapp'),
                  s['enrollment_date'], s.get('active', 1)))

        for p in data.get('payments', []):
            new_sid = id_map.get(p['student_id'])
            if not new_sid:
                continue
            conn.execute(f"""
                INSERT {IGNORE} INTO payments
                  (student_id, month, amount_due, amount_paid, payment_date, notes)
                VALUES (?,?,?,?,?,?)
                {CONFLICT_IGNORE}
            """, (new_sid, p['month'], p['amount_due'], p['amount_paid'],
                  p.get('payment_date'), p.get('notes')))

        for a in data.get('attendance', []):
            new_sid = id_map.get(a['student_id'])
            if not new_sid:
                continue
            conn.execute(f"""
                INSERT {IGNORE} INTO attendance
                  (student_id, session_date, session_number, duration_hours, status)
                VALUES (?,?,?,?,?)
                {CONFLICT_IGNORE}
            """, (new_sid, a['session_date'], a['session_number'],
                  a['duration_hours'], a['status']))

    return jsonify({'ok': True, 'imported': {
        'students':   len(data.get('students', [])),
        'payments':   len(data.get('payments', [])),
        'attendance': len(data.get('attendance', [])),
    }})


if __name__ == '__main__':
    port     = int(os.environ.get('PORT', 3000))
    is_local = 'PORT' not in os.environ
    if is_local:
        webbrowser.open(f'http://localhost:{port}')
    app.run(host='0.0.0.0', port=port, debug=is_local)
