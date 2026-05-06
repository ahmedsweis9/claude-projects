(function () {
  const _fetch = window.fetch.bind(window);
  window.fetch = async function (url, opts) {
    const res = await _fetch(url, opts);
    if (res.status === 401 && !String(url).includes('/api/login')) {
      window.location.href = '/login.html';
    }
    return res;
  };
})();

async function logout() {
  await fetch('/api/logout', { method: 'POST' });
  window.location.href = '/login.html';
}

document.addEventListener('DOMContentLoaded', function () {
  const nav = document.querySelector('.nav');
  if (!nav) return;
  const div = document.createElement('div');
  div.style.cssText = 'margin-top:auto;padding:12px 8px 16px;';
  div.innerHTML =
    '<button onclick="logout()" style="' +
    'width:100%;padding:9px 16px;background:none;border:1px solid #334155;' +
    'border-radius:6px;color:#64748b;font-size:13px;cursor:pointer;' +
    'text-align:left;font-family:inherit;display:flex;align-items:center;gap:10px;' +
    'transition:background .15s,color .15s;"' +
    ' onmouseover="this.style.background=\'#334155\';this.style.color=\'#fff\'"' +
    ' onmouseout="this.style.background=\'none\';this.style.color=\'#64748b\'">' +
    '<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">' +
    '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>' +
    '<polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>' +
    '</svg>Sign out</button>';
  nav.appendChild(div);
});
