(function () {
  /* Inject nav styles — works on both light and dark pages since the
     nav bar itself is always dark (--ink-800). */
  const style = document.createElement('style');
  style.textContent = `
    #ur-auth-nav { display:flex; align-items:center; }
    .ur-auth-link {
      display:flex; align-items:center; gap:7px;
      font-family:'Cinzel',serif; font-size:11px; letter-spacing:1.5px;
      text-transform:uppercase; color:#c8a838; text-decoration:none;
      padding:0 12px; border-left:1px solid rgba(255,255,255,0.06);
      height:52px; transition:color 0.15s;
    }
    .ur-auth-link:hover { color:#f0d060; }
    .ur-auth-name { font-size:12px; }
    .ur-auth-dot  { font-size:9px; opacity:0.6; }
    .ur-signin-btn {
      font-family:'Cinzel',serif; font-size:9px; letter-spacing:2px;
      text-transform:uppercase; padding:6px 14px;
      border:1px solid rgba(184,137,42,0.4); border-radius:2px;
      color:#c8a838; background:rgba(184,137,42,0.08);
      text-decoration:none; transition:all 0.15s; margin-left:10px;
    }
    .ur-signin-btn:hover { background:rgba(184,137,42,0.18); color:#f0d060; }
    .ur-logout-btn {
      background:transparent; border:none; cursor:pointer;
      font-family:'Cinzel',serif; font-size:9px; letter-spacing:1.5px;
      text-transform:uppercase; color:#7a6030; padding:0 10px;
      transition:color 0.15s;
    }
    .ur-logout-btn:hover { color:#c0392b; }
  `;
  document.head.appendChild(style);

  function esc(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
  }

  function renderAuthed(user) {
    const el = document.getElementById('ur-auth-nav');
    if (!el) return;
    el.innerHTML =
      `<a href="/profile.html" class="ur-auth-link">` +
        `<span class="ur-auth-dot">◉</span>` +
        `<span class="ur-auth-name">${esc(user.displayName || user.username)}</span>` +
      `</a>` +
      `<button class="ur-logout-btn" onclick="window.urLogout()">Sign Out</button>`;
  }

  function renderAnon() {
    const el = document.getElementById('ur-auth-nav');
    if (!el) return;
    el.innerHTML = `<a href="/login.html" class="ur-signin-btn">Sign In</a>`;
  }

  async function init() {
    try {
      const res = await fetch('/api/auth/me', { credentials: 'include' });
      if (res.ok) {
        window.UR_USER = await res.json();
        renderAuthed(window.UR_USER);
      } else {
        window.UR_USER = null;
        renderAnon();
      }
    } catch {
      window.UR_USER = null;
      renderAnon();
    }
  }

  window.urLogout = async function () {
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
    window.UR_USER = null;
    renderAnon();
    if (window.location.pathname.startsWith('/profile')) {
      window.location.href = '/';
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
