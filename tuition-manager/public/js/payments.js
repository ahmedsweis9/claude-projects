const MONTHS = ['January','February','March','April','May','June',
                 'July','August','September','October','November','December'];

const urlp = new URLSearchParams(location.search);
const today = new Date().toISOString().split('T')[0];

let cur = new Date();
let year  = cur.getFullYear();
let month = cur.getMonth();

// Honor ?month= param from dashboard quick-link
if (urlp.get('month')) {
  const [y, m] = urlp.get('month').split('-').map(Number);
  year = y; month = m - 1;
}

let allRows = [];
let highlightStudentId = urlp.get('student') ? parseInt(urlp.get('student')) : null;

function monthStr() { return `${year}-${String(month + 1).padStart(2, '0')}`; }

function changeMonth(dir) {
  month += dir;
  if (month < 0)  { month = 11; year--; }
  if (month > 11) { month = 0;  year++; }
  load();
}

async function load() {
  document.getElementById('month-label').textContent = `${MONTHS[month]} ${year}`;

  // Get all active students and all payment records for this month
  const [students, payments, dash] = await Promise.all([
    fetch(`/api/students?active=1&month=${monthStr()}`).then(r => r.json()),
    fetch(`/api/payments?month=${monthStr()}`).then(r => r.json()),
    fetch(`/api/dashboard?month=${monthStr()}`).then(r => r.json()),
  ]);

  document.getElementById('stat-expected').textContent   = fmtOMR(dash.expected_revenue);
  document.getElementById('stat-collected').textContent  = fmtOMR(dash.collected);
  document.getElementById('stat-outstanding').textContent= fmtOMR(dash.outstanding);

  // Build a unified row per student
  const payMap = {};
  payments.forEach(p => { payMap[p.student_id] = p; });

  allRows = students.map(s => {
    const p = payMap[s.id];
    const paid = p && p.amount_paid >= s.amount_due;
    const partial = p && p.amount_paid > 0 && !paid;
    return {
      id:           s.id,
      name:         s.name,
      grade:        s.grade,
      section:      s.section,
      amount_due:   s.amount_due,
      amount_paid:  p ? p.amount_paid : 0,
      payment_date: p ? p.payment_date : null,
      notes:        p ? p.notes : null,
      due_date:     s.due_date,
      not_yet_due:  s.not_yet_due,
      status:       paid ? 'paid' : partial ? 'partial' : s.not_yet_due ? 'pending' : 'unpaid',
    };
  });

  applyFilter();
}

function applyFilter() {
  const filter = document.getElementById('status-filter').value;
  // 'unpaid' filter shows both unpaid and pending (not yet due) since both have no payment
  const rows = filter === 'all' ? allRows
    : filter === 'unpaid' ? allRows.filter(r => r.status === 'unpaid' || r.status === 'pending')
    : allRows.filter(r => r.status === filter);

  document.getElementById('table-title').textContent =
    `${rows.length} student${rows.length !== 1 ? 's' : ''} — ${MONTHS[month]} ${year}`;

  const tbody = document.getElementById('payments-tbody');
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="8"><div class="empty">
      <div class="empty-icon">&#128179;</div><h3>No records</h3></div></td></tr>`;
    return;
  }

  tbody.innerHTML = rows.map(r => {
    const rowCls = r.status === 'paid' ? 'row-paid'
      : r.status === 'partial' ? 'row-partial'
      : r.status === 'pending' ? ''
      : 'row-unpaid';
    const dueDay = r.due_date ? parseInt(r.due_date.split('-')[2]) : null;
    const badge = r.status === 'paid'
      ? '<span class="badge badge-green">Paid</span>'
      : r.status === 'partial'
        ? '<span class="badge badge-amber">Partial</span>'
        : r.status === 'pending'
          ? `<span class="badge badge-gray">Due ${dueDay ? 'on ' + dueDay + fmtOrdinal(dueDay) : '—'}</span>`
          : '<span class="badge badge-red">Unpaid</span>';
    const section = r.section ? ` <span class="badge badge-gray" style="font-size:10px">${capitalize(r.section)}</span>` : '';
    const highlight = highlightStudentId === r.id ? ' style="outline:2px solid #2563eb"' : '';
    return `<tr class="${rowCls}"${highlight}>
      <td><a href="/student.html?id=${r.id}">${r.name}</a></td>
      <td>Grade ${r.grade}${section}</td>
      <td>${fmtOMR(r.amount_due)}</td>
      <td>${r.amount_paid > 0 ? fmtOMR(r.amount_paid) : '—'}</td>
      <td>${r.payment_date || '—'}</td>
      <td>${badge}</td>
      <td>${r.notes || '—'}</td>
      <td class="text-right">
        ${r.status !== 'pending' || r.amount_paid > 0
          ? `<button class="btn btn-primary btn-sm" onclick='openPay(${JSON.stringify(r)})'>${r.status === 'unpaid' || r.status === 'pending' ? 'Record' : 'Update'}</button>`
          : `<button class="btn btn-outline btn-sm" onclick='openPay(${JSON.stringify(r)})'>Record early</button>`}
      </td>
    </tr>`;
  }).join('');

  // Scroll highlighted row into view
  if (highlightStudentId) {
    setTimeout(() => {
      const el = tbody.querySelector('[style*="outline"]');
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      highlightStudentId = null;
    }, 100);
  }
}

// ── Modal ─────────────────────────────────────────────────────────────────────

function openPay(row) {
  document.getElementById('pf-student-id').value = row.id;
  document.getElementById('pf-month-hidden').value = monthStr();
  document.getElementById('pay-modal-title').textContent = `Record Payment — ${row.name}`;
  document.getElementById('pf-info').textContent =
    `Month: ${MONTHS[month]} ${year} · Due: ${fmtOMR(row.amount_due)}`;
  document.getElementById('pf-amount').value = row.amount_due.toFixed(3);
  document.getElementById('pf-date').value = today;
  document.getElementById('pf-notes').value = row.notes || '';
  document.getElementById('pay-modal').classList.add('open');
}

function closePay() { document.getElementById('pay-modal').classList.remove('open'); }

async function submitPayment(e) {
  e.preventDefault();
  await fetch('/api/payments', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({
      student_id:   document.getElementById('pf-student-id').value,
      month:        document.getElementById('pf-month-hidden').value,
      amount_paid:  document.getElementById('pf-amount').value,
      payment_date: document.getElementById('pf-date').value,
      notes:        document.getElementById('pf-notes').value.trim(),
    })
  });
  closePay();
  load();
}

function fmtOMR(n) { return Number(n).toFixed(3) + ' OMR'; }
function capitalize(s) { return s ? s[0].toUpperCase() + s.slice(1) : ''; }
function fmtOrdinal(n) {
  const s = ['th','st','nd','rd'], v = n % 100;
  return s[(v - 20) % 10] || s[v] || s[0];
}

load();
