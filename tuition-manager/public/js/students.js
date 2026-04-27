let activeGrade = 'all';
const today = new Date().toISOString().split('T')[0];

// Grade filter pills
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
  const search  = document.getElementById('search').value.trim();
  const active  = document.getElementById('active-filter').value;
  const month   = today.slice(0, 7);

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
    const paid = s.paid_this_month >= s.amount_due;
    const partial = s.paid_this_month > 0 && !paid;
    const rowCls = paid ? 'row-paid' : partial ? 'row-partial' : 'row-unpaid';
    const badge = paid
      ? '<span class="badge badge-green">Paid</span>'
      : partial
        ? `<span class="badge badge-amber">Partial (${s.paid_this_month.toFixed(3)})</span>`
        : '<span class="badge badge-red">Unpaid</span>';
    const section = s.section ? ` <span class="badge badge-gray">${capitalize(s.section)}</span>` : '';
    return `<tr class="${rowCls}">
      <td><a href="/student.html?id=${s.id}">${s.name}</a></td>
      <td>Grade ${s.grade}${section}</td>
      <td>${s.phone || '<span class="text-muted">—</span>'}</td>
      <td>${s.parent_name || '<span class="text-muted">—</span>'}</td>
      <td>${s.parent_phone || '<span class="text-muted">—</span>'}</td>
      <td>${s.enrollment_date}</td>
      <td>${badge}</td>
      <td class="text-right">
        <button class="btn btn-outline btn-sm" onclick='openEditModal(${JSON.stringify(s)})'>Edit</button>
      </td>
    </tr>`;
  }).join('');
}

// ── Modal ─────────────────────────────────────────────────────────────────────

function openAddModal() {
  document.getElementById('edit-id').value = '';
  document.getElementById('modal-title').textContent = 'Add Student';
  document.getElementById('submit-btn').textContent = 'Add Student';
  document.getElementById('student-form').reset();
  document.getElementById('f-enrollment').value = today;
  document.getElementById('section-group').style.display = 'none';
  document.getElementById('active-group').style.display = 'none';
  document.getElementById('student-modal').classList.add('open');
}

function openEditModal(s) {
  document.getElementById('edit-id').value = s.id;
  document.getElementById('modal-title').textContent = 'Edit Student';
  document.getElementById('submit-btn').textContent = 'Save Changes';
  document.getElementById('f-name').value = s.name;
  document.getElementById('f-grade').value = s.grade;
  document.getElementById('f-enrollment').value = s.enrollment_date;
  document.getElementById('f-phone').value = s.phone || '';
  document.getElementById('f-whatsapp').value = s.whatsapp || '';
  document.getElementById('f-parent-name').value = s.parent_name || '';
  document.getElementById('f-parent-phone').value = s.parent_phone || '';
  document.getElementById('f-parent-whatsapp').value = s.parent_whatsapp || '';
  document.getElementById('f-active').value = s.active;
  document.getElementById('active-group').style.display = '';

  const isg11 = String(s.grade) === '11';
  document.getElementById('section-group').style.display = isg11 ? '' : 'none';
  if (isg11) document.getElementById('f-section').value = s.section || 'boys';

  document.getElementById('student-modal').classList.add('open');
}

function closeModal() {
  document.getElementById('student-modal').classList.remove('open');
}

function onGradeChange() {
  const g = document.getElementById('f-grade').value;
  document.getElementById('section-group').style.display = g === '11' ? '' : 'none';
}

async function submitStudent(e) {
  e.preventDefault();
  const id = document.getElementById('edit-id').value;
  const payload = {
    name:             document.getElementById('f-name').value.trim(),
    grade:            document.getElementById('f-grade').value,
    section:          document.getElementById('f-section').value,
    phone:            document.getElementById('f-phone').value.trim(),
    whatsapp:         document.getElementById('f-whatsapp').value.trim(),
    parent_name:      document.getElementById('f-parent-name').value.trim(),
    parent_phone:     document.getElementById('f-parent-phone').value.trim(),
    parent_whatsapp:  document.getElementById('f-parent-whatsapp').value.trim(),
    enrollment_date:  document.getElementById('f-enrollment').value,
    active:           document.getElementById('f-active').value || '1',
  };

  const url    = id ? `/api/students/${id}` : '/api/students';
  const method = id ? 'PUT' : 'POST';
  await fetch(url, { method, headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) });

  closeModal();
  loadStudents();
}

function capitalize(s) { return s ? s[0].toUpperCase() + s.slice(1) : ''; }

loadStudents();
