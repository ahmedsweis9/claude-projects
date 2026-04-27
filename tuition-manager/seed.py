from database import get_db, init_db

init_db()
with get_db() as conn:
    students = [
        ('Ali Hassan',   5,  None,    '9512 3001', None,         'Hassan Ali',   '9512 1001', None,         '2026-01-10'),
        ('Sara Ahmed',   8,  None,    '9512 3002', None,         'Ahmed Ali',    '9512 1002', None,         '2026-02-01'),
        ('Khalid Nasser',11, 'boys',  '9512 3003', None,         'Nasser Khalid','9512 1003', None,         '2026-01-15'),
        ('Fatima Omar',  11, 'girls', '9512 3004', None,         'Omar Said',    '9512 1004', None,         '2026-01-20'),
        ('Yousef Salim', 12, None,    '9512 3005', None,         'Salim Hassan', '9512 1005', None,         '2025-09-01'),
    ]
    for s in students:
        conn.execute(
            "INSERT INTO students (name,grade,section,phone,whatsapp,parent_name,parent_phone,parent_whatsapp,enrollment_date,active) "
            "VALUES (?,?,?,?,?,?,?,?,?,1)", s
        )
    count = conn.execute('SELECT COUNT(*) FROM students').fetchone()[0]
    print(f'Students in DB: {count}')
