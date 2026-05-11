/**
 * ur-nav.js — Universal Realms shared navigation
 * Drop-in replacement for ur-auth.js. Handles:
 *   - Nav injection / replacement of existing .ur-nav-shell
 *   - Tools dropdown (Battle, Duel, Raid)
 *   - Auth state (sets window.UR_USER, renders Sign In / username)
 */
(function () {

  // ── STYLES ─────────────────────────────────────────────────────
  const style = document.createElement('style');
  style.textContent = `
    .ur-nav-shell {
      height: 52px; display: flex; align-items: stretch;
      background: #2a1c0d; border-bottom: 1px solid #3d2b14;
      position: sticky; top: 0; z-index: 1000;
      box-shadow: 0 2px 10px rgba(0,0,0,0.45);
    }
    .ur-nav-shell::after {
      content: ''; position: absolute; bottom: -1px; left: 0; right: 0; height: 1px;
      background: linear-gradient(90deg, transparent, rgba(184,137,42,0.28), transparent);
      pointer-events: none;
    }
    .ur-logo-btn {
      padding: 0 22px; display: flex; flex-direction: column; justify-content: center;
      border-right: 1px solid rgba(255,255,255,0.06); text-decoration: none;
      flex-shrink: 0; transition: background 0.15s;
    }
    .ur-logo-btn:hover { background: rgba(255,255,255,0.03); }
    .ur-logo-name {
      font-family: 'Cinzel', serif; font-size: 12px; font-weight: 600;
      color: #f5edd8; letter-spacing: 2.5px; text-transform: uppercase; line-height: 1;
    }
    .ur-logo-tag {
      font-family: 'EB Garamond', Georgia, serif; font-size: 9px; color: #c8a838;
      letter-spacing: 1.5px; margin-top: 3px; font-style: italic; opacity: 0.75;
    }
    .ur-nav-links {
      display: flex; align-items: stretch; flex: 1; padding: 0 4px; overflow-x: auto;
    }
    .ur-nav-links::-webkit-scrollbar { display: none; }
    .ur-nav-lnk {
      display: flex; align-items: center; gap: 6px; padding: 0 13px;
      font-family: 'EB Garamond', Georgia, serif; font-size: 13.5px; font-style: italic;
      color: #9a8468; text-decoration: none;
      border-bottom: 2px solid transparent; border-top: none; border-left: none; border-right: none;
      background: none; cursor: pointer; white-space: nowrap; transition: all 0.15s;
    }
    .ur-nav-lnk:hover { color: #e8d9bb; background: rgba(255,255,255,0.03); }
    .ur-nav-lnk.cur {
      color: #c8a838; border-bottom-color: #8b6914;
      font-style: normal; font-weight: 500; background: rgba(200,168,56,0.08);
    }
    .ur-nav-icon { font-size: 10px; opacity: 0.65; }
    .ur-nav-lnk.cur .ur-nav-icon { opacity: 1; }

    /* ── Dropdown ── */
    .ur-dropdown { position: relative; display: flex; align-items: stretch; }
    .ur-dd-arrow { font-size: 8px; opacity: 0.55; margin-left: 2px; transition: transform 0.15s; display: inline-block; }
    .ur-dropdown.open .ur-dd-arrow { transform: rotate(180deg); }
    .ur-dropdown.open > .ur-nav-lnk { color: #c8a838; background: rgba(200,168,56,0.08); }

    .ur-dd-menu {
      position: absolute; top: 100%; left: 0;
      min-width: 190px; background: #1a1208;
      border: 1px solid rgba(139,105,20,0.45); border-top: none;
      border-radius: 0 0 3px 3px;
      box-shadow: 0 10px 28px rgba(0,0,0,0.55);
      display: none; z-index: 1001;
    }
    .ur-dropdown.open .ur-dd-menu { display: block; }

    .ur-dd-item {
      display: flex; align-items: center; gap: 10px;
      padding: 11px 16px; text-decoration: none;
      font-family: 'EB Garamond', Georgia, serif; font-size: 14px; font-style: italic;
      color: #9a8468; border-bottom: 1px solid rgba(139,105,20,0.12);
      transition: all 0.15s;
    }
    .ur-dd-item:last-child { border-bottom: none; }
    .ur-dd-item:hover { color: #e8d9bb; background: rgba(255,255,255,0.04); }
    .ur-dd-item.cur { color: #c8a838; background: rgba(200,168,56,0.06); font-style: normal; }
    .ur-dd-icon { font-size: 11px; opacity: 0.7; flex-shrink: 0; }
    .ur-dd-label { flex: 1; }
    .ur-dd-desc { font-size: 11px; color: #4a3a18; font-style: normal; }

    /* ── Right section & auth ── */
    .ur-nav-right { display: flex; align-items: center; padding: 0 18px; flex-shrink: 0; border-left: 1px solid rgba(255,255,255,0.06); }
    #ur-auth-nav { display: flex; align-items: center; }
    .ur-auth-link {
      display: flex; align-items: center; gap: 7px;
      font-family: 'Cinzel', serif; font-size: 11px; letter-spacing: 1.5px;
      text-transform: uppercase; color: #c8a838; text-decoration: none;
      padding: 0 12px; border-left: 1px solid rgba(255,255,255,0.06);
      height: 52px; transition: color 0.15s;
    }
    .ur-auth-link:hover { color: #f0d060; }
    .ur-auth-dot { font-size: 9px; opacity: 0.6; }
    .ur-signin-btn {
      font-family: 'Cinzel', serif; font-size: 9px; letter-spacing: 2px;
      text-transform: uppercase; padding: 6px 14px;
      border: 1px solid rgba(184,137,42,0.4); border-radius: 2px;
      color: #c8a838; background: rgba(184,137,42,0.08);
      text-decoration: none; transition: all 0.15s; margin-left: 10px;
    }
    .ur-signin-btn:hover { background: rgba(184,137,42,0.18); color: #f0d060; }
    .ur-logout-btn {
      background: transparent; border: none; cursor: pointer;
      font-family: 'Cinzel', serif; font-size: 9px; letter-spacing: 1.5px;
      text-transform: uppercase; color: #7a6030; padding: 0 10px; transition: color 0.15s;
    }
    .ur-logout-btn:hover { color: #c0392b; }
  `;
  document.head.appendChild(style);

  // ── PAGE DETECTION ──────────────────────────────────────────────
  const path = window.location.pathname;
  const TOOL_PAGES = ['/battle_roller.html', '/duel_roller.html', '/raid_roller.html'];
  const toolsActive = TOOL_PAGES.some(p => path.endsWith(p));

  function c(pages) {
    return pages.some(p => path === p || path.endsWith(p)) ? ' cur' : '';
  }

  // ── BUILD NAV HTML ──────────────────────────────────────────────
  function buildNav() {
    return `
      <a href="/" class="ur-logo-btn">
        <div class="ur-logo-name">Universal Realms</div>
        <div class="ur-logo-tag">World Engine</div>
      </a>
      <div class="ur-nav-links">
        <a href="/" class="ur-nav-lnk${c(['/', '/index.html'])}">
          <span class="ur-nav-icon">⌂</span>Dashboard
        </a>
        <a href="/character_creator.html" class="ur-nav-lnk${c(['/character_creator.html'])}">
          <span class="ur-nav-icon">◉</span>Characters
        </a>
        <div class="ur-dropdown${toolsActive ? ' open' : ''}" id="ur-tools-dd">
          <button class="ur-nav-lnk${toolsActive ? ' cur' : ''}">
            <span class="ur-nav-icon">⚒</span>Tools<span class="ur-dd-arrow">▾</span>
          </button>
          <div class="ur-dd-menu">
            <a href="/battle_roller.html" class="ur-dd-item${c(['/battle_roller.html'])}">
              <span class="ur-dd-icon">⚔</span>
              <span class="ur-dd-label">Battle Roller</span>
              <span class="ur-dd-desc">Army combat</span>
            </a>
            <a href="/duel_roller.html" class="ur-dd-item${c(['/duel_roller.html'])}">
              <span class="ur-dd-icon">◈</span>
              <span class="ur-dd-label">Duel Roller</span>
              <span class="ur-dd-desc">Personal combat</span>
            </a>
            <a href="/raid_roller.html" class="ur-dd-item${c(['/raid_roller.html'])}">
              <span class="ur-dd-icon">⚑</span>
              <span class="ur-dd-label">Raid Roller</span>
              <span class="ur-dd-desc">Coastal & land raids</span>
            </a>
          </div>
        </div>
        <a href="/chronicle_map.html" class="ur-nav-lnk${c(['/chronicle_map.html'])}">
          <span class="ur-nav-icon">⊞</span>Maps
        </a>
        <a href="/players.html" class="ur-nav-lnk${c(['/players.html'])}">
          <span class="ur-nav-icon">◎</span>Players
        </a>
        <a href="/scenarios.html" class="ur-nav-lnk${c(['/scenarios.html'])}">
          <span class="ur-nav-icon">✦</span>Scenarios
        </a>
        <a href="/games.html" class="ur-nav-lnk${c(['/games.html'])}">
          <span class="ur-nav-icon">⚑</span>Games
        </a>
      </div>
      <div class="ur-nav-right" id="ur-auth-nav"></div>
    `;
  }

  // ── MOUNT NAV ──────────────────────────────────────────────────
  function mountNav() {
    let shell = document.querySelector('.ur-nav-shell');
    if (!shell) {
      shell = document.createElement('nav');
      shell.className = 'ur-nav-shell';
      document.body.prepend(shell);
    }
    // Ensure it's a sticky nav regardless of original tag
    shell.style.position  = 'sticky';
    shell.style.top       = '0';
    shell.style.zIndex    = '1000';
    shell.innerHTML       = buildNav();

    // Dropdown toggle
    const dd      = document.getElementById('ur-tools-dd');
    const trigger = dd?.querySelector('button');
    if (dd && trigger) {
      trigger.addEventListener('click', e => {
        e.stopPropagation();
        dd.classList.toggle('open');
      });
      document.addEventListener('click', () => {
        if (!toolsActive) dd.classList.remove('open');
      });
    }
  }

  // ── AUTH ────────────────────────────────────────────────────────
  function esc(str) {
    const d = document.createElement('div');
    d.textContent = String(str || '');
    return d.innerHTML;
  }

  function renderAuthed(user) {
    const el = document.getElementById('ur-auth-nav');
    if (!el) return;
    el.innerHTML =
      `<a href="/profile.html" class="ur-auth-link">` +
        `<span class="ur-auth-dot">◉</span>` +
        `<span>${esc(user.displayName || user.username)}</span>` +
      `</a>` +
      `<button class="ur-logout-btn" onclick="window.urLogout()">Sign Out</button>`;
  }

  function renderAnon() {
    const el = document.getElementById('ur-auth-nav');
    if (!el) return;
    el.innerHTML = `<a href="/login.html" class="ur-signin-btn">Sign In</a>`;
  }

  async function initAuth() {
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

  // ── INIT ────────────────────────────────────────────────────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { mountNav(); initAuth(); });
  } else {
    mountNav();
    initAuth();
  }

})();
