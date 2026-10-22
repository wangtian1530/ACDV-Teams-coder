/* ACDV Overlay Loader — inject module CSS/JS với safe mode + banner */
(function () {
  'use strict';

  function isSafeParam() {
    return new URLSearchParams(location.search).get('safe') === '1';
  }

  async function refresh() {
    document.querySelectorAll('link[data-overlay], script[data-overlay]')
      .forEach(el => el.remove());
    const banner = document.getElementById('overlayBanner');
    if (banner) banner.remove();

    if (isSafeParam()) {
      console.info('[Overlay] safe mode via ?safe=1 — skipping all');
      return;
    }

    let data = null;
    try {
      const res = await fetch('/api/overlay').then(r => r.json());
      if (res && res.ok) data = res;
    } catch (e) {
      console.warn('[Overlay] fetch failed', e);
      return;
    }
    if (!data) return;
    if (data.safe_mode) {
      console.info('[Overlay] safe_mode on — no overlays');
      return;
    }

    let activeCount = 0;
    for (const ov of (data.overlays || [])) {
      if (ov.css_enabled && ov.css) {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = ov.css + '?t=' + Date.now();
        link.dataset.overlay = ov.name;
        document.head.appendChild(link);
        activeCount++;
        console.info('[Overlay] CSS →', ov.name);
      }
      if (ov.js_enabled && ov.js) {
        await injectScript(ov.js, ov.name);
        activeCount++;
        console.info('[Overlay] JS →', ov.name);
      }
    }

    if (activeCount > 0) showBanner(data.overlays.filter(o => o.css_enabled || o.js_enabled).length);
  }

  function injectScript(src, name) {
    return new Promise((resolve) => {
      const s = document.createElement('script');
      s.src = src + '?t=' + Date.now();
      s.dataset.overlay = name;
      s.onload = () => resolve();
      s.onerror = () => { console.warn('[Overlay] JS failed:', name); resolve(); };
      document.body.appendChild(s);
    });
  }

  function showBanner(count) {
    const b = document.createElement('div');
    b.id = 'overlayBanner';
    b.innerHTML = `
      <span>🎨 ${count} module overlay${count !== 1 ? 's' : ''} active</span>
      <button id="overlaySafeMode" title="Reload without any module overlay">🛑 Disable</button>
      <button id="overlayDismiss">×</button>
    `;
    b.style.cssText = 'position:fixed;bottom:10px;right:10px;background:#2d2d2d;color:#fff;padding:8px 12px;border-radius:6px;z-index:99999;font:12px -apple-system,sans-serif;display:flex;gap:8px;align-items:center;box-shadow:0 2px 8px rgba(0,0,0,0.4);';
    b.querySelector('#overlaySafeMode').addEventListener('click', () => {
      location.href = location.pathname + '?safe=1';
    });
    b.querySelector('#overlayDismiss').addEventListener('click', () => b.remove());
    document.body.appendChild(b);
    setTimeout(() => { if (b.parentNode) b.remove(); }, 12000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', refresh);
  } else {
    setTimeout(refresh, 50);
  }

  window.OverlayLoader = { refresh };
})();