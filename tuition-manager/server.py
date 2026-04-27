import os
import webbrowser
from datetime import date
from flask import Flask, jsonify, request, send_from_directory
from database import get_db, init_db, monthly_fee, row_to_dict, rows_to_list

app = Flask(__name__, static_folder='public', static_url_path='')

# ── Static pages ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('public', path)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route('/api/dashboard')
def dashboard():
    month = request.args.get('month', date.today().strftime('%Y-%m'))
    with get_db() as conn:
        total_students = conn.execute(
            "SELECT COUNT(*) FROM students WHERE active=1"
        ).fetchone()[0]

        expected = conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN grade<=8 THEN 50 ELSE 60 END),0) "
            "FROM students WHERE active=1"
        ).fetchone()[0]

        collected = conn.execute(
            "SELECT COALESCE(SUM(p.amount_paid),0) FROM payments p "
            "JOIN students s ON s.id=p.student_id "
            "WHERE p.month=? AND s.active=1",
            (month,)
        ).fetchone()[0]

        # Students with no fully-paid record this month
        unpaid = rows_to_list(conn.execute("""
            SELECT s.id, s.name, s.grade, s.section,
                   s.parent_phone, s.parent_whatsapp,
                   COALESCE(p.amount_paid, 0) AS amount_paid,
                   CASE WHEN s.grade<=8 THEN 50 ELSE 60 END AS amount_due
            FROM students s
            LEFT JOIN payments p ON p.student_id=s.id AND p.month=?
            WHERE s.active=1
              AND (p.id IS NULL OR p.amount_paid < (CASE WHEN s.grade<=8 THEN 50 ELSE 60 END))
            ORDER BY s.grade, s.name
        """, (month,)).fetchall())

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
    grade = request.args.get('grade')
    section = request.args.get('section')
    active = request.args.get('active', '1')
    search = request.args.get('search', '').strip()
    month = request.args.get('month', date.today().strftime('%Y-%m'))

    query = """
        SELECT s.*,
               COALESCE(p.amount_paid, 0) AS paid_this_month,
               CASE WHEN s.grade<=8 THEN 50 ELSE 60 END AS amount_due
        FROM students s
        LEFT JOIN payments p ON p.student_id=s.id AND p.month=?
        WHERE 1=1
    """
    params = [month]

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

    return jsonify(students)


@app.route('/api/students', methods=['POST'])
def create_student():
    d = request.json
    grade = int(d['grade'])
    section = d.get('section') if grade == 11 else None
    with get_db() as conn:
        cur = conn.execute("""
            INSERT INTO students
              (name, grade, section, phone, whatsapp,
               parent_name, parent_phone, parent_whatsapp, enrollment_date, active)
            VALUES (?,?,?,?,?,?,?,?,?,1)
        """, (
            d['name'], grade, section,
            d.get('phone'), d.get('whatsapp'),
            d.get('parent_name'), d.get('parent_phone'), d.get('parent_whatsapp'),
            d.get('enrollment_date', date.today().isoformat())
        ))
        student_id = cur.lastrowid
        student = row_to_dict(conn.execute(
            "SELECT * FROM students WHERE id=?", (student_id,)
        ).fetchone())
    return jsonify(student), 201


@app.route('/api/students/<int:sid>', methods=['GET'])
def get_student(sid):
    with get_db() as conn:
        student = row_to_dict(conn.execute(
            "SELECT * FROM students WHERE id=?", (sid,)
        ).fetchone())
    if not student:
        return jsonify({'error': 'Not found'}), 404
    student['amount_due'] = monthly_fee(student['grade'])
    return jsonify(student)


@app.route('/api/students/<int:sid>', methods=['PUT'])
def update_student(sid):
    d = request.json
    grade = int(d['grade'])
    section = d.get('section') if grade == 11 else None
    with get_db() as conn:
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
    with get_db() as conn:
        rows = rows_to_list(conn.execute(
            "SELECT * FROM payments WHERE student_id=? ORDER BY month DESC",
            (sid,)
        ).fetchall())
    return jsonify(rows)


@app.route('/api/payments', methods=['GET'])
def list_payments():
    month = request.args.get('month', date.today().strftime('%Y-%m'))
    with get_db() as conn:
        rows = rows_to_list(conn.execute("""
            SELECT p.*, s.name, s.grade, s.section,
                   CASE WHEN s.grade<=8 THEN 50 ELSE 60 END AS amount_due_calc
            FROM payments p
            JOIN students s ON s.id=p.student_id
            WHERE p.month=?
            ORDER BY s.grade, s.name
        """, (month,)).fetchall())
    return jsonify(rows)


