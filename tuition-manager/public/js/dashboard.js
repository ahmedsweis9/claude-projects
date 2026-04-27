const MONTHS = ['January','February','March','April','May','June',
                 'July','August','September','October','November','December'];

let currentDate = new Date();
let year  = currentDate.getFullYear();
let month = currentDate.getMonth(); // 0-based

function monthStr() {
  return `${year}-${String(month + 1).padStart(2, '0')}`;
}

function changeMonth(dir) {
  month += dir;
  if (month < 0)  { month = 11; year--; }
  if (month > 11) { month = 0;  year++; }
  load();
}

function fmtOMR(n) { return n.toFixed(3) + ' OMR'; }

async function load() {
  document.getElementById('month-label').textContent = `${MONTHS[month]} ${year}`;
  document.getElementById('month-subtitle').textContent = `Showing data for ${MONTHS[month]} ${year}`;

  const data = await fetch(`/api/dashboard?month=${monthStr()}`).then(r => r.json());

  document.getElementById('stat-students').textContent   = data.total_students;
  document.getElementById('stat-expected').textContent   = fmtOMR(data.expected_revenue);
  document.getElementById('stat-collected').textContent  = fmtOMR(data.collected);
  document.getElementById('stat-outstanding').textContent= fmtOMR(data.outstanding);

  const list = document.getElementById('alert-list');
  const count = document.getElementById('alert-count');

  if (!data.unpaid.length) {
    count.textContent = '0';
    list.innerHTML = `<div class="empty">
      <div class="empty-icon">&#10003;</div>
      <h3>All paid up!</h3>
      <p>No outstanding payments for ${MONTHS[month]} ${year}.</p>
    </div>`;
    return;
  }

  count.textContent = data.unpaid.length;
  list.innerHTML = data.unpaid.map(s => {
    const partial = s.amount_paid > 0;
    const remaining = (s.amount_due - s.amount_paid).toFixed(3);
    const cls = partial ? 'alert-item partial' : 'alert-item';
    const status = partial
      ? `Partial — ${fmtOMR(s.amount_paid)} paid, ${remaining} OMR remaining`
      : `Unpaid — ${fmtOMR(s.amount_due)} due`;
    const section = s.section ? ` (${capitalize(s.section)})` : '';
    return `<div class="${cls}">
      <div class="info">
        <span class="name"><a href="/student.html?id=${s.id}">${s.name}</a></span>
        <span class="meta">Grade ${s.grade}${section} · ${status}</span>
      </div>
      <div class="flex gap-8">
        ${s.parent_phone ? `<a class="btn btn-outline btn-sm" href="https://wa.me/968${s.parent_whatsapp || s.parent_phone}" target="_blank">WhatsApp</a>` : ''}
        <a class="btn btn-primary btn-sm" href="/payments.html?month=${monthStr()}&student=${s.id}">Record</a>
      </div>
    </div>`;
  }).join('');

  buildGradePills();
}

function buildGradePills() {
  const container = document.getElementById('grade-pills');
  const today = new Date().toISOString().split('T')[0];
  container.innerHTML = Array.from({length: 8}, (_, i) => i + 5).map(g => {
    const label = g === 11 ? '11 Boys' : (g === 11 ? '11 Girls' : `Grade ${g}`);
    if (g === 11) {
      return `<a class="pill" href="/attendance.html?grade=11&section=boys&date=${today}">Grade 11 Boys</a>
              <a class="pill" href="/attendance.html?grade=11&section=girls&date=${today}">Grade 11 Girls</a>`;
    }
    return `<a class="pill" href="/attendance.html?grade=${g}&date=${today}">Grade ${g}</a>`;
  }).join('');
}

function capitalize(s) { return s ? s[0].toUpperCase() + s.slice(1) : ''; }

load();
