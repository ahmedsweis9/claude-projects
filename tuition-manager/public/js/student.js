const params = new URLSearchParams(location.search);
const sid = params.get('id');
const today = new Date().toISOString().split('T')[0];

let studentData = null;

if (!sid) { location.href = '/students.html'; }

async function load() {
  const [student, payments, attendance] = await Promise.all([
    fetch(`/api/students/${sid}`).then(r => r.json()),
    fetch(`/api/students/${sid}/payments`).then(r => r.json()),
    fetch(`/api/students/${sid}/attendance`).then(r => r.json()),
  ]);

  studentData = student;
  renderProfile(student);
  renderPayments(payments, student);
  renderAttendance(attendance);
}

function renderProfile(s) {
  const section = s.section ? ` · ${capitalize(s.section)} class` : '';
  document.title = `${s.name} — Tuition Manager`;
  document.getElementById('student-name').textContent = s.name;
  document.getElementById('student-meta').textContent =
    `Grade ${s.grade}${section} · ${s.active ? 'Active' : 'Archived'} · ${s.amount_due} OMR/month`;

  document.getElementById('d-phone').textContent        = s.phone || '—';
  document.getElementById('d-whatsapp').textContent     = s.whatsapp || '—';
  document.getElementById('d-parent-name').textContent  = s.parent_name || '—';
  document.getElementById('d-parent-phone').textContent = s.parent_phone || '—';
  document.getElementById('d-parent-wa').textContent    = s.parent_whatsapp || '—';
  document.getElementById('d-enrolled').textContent     = s.enrollment_date;
}

function renderPayments(payments, student) {
  const tbody = document.getElementById('payments-tbody');
  if (!payments.length) {
    tbody.innerHTML = `<tr><td colspan="6"><div class="empty">
      <div class="empty-icon">&#128179;</div>
      <h3>No payments recorded</h3>
      <p>Use "Record Payment" to add one.</p>
    </div></td></tr>`;
    return;
  }
  tbody.innerHTML = payments.map(p => {
    const paid    = p.amount_paid >= p.amount_due;
    const partial = p.amount_paid > 0 && !paid;
    const badge   = paid
      ? '<span class="badge badge-green">Paid</span>'
      : partial
        ? '<span class="badge badge-amber">Partial</span>'
        : '<span class="badge badge-red">Unpaid</span>';
    return `<tr class="${paid ? 'row-paid' : partial ? 'row-partial' : 'row-unpaid'}">
      <td>${fmtMonth(p.month)}</td>
      <td>${p.amount_due.toFixed(3)} OMR</td>
      <td>${p.amount_paid.toFixed(3)} OMR</td>
      <td>${p.payment_date || '—'}</td>
      <td>${badge}</td>
      <td>${p.notes || '—'}</td>
    </tr>`;
  }).join('');
}

function renderAttendance(records) {
  const tbody = document.getElementById('attendance-tbody');
  if (!records.length) {
    tbody.innerHTML = `<tr><td colspan="4"><div class="empty">
      <div class="empty-icon">&#128197;</div>
      <h3>No attendance recorded</h3>
    </div></td></tr>`;
    return;
  }
  tbody.innerHTML = records.map(r => {
    const badge = r.status === 'present'
      ? '<span class="badge badge-green">Present</span>'
      : r.status === 'absent'
        ? '<span class="badge badge-red">Absent</span>'
        : '<span class="badge badge-amber">Excused</span>';
    return `<tr>
      <td>${r.session_date}</td>
      <td>Session ${r.session_number}</td>
      <td>${r.duration_hours}h</td>
      <td>${badge}</td>
    </tr>`;
  }).join('');
}

// ── Edit Modal ────────────────────────────────────────────────────────────────

function openEditModal() {
  const s = studentData;
  document.getElementById('ef-name').value           = s.name;
  document.getElementById('ef-grade').value          = s.grade;
  document.getElementById('ef-enrollment').value     = s.enrollment_date;
  document.getElementById('ef-phone').value          = s.phone || '';
  document.getElementById('ef-whatsapp').value       = s.whatsapp || '';
  document.getElementById('ef-parent-name').value    = s.parent_name || '';
  document.getElementById('ef-parent-phone').value   = s.parent_phone || '';
  document.getElementById('ef-parent-whatsapp').value= s.parent_whatsapp || '';
  document.getElementById('ef-active').value         = s.active;
  const g11 = String(s.grade) === '11';
  document.getElementById('ef-section-group').style.display = g11 ? '' : 'none';
  if (g11) document.getElementById('ef-section').value = s.section || 'boys';
  document.getElementById('edit-modal').classList.add('open');
}

function closeEdit() { document.getElementById('edit-modal').classList.remove('open'); }

function onEditGradeChange() {
  const g = document.getElementById('ef-grade').value;
  document.getElementById('ef-section-group').style.display = g === '11' ? '' : 'none';
}

async function submitEdit(e) {
  e.preventDefault();
  const payload = {
    name:            document.getElementById('ef-name').value.trim(),
    grade:           document.getElementById('ef-grade').value,
    section:         document.getElementById('ef-section').value,
    phone:           document.getElementById('ef-phone').value.trim(),
    whatsapp:        document.getElementById('ef-whatsapp').value.trim(),
    parent_name:     document.getElementById('ef-parent-name').value.trim(),
    parent_phone:    document.getElementById('ef-parent-phone').value.trim(),
    parent_whatsapp: document.getElementById('ef-parent-whatsapp').value.trim(),
    enrollment_date: document.getElementById('ef-enrollment').value,
    active:          document.getElementById('ef-active').value,
  };
  await fetch(`/api/students/${sid}`, {
    method: 'PUT',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });
  closeEdit();
  load();
}

// ── Payment Modal ─────────────────────────────────────────────────────────────

function openPaymentModal() {
  const currentMonth = today.slice(0, 7);
  document.getElementById('pf-month').value  = currentMonth;
  document.getElementById('pf-date').value   = today;
  document.getElementById('pf-amount').value = studentData ? studentData.amount_due : '';
  document.getElementById('pf-notes').value  = '';
  if (studentData) {
    document.getElementById('pf-due-info').textContent =
      `Monthly fee for Grade ${studentData.grade}: ${studentData.amount_due} OMR`;
  }
  document.getElementById('payment-modal').classList.add('open');
}

function closePayment() { document.getElementById('payment-modal').classList.remove('open'); }

async function submitPayment(e) {
  e.preventDefault();
  await fetch('/api/payments', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({
      student_id:   sid,
      month:        document.getElementById('pf-month').value,
      amount_paid:  document.getElementById('pf-amount').value,
      payment_date: document.getElementById('pf-date').value,
      notes:        document.getElementById('pf-notes').value.trim(),
    })
  });
  closePayment();
  load();
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtMonth(m) {
  const [y, mo] = m.split('-');
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${months[parseInt(mo) - 1]} ${y}`;
}

function capitalize(s) { return s ? s[0].toUpperCase() + s.slice(1) : ''; }

load();