@app.route('/api/payments', methods=['POST'])
def record_payment():
    d = request.json
    sid = int(d['student_id'])
    month = d['month']
    amount_paid = float(d['amount_paid'])

    with get_db() as conn:
        student = conn.execute(
            "SELECT grade FROM students WHERE id=?", (sid,)
        ).fetchone()
        if not student:
            return jsonify({'error': 'Student not found'}), 404

        fee = monthly_fee(student['grade'])

        # Upsert: if a record exists for this month, update it
        existing = conn.execute(
            "SELECT id FROM payments WHERE student_id=? AND month=?",
            (sid, month)
        ).fetchone()

        if existing:
            conn.execute("""
                UPDATE payments
                SET amount_paid=?, payment_date=?, notes=?
                WHERE id=?
            """, (amount_paid, d.get('payment_date', date.today().isoformat()),
                  d.get('notes'), existing['id']))
            payment_id = existing['id']
        else:
            cur = conn.execute("""
                INSERT INTO payments
                  (student_id, month, amount_due, amount_paid, payment_date, notes)
                VALUES (?,?,?,?,?,?)
            """, (sid, month, fee, amount_paid,
                  d.get('payment_date', date.today().isoformat()),
                  d.get('notes')))
            payment_id = cur.lastrowid

        payment = row_to_dict(conn.execute(
            "SELECT * FROM payments WHERE id=?", (payment_id,)
        ).fetchone())

    return jsonify(payment), 201


# ── Attendance ────────────────────────────────────────────────────────────────

@app.route('/api/students/<int:sid>/attendance', methods=['GET'])
def student_attendance(sid):
    with get_db() as conn:
        rows = rows_to_list(conn.execute(
            "SELECT * FROM attendance WHERE student_id=? ORDER BY session_date DESC, session_number",
            (sid,)
        ).fetchall())
    return jsonify(rows)


@app.route('/api/attendance', methods=['GET'])
def list_attendance():
    session_date = request.args.get('date', date.today().isoformat())
    grade = request.args.get('grade')

    query = """
        SELECT a.*, s.name, s.grade, s.section
        FROM attendance a
        JOIN students s ON s.id=a.student_id
        WHERE a.session_date=?
    """
    params = [session_date]
    if grade:
        query += " AND s.grade=?"
        params.append(int(grade))
    query += " ORDER BY s.name"

    with get_db() as conn:
        rows = rows_to_list(conn.execute(query, params).fetchall())
    return jsonify(rows)


@app.route('/api/attendance', methods=['POST'])
def record_attendance():
    """
    Accepts a list of attendance records:
    [{ student_id, session_date, session_number, duration_hours, status }, ...]
    """
    records = request.json
    if not isinstance(records, list):
        records = [records]

    saved = []
    with get_db() as conn:
        for r in records:
            sid = int(r['student_id'])
            sdate = r['session_date']
            snum = int(r.get('session_number', 1))

            existing = conn.execute(
                "SELECT id FROM attendance WHERE student_id=? AND session_date=? AND session_number=?",
                (sid, sdate, snum)
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE attendance SET status=?, duration_hours=? WHERE id=?",
                    (r.get('status', 'present'), float(r.get('duration_hours', 2)),
                     existing['id'])
                )
                aid = existing['id']
            else:
                cur = conn.execute("""
                    INSERT INTO attendance
                      (student_id, session_date, session_number, duration_hours, status)
                    VALUES (?,?,?,?,?)
                """, (sid, sdate, snum,
                      float(r.get('duration_hours', 2)),
                      r.get('status', 'present')))
                aid = cur.lastrowid

            saved.append(row_to_dict(conn.execute(
                "SELECT * FROM attendance WHERE id=?", (aid,)
            ).fetchone()))

    return jsonify(saved), 201


@app.route('/api/attendance/session', methods=['GET'])
def get_session_students():
    """Return students for a grade so the attendance page can build a checklist."""
    grade = request.args.get('grade')
    session_date = request.args.get('date', date.today().isoformat())
    session_number = request.args.get('session_number', 1)

    with get_db() as conn:
        students = rows_to_list(conn.execute(
            "SELECT id, name, grade, section FROM students WHERE active=1 AND grade=? ORDER BY name",
            (int(grade),)
        ).fetchall()) if grade else []

        # Pull any existing attendance for this session
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


if __name__ == '__main__':
    init_db()
    webbrowser.open('http://localhost:3000')
    app.run(port=3000, debug=False)
