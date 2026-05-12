let activeGrade = 'all';
const today = new Date().toISOString().split('T')[0];

const grades = ['all', 5, 6, 7, 8, 9, 10, 11, 12];
document.getElementById('grade-pills').innerHTML = grades.map(g =>
  `<button class="pill ${g === activeGrade ? 'active' : ''}" onclick="setGrade('${g}')">${g === 'all' ? 'All Grades' : 'Grade ' + g}</button>`
).join('');

function setGrade(g) {
  activeGrade = g;
  document.querySelectorAll('.pill').forEach((el, i) =>
    el.classList.toggle('active', grades[i] == g)
  );
  loadStudents();
}

async function loadStudents() {
  const search = document.getElementById('search').value.trim();
  const active = document.getElementById('active-filter').value;
  const month  = today.slice(0, 7);

  const params = new URLSearchParams({ active, month });
  if (activeGrade !== 'all') params.set('grade', activeGrade);
  if (search) params.set('search', search);

  const students = await fetch(`/api/students?${params}`).then(r => r.json());

  document.getElementById('count-label').textContent =
    `${students.length} student${students.length !== 1 ? 's' : ''}`;

  const tbody = document.getElementById('student-tbody');
  if (!students.length) {
    tbody.innerHTML = `<tr><td colspan="8">
      <div class="empty"><div class="empty-icon">&#128106;</div>
      <h3>No students found</h3><p>Try a different filter or add a new student.</p></div>
    </td></tr>`;
    return;
  }

  tbody.innerHTML = students.map(s => {
    const paid    = s.paid_this_month >= s.amount_due;
    const partial = s.paid_this_month > 0 && !paid;
    const rowCls  = paid ? 'row-paid' : partial ? 'row-partial' : s.not_yet_due ? '' : 'row-unpaid';
    const dueLabel = s.due_date ? ` (due ${parseInt(s.due_date.split('-')[2])}th)` : '';
    const badge = paid
      ? '<span class="badge badge-green">Paid</span>'
      : s.not_yet_due
        ? `<span class="badge badge-gray">Not yet due${dueLabel}</span>`
        : partial
          ? `<span class="badge badge-amber">Partial (${s.paid_this_month.toFixed(3)})</span>`
          : '<span class="badge badge-red">Unpaid</span>';
    const section = s.section
      ? ` <span class="badge badge-purple">${capitalize(s.section)}</span>` : '';
    return `<tr class="${rowCls}">
      <td><a href="/student.html?id=${s.id}">${s.name}</a></td>
      <td>Grade ${s.grade}${section}</td>
      <td>${s.phone || '<span class="text-muted">—</span>'}</td>
      <td>${s.parent_name || '<span class="text-muted">—</span>'}</td>
      <td>${s.parent_phone || '<span class="text-muted">—</span>'}</td>
      <td>${s.enrollment_date}</td>
      <td>${badge}</td>
      <td class="text-right" style="display:flex;gap:6px;justify-content:flex-end">
        <button class="btn btn-outline btn-sm" onclick='openEditModal(${JSON.stringify(s)})'>Edit</button>
        <button class="btn btn-sm" style="background:#7f1d1d;color:#fca5a5;border:1px solid #991b1b" onclick="deleteStudent(${s.id}, ${JSON.stringify(s.name)})">Delete</button>
      </td>
    </tr>`;
  }).join('');
}

// ── Modal ─────────────────────────────────────────────────────────────────────

function openAddModal() {
  document.getElementById('edit-id').value = '';
  document.getElementById('modal-title').textContent = 'Add Student';
  document.getElementById('submit-btn').textContent  = 'Add Student';
  document.getElementById('student-form').reset();
  document.getElementById('f-enrollment').value = today;
  document.getElementById('section-group').style.display = '';
  document.getElementById('active-group').style.display  = 'none';
  document.getElementById('student-modal').classList.add('open');
}

function openEditModal(s) {
  document.getElementById('edit-id').value        = s.id;
  document.getElementById('modal-title').textContent = 'Edit Student';
  document.getElementById('submit-btn').textContent  = 'Save Changes';
  document.getElementById('f-name').value         = s.name;
  document.getElementById('f-grade').value        = s.grade;
  document.getElementById('f-section').value      = s.section || 'boys';
  document.getElementById('f-enrollment').value   = s.enrollment_date;
  document.getElementById('f-phone').value        = s.phone || '';
  document.getElementById('f-whatsapp').value     = s.whatsapp || '';
  document.getElementById('f-parent-name').value  = s.parent_name || '';
  document.getElementById('f-parent-phone').value = s.parent_phone || '';
  document.getElementById('f-parent-whatsapp').value = s.parent_whatsapp || '';
  document.getElementById('f-active').value       = s.active;
  document.getElementById('section-group').style.display = '';
  document.getElementById('active-group').style.display  = '';
  document.getElementById('student-modal').classList.add('open');
}

function closeModal() {
  document.getElementById('student-modal').classList.remove('open');
}

function onGradeChange() {
  // Section applies to all grades
  document.getElementById('section-group').style.display = '';
}

async function submitStudent(e) {
  e.preventDefault();
  const id = document.getElementById('edit-id').value;
  const payload = {
    name:            document.getElementById('f-name').value.trim(),
    grade:           document.getElementById('f-grade').value,
    section:         document.getElementById('f-section').value,
    phone:           document.getElementById('f-phone').value.trim(),
    whatsapp:        document.getElementById('f-whatsapp').value.trim(),
    parent_name:     document.getElementById('f-parent-name').value.trim(),
    parent_phone:    document.getElementById('f-parent-phone').value.trim(),
    parent_whatsapp: document.getElementById('f-parent-whatsapp').value.trim(),
    enrollment_date: document.getElementById('f-enrollment').value,
    active:          document.getElementById('f-active').value || '1',
  };

  const url    = id ? `/api/students/${id}` : '/api/students';
  const method = id ? 'PUT' : 'POST';
  await fetch(url, { method, headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) });
  closeModal();
  loadStudents();
}

async function deleteStudent(id, name) {
  if (!confirm(`Permanently delete "${name}"?\n\nThis will also delete all their payments and attendance records. This cannot be undone.`)) return;
  if (!confirm(`Are you sure? All data for "${name}" will be gone forever.`)) return;
  await fetch(`/api/students/${id}`, { method: 'DELETE' });
  loadStudents();
}

function capitalize(s) { return s ? s[0].toUpperCase() + s.slice(1) : ''; }

loadStudents();
