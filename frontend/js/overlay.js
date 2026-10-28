/* ACDV Overlay Runtime v2.0.1
 * - ACDV.register() với cleanup registry.
 * - ETag-based, không bust cache.
 * - Safe mode unload thật sự.
 * - App-ready wait, timeout on inject, duplicate id check.
 *
 * v2.0.1 fixes:
 * - C6: tắt JS không xoá CSS. Chỉ unload script, giữ link CSS.
 * - H12: register() so sánh record identity (không theo tên) để tránh double-init.
 */
(function () {
  'use strict';

  const RUNTIME_VERSION = '2.0.1';

  const ACDV = {
    version: RUNTIME_VERSION,
    _modules: new Map(),
    _injected: new Map(),
    _appReady: false,
    _appWaiters: [],
    _safeMode: false,
    _refreshing: null,

    _setAppReady() {
      if (this._appReady) return;
      this._appReady = true;
      const waiters = this._appWaiters;
      this._appWaiters = [];
      for (const fn of waiters) {
        try { fn(); } catch (e) { console.error('[ACDV] appReady waiter:', e); }
      }
    },

    whenAppReady(fn) {
      if (this._appReady) {
        try { fn(); } catch (e) { console.error('[ACDV]', e); }
      } else {
        this._appWaiters.push(fn);
      }
    },

    _createContext(name) {
      const cleanups = [];

      const ctx = {
        get app()      { return window.App; },
        get cm()       { return window.App && App.editor && App.editor.cm; },
        get editor()   { return window.App && App.editor; },
        get ws()       { return window.App && App.ws; },
        get settings() {
          try { return (window.App && App.editor && App.editor.globalSettings) || {}; }
          catch (e) { return {}; }
        },

        on(target, evt, handler, opts) {
          if (!target || typeof target.addEventListener !== 'function') return;
          target.addEventListener(evt, handler, opts);
          cleanups.push(() => {
            try { target.removeEventListener(evt, handler, opts); } catch (e) {}
          });
        },

        timer(fn, ms) {
          const t = setTimeout(() => { try { fn(); } catch (e) {} }, ms);
          cleanups.push(() => clearTimeout(t));
          return t;
        },

        interval(fn, ms) {
          const t = setInterval(() => { try { fn(); } catch (e) {} }, ms);
          cleanups.push(() => clearInterval(t));
          return t;
        },

        wsOn(evt, handler) {
          const ws = window.App && App.ws;
          if (!ws) return;
          const unsub = ws.on(evt, handler);
          cleanups.push(() => {
            try {
              if (typeof unsub === 'function') unsub();
              else ws.off(evt, handler);
            } catch (e) {}
          });
        },

        cmOn(evt, handler) {
          const cm = window.App && App.editor && App.editor.cm;
          if (!cm || typeof cm.on !== 'function') return;
          try {
            cm.on(evt, handler);
            cleanups.push(() => {
              try { cm.off(evt, handler); } catch (e) {}
            });
          } catch (e) { console.error('[ACDV] cmOn failed:', e); }
        },

        append(parent, el) {
          if (!parent || !el) return el;
          parent.appendChild(el);
          cleanups.push(() => {
            try { if (el.parentNode) el.parentNode.removeChild(el); } catch (e) {}
          });
          return el;
        },

        log(msg, ...args)   { console.log(`[${name}]`, msg, ...args); },
        warn(msg, ...args)  { console.warn(`[${name}]`, msg, ...args); },
        error(msg, ...args) { console.error(`[${name}]`, msg, ...args); },

        async fetch(url, opts) {
          try {
            const u = new URL(url, location.origin);
            if (u.origin !== location.origin) {
              throw new Error(`Cross-origin fetch blocked: ${u.href}`);
            }
          } catch (e) {
            throw new Error(`Invalid URL: ${url}`);
          }
          return window.fetch(url, opts);
        },

        storageGet(key, def) {
          try {
            const v = localStorage.getItem(`acdv.mod.${name}.${key}`);
            return v === null ? def : JSON.parse(v);
          } catch (e) { return def; }
        },
        storageSet(key, value) {
          try { localStorage.setItem(`acdv.mod.${name}.${key}`, JSON.stringify(value)); }
          catch (e) {}
        },
        storageRemove(key) {
          try { localStorage.removeItem(`acdv.mod.${name}.${key}`); } catch (e) {}
        },

        onCleanup(fn) {
          if (typeof fn === 'function') cleanups.push(fn);
        },
      };

      return { ctx, cleanups };
    },

    register(name, initFn) {
      if (!name || typeof initFn !== 'function') {
        console.error('[ACDV] invalid register:', name, typeof initFn);
        return;
      }

      if (this._modules.has(name)) {
        this.unload(name);
      }

      const { ctx, cleanups } = this._createContext(name);
      const record = { cleanups, ctx, initCalled: false, initFn };
      this._modules.set(name, record);

      // ⭐ H12: so sánh record identity, KHÔNG theo tên
      this.whenAppReady(() => {
        if (this._modules.get(name) !== record) {
          console.info(`[ACDV] ${name} register overwritten before ready — skip old init`);
          return;
        }
        record.initCalled = true;
        try {
          initFn(ctx);
        } catch (e) {
          console.error(`[ACDV] ${name} init failed:`, e);
        }
      });
    },

    unload(name) {
      const record = this._modules.get(name);

      if (record) {
        for (let i = record.cleanups.length - 1; i >= 0; i--) {
          try { record.cleanups[i](); }
          catch (e) { console.error(`[ACDV] ${name} cleanup:`, e); }
        }
        this._modules.delete(name);
      }

      const inj = this._injected.get(name);
      if (inj) {
        try { if (inj.scriptEl && inj.scriptEl.parentNode) inj.scriptEl.parentNode.removeChild(inj.scriptEl); }
        catch (e) {}
        try { if (inj.linkEl && inj.linkEl.parentNode) inj.linkEl.parentNode.removeChild(inj.linkEl); }
        catch (e) {}
        this._injected.delete(name);
      }
    },

    /** ⭐ C6: chỉ unload JS, GIỮ CSS. */
    _unloadJsOnly(name) {
      const record = this._modules.get(name);
      if (record) {
        for (let i = record.cleanups.length - 1; i >= 0; i--) {
          try { record.cleanups[i](); }
          catch (e) { console.error(`[ACDV] ${name} cleanup:`, e); }
        }
        this._modules.delete(name);
      }
      const inj = this._injected.get(name);
      if (inj && inj.scriptEl) {
        try { if (inj.scriptEl.parentNode) inj.scriptEl.parentNode.removeChild(inj.scriptEl); }
        catch (e) {}
        inj.scriptEl = null;
        inj.jsSrc = null;
        inj.jsEtag = null;
      }
    },

    unloadAll() {
      for (const name of Array.from(this._modules.keys())) this.unload(name);
      for (const [name, inj] of Array.from(this._injected.entries())) {
        try { if (inj.scriptEl && inj.scriptEl.parentNode) inj.scriptEl.parentNode.removeChild(inj.scriptEl); } catch (e) {}
        try { if (inj.linkEl && inj.linkEl.parentNode) inj.linkEl.parentNode.removeChild(inj.linkEl); } catch (e) {}
        this._injected.delete(name);
      }
    },

    status() {
      const mods = {};
      for (const [name, r] of this._modules) {
        mods[name] = { cleanups: r.cleanups.length, initCalled: r.initCalled };
      }
      const inj = {};
      for (const [name, e] of this._injected) {
        inj[name] = { css: e.cssHref, cssEtag: e.cssEtag, js: e.jsSrc, jsEtag: e.jsEtag };
      }
      return { version: RUNTIME_VERSION, appReady: this._appReady,
               safeMode: this._safeMode, modules: mods, injected: inj };
    },
  };

  window.ACDV = ACDV;

  function isSafeParam() {
    return new URLSearchParams(location.search).get('safe') === '1';
  }

  function withEtag(url, etag) {
    if (!etag) return url;
    return url + (url.includes('?') ? '&' : '?') + 'v=' + encodeURIComponent(etag);
  }

  function injectLink(href, name, etag) {
    return new Promise((resolve) => {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = withEtag(href, etag);
      link.dataset.overlay = name;
      link.dataset.acdvEtag = etag || '';
      let done = false;
      const finish = (ok) => {
        if (done) return;
        done = true;
        clearTimeout(timer);
        if (!ok) console.warn('[ACDV] CSS failed/timeout:', name);
        resolve(link);
      };
      const timer = setTimeout(() => finish(false), 3000);
      link.onload = () => finish(true);
      link.onerror = () => finish(false);
      document.head.appendChild(link);
    });
  }

  function injectScript(src, name, etag) {
    return new Promise((resolve) => {
      const s = document.createElement('script');
      s.src = withEtag(src, etag);
      s.dataset.overlay = name;
      s.dataset.acdvEtag = etag || '';
      s.async = true;

      let done = false;
      const finish = (ok) => {
        if (done) return;
        done = true;
        clearTimeout(timer);
        if (!ok) console.warn('[ACDV] JS failed/timeout:', name);
        resolve(s);
      };
      const timer = setTimeout(() => finish(false), 5000);
      s.onload = () => finish(true);
      s.onerror = () => finish(false);
      document.body.appendChild(s);
    });
  }

  function checkDuplicateIds() {
    const seen = new Map();
    document.querySelectorAll('[id]').forEach(el => {
      const prev = seen.get(el.id);
      if (prev) {
        console.warn('[ACDV] duplicate id:', el.id,
          '| first:', prev, '| second:', el.tagName);
      } else {
        seen.set(el.id, el.tagName);
      }
    });
  }

  async function refresh() {
    if (ACDV._refreshing) return ACDV._refreshing;

    const p = (async () => {
      if (isSafeParam()) {
        console.info('[ACDV] safe mode via ?safe=1 — unloading all');
        ACDV._safeMode = true;
        ACDV.unloadAll();
        hideBanner();
        return;
      }

      let data = null;
      try {
        const res = await fetch('/api/overlay').then(r => r.json());
        if (res && res.ok) data = res;
      } catch (e) {
        console.warn('[ACDV] /api/overlay fetch failed:', e);
        return;
      }
      if (!data) return;

      if (data.safe_mode) {
        console.info('[ACDV] safe_mode=on — unloading all');
        ACDV._safeMode = true;
        ACDV.unloadAll();
        hideBanner();
        return;
      }
      ACDV._safeMode = false;

      const overlays = data.overlays || [];
      const active = new Set();

      for (const ov of overlays) {
        const name = ov.name;
        if (!name) continue;
        active.add(name);

        const cssOn = !!ov.css_enabled;
        const jsOn  = !!ov.js_enabled;
        const cssEtag = ov.css_etag || '';
        const jsEtag  = ov.js_etag  || '';

        const existing = ACDV._injected.get(name) || {};

        // CSS
        if (!cssOn) {
          if (existing.linkEl) {
            try { existing.linkEl.parentNode.removeChild(existing.linkEl); } catch (e) {}
            existing.linkEl = null; existing.cssHref = null; existing.cssEtag = null;
          }
        } else if (ov.css) {
          const need = !existing.linkEl || existing.cssEtag !== cssEtag;
          if (need) {
            const linkEl = await injectLink(ov.css, name, cssEtag);
            existing.linkEl = linkEl;
            existing.cssHref = ov.css;
            existing.cssEtag = cssEtag;
          }
        }

        // JS
        if (!jsOn) {
          // ⭐ C6: KHÔNG unload toàn bộ — chỉ dọn JS, giữ CSS
          ACDV._unloadJsOnly(name);
          existing.scriptEl = null;
          existing.jsSrc = null;
          existing.jsEtag = null;
        } else if (ov.js) {
          const need = !existing.scriptEl || existing.jsEtag !== jsEtag;
          if (need) {
            // Trước khi inject JS mới, dọn record cũ (nếu có) để tránh double-init
            ACDV._unloadJsOnly(name);
            const scriptEl = await injectScript(ov.js, name, jsEtag);
            existing.scriptEl = scriptEl;
            existing.jsSrc = ov.js;
            existing.jsEtag = jsEtag;
          }
        }

        ACDV._injected.set(name, existing);
      }

      for (const [name] of Array.from(ACDV._injected)) {
        if (!active.has(name)) ACDV.unload(name);
      }

      setTimeout(checkDuplicateIds, 200);

      if (active.size > 0) showBanner(active.size);
      else hideBanner();
    })();

    ACDV._refreshing = p;
    try { await p; } finally { ACDV._refreshing = null; }
  }

  function showBanner(count) {
    hideBanner();
    const b = document.createElement('div');
    b.id = 'overlayBanner';
    b.innerHTML = `
      <span>🎨 ${count} overlay${count !== 1 ? 's' : ''} active</span>
      <button id="overlaySafeMode" title="Reload without overlays">🛑 Disable</button>
      <button id="overlayDismiss">×</button>
    `;
    b.style.cssText = 'position:fixed;bottom:10px;right:10px;background:#2d2d2d;color:#fff;padding:8px 12px;border-radius:6px;z-index:99999;font:12px -apple-system,sans-serif;display:flex;gap:8px;align-items:center;box-shadow:0 2px 8px rgba(0,0,0,0.4);';
    b.querySelector('#overlaySafeMode').addEventListener('click', () => {
      ACDV.unloadAll();
      location.href = location.pathname + '?safe=1';
    });
    b.querySelector('#overlayDismiss').addEventListener('click', () => b.remove());
    document.body.appendChild(b);
    setTimeout(() => { if (b.parentNode) b.remove(); }, 12000);
  }

  function hideBanner() {
    const b = document.getElementById('overlayBanner');
    if (b) b.remove();
  }

  function bootstrap() {
    if (window.App && typeof App.whenReady === 'function') {
      App.whenReady(() => ACDV._setAppReady());
    } else {
      let attempts = 0;
      const poll = () => {
        if (window.App && App._isReady === true) { ACDV._setAppReady(); return; }
        if (++attempts > 50) {
          console.warn('[ACDV] App never signaled ready — assuming ready');
          ACDV._setAppReady();
          return;
        }
        setTimeout(poll, 100);
      };
      poll();
    }

    refresh().catch(e => console.error('[ACDV] refresh:', e));
  }

  window.OverlayLoader = {
    refresh,
    unload:     (name) => ACDV.unload(name),
    unloadAll:  () => ACDV.unloadAll(),
    status:     () => ACDV.status(),
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrap);
  } else {
    setTimeout(bootstrap, 0);
  }

  console.info(`[ACDV] Overlay Runtime v${RUNTIME_VERSION} loaded`);
})();