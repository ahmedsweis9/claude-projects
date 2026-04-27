// Grade 5 session durations: [1, 1, 2]; others: [2, 2]
const SESSION_DURATIONS = { 5: [1, 1, 2] };
const DEFAULT_DURATION  = [2, 2];

let students = [];
let statuses = {};

// Pre-fill from URL params (dashboard quick-links)
const urlp = new URLSearchParams(location.search);
const today = new Date().toISOString().split('T')[0];
document.getElementById('att-date').value = urlp.get('date') || today;
if (urlp.get('grade')) document.getElementById('att-grade').value = urlp.get('grade');
if (urlp.get('section')) document.getElementById('att-section').value = urlp.get('section');

function onGradeChange() {
  const g = document.getElementById('att-grade').value;
  document.getElementById('section-group').style.display = g === '11' ? '' : 'none';

  // Limit session 3 option to grade 5
  const s3 = document.querySelector('#att-session option[value="3"]');
  s3.disabled = g !== '5';
  if (document.getElementById('att-session').value === '3' && g !== '5') {
    document.getElementById('att-session').value = '1';
  }
  loadSession();
}

async function loadSession() {
  const grade   = document.getElementById('att-grade').value;
  const date    = document.getElementById('att-date').value;
  const session = document.getElementById('att-session').value;

  if (!grade || !date) return;

  document.getElementById('select-prompt').style.display = 'none';
  document.getElementById('checklist-card').style.display = '';
  document.getElementById('schedule-info').style.display = '';

  const params = new URLSearchParams({ grade, date, session_number: session });
  students = await fetch(`/api/attendance/session?${params}`).then(r => r.json());

  // Init statuses from existing data or default to present
  statuses = {};
  students.forEach(s => {
    statuses[s.id] = s.existing_status || 'present';
  });

  // Section filter for grade 11
  if (grade === '11') {
    const section = document.getElementById('att-section').value;
    students = students.filter(s => s.section === section);
  }

  const durations = SESSION_DURATIONS[parseInt(grade)] || DEFAULT_DURATION;
  const dur = durations[parseInt(session) - 1] || 2;

  const scheduleEl = document.getElementById('schedule-text');
  if (grade === '5') {
    scheduleEl.textContent = `Grade 5 schedule: 3 sessions/week — 1hr + 1hr + 2hr. This is Session ${session} (${dur}hr).`;
  } else {
    scheduleEl.textContent = `Grade ${grade} schedule: 2 sessions/week — 2hr each. This is Session ${session} (${dur}hr).`;
  }

  const title = document.getElementById('checklist-title');
  const section = grade === '11' ? ` · ${capitalize(document.getElementById('att-section').value)}` : '';
  title.textContent = `Grade ${grade}${section} — ${date} — Session ${session}`;

  renderList();
}

function renderList() {
  const list = document.getElementById('att-list');
  const none = document.getElementById('no-students');

  if (!students.length) {
    list.innerHTML = '';
    none.style.display = '';
    return;
  }
  none.style.display = 'none';

  list.innerHTML = students.map(s => {
    const cur = statuses[s.id] || 'present';
    return `<div class="att-row" id="row-${s.id}">
      <span class="att-name">${s.name}</span>
      <div class="att-btns">
        <button class="att-btn ${cur === 'present' ? 'sel-present' : ''}"
          onclick="setStatus(${s.id}, 'present', this)">Present</button>
        <button class="att-btn ${cur === 'absent' ? 'sel-absent' : ''}"
          onclick="setStatus(${s.id}, 'absent', this)">Absent</button>
        <button class="att-btn ${cur === 'excused' ? 'sel-excused' : ''}"
          onclick="setStatus(${s.id}, 'excused', this)">Excused</button>
      </div>
    </div>`;
  }).join('');
}

function setStatus(id, status, btn) {
  statuses[id] = status;
  const row = document.getElementById(`row-${id}`);
  row.querySelectorAll('.att-btn').forEach(b => b.className = 'att-btn');
  btn.className = `att-btn sel-${status}`;
}

function markAll(status) {
  students.forEach(s => { statuses[s.id] = status; });
  renderList();
}

async function saveAttendance() {
  const grade   = document.getElementById('att-grade').value;
  const date    = document.getElementById('att-date').value;
  const session = parseInt(document.getElementById('att-session').value);
  const durations = SESSION_DURATIONS[parseInt(grade)] || DEFAULT_DURATION;
  const dur = durations[session - 1] || 2;

  const records = students.map(s => ({
    student_id:     s.id,
    session_date:   date,
    session_number: session,
    duration_hours: dur,
    status:         statuses[s.id] || 'present',
  }));

  await fetch('/api/attendance', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(records)
  });

  const toast = document.getElementById('save-toast');
  toast.style.display = 'block';
  setTimeout(() => { toast.style.display = 'none'; }, 2500);
}

function capitalize(s) { return s ? s[0].toUpperCase() + s.slice(1) : ''; }

// Auto-load if grade came from URL
if (urlp.get('grade')) { onGradeChange(); }
