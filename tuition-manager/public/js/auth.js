(function () {
  const _fetch = window.fetch.bind(window);
  window.fetch = async function (url, opts) {
    const res = await _fetch(url, opts);
    if (res.status === 401 &&
        !String(url).includes('/api/login') &&
        !String(url).includes('/api/signup')) {
      window.location.href = '/login.html';
    }
    return res;
  };
})();

async function logout() {
  await fetch('/api/logout', { method: 'POST' });
  window.location.href = '/login.html';
}

document.addEventListener('DOMContentLoaded', async function () {
  const navUser   = document.getElementById('nav-user');
  const navAvatar = document.getElementById('nav-avatar');
  const navName   = document.getElementById('nav-name');
  if (!navName) return;
  try {
    const res = await fetch('/api/me');
    if (res.ok) {
      const u = await res.json();
      if (navName)   navName.textContent   = u.name || 'User';
      if (navAvatar) navAvatar.textContent = (u.name || 'U')[0].toUpperCase();
      if (navUser)   navUser.style.display = 'flex';
    }
  } catch (_) {}
});
