/* ACDV Settings UI — global + per-module settings + overlay toggles + About */
(function () {
  'use strict';

  const state = {
    global: null,
    modules: [],
    version: '1.3.0',
    activeTab: 'general',
  };

  function q(sel, root) { return (root || document).querySelector(sel); }
  function qa(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

  // ============================================================ //
  //  USER GUIDE (rendered in About tab)
  // ============================================================ //
  const GUIDE_HTML = `
    <details class="about-details" open>
      <summary>1. Tạo và mở project</summary>
      <div class="content">
        <ul>
          <li>Nhấn nút <code>＋</code> trên toolbar hoặc <code>New Project</code> ở màn hình chính</li>
          <li>Chọn tên + ngôn ngữ → hệ thống tự tạo file starter (<code>main.py</code>, <code>index.js</code>, …)</li>
          <li>Upload project có sẵn dạng ZIP qua nút <code>📤</code> trong tab Projects</li>
          <li>Click tên project ở sidebar để mở (double-tap để xoá trên mobile)</li>
        </ul>
      </div>
    </details>
    <details class="about-details">
      <summary>2. Editor & Tabs</summary>
      <div class="content">
        <ul>
          <li>Click file trong Explorer để mở tab</li>
          <li><code>Ctrl+S</code> — Lưu · <code>Ctrl+Enter</code> — Chạy file hiện tại</li>
          <li>Tab có chấm <code>●</code> = chưa lưu</li>
          <li>Click <code>×</code> để đóng tab (cảnh báo nếu chưa lưu)</li>
          <li>Hỗ trợ syntax highlighting: Python, JS, HTML, CSS, XML, Markdown</li>
        </ul>
      </div>
    </details>
    <details class="about-details">
      <summary>3. Chạy code</summary>
      <div class="content">
        <ul>
          <li>Hỗ trợ: <code>.py</code>, <code>.js</code>, <code>.sh</code>, <code>.bash</code></li>
          <li>Nhấn <code>▶</code> trên toolbar hoặc icon <code>▶</code> cạnh file trong Explorer</li>
          <li>Output stream realtime vào panel Run</li>
          <li>Nhấn <code>■</code> để dừng — SIGTERM trước, SIGKILL nếu quá 2s</li>
          <li>Log lưu tự động trong <code>core/data/logs/</code></li>
          <li>Khi đóng browser → auto-stop process (nếu <code>auto_stop_on_disconnect=true</code>)</li>
        </ul>
      </div>
    </details>
    <details class="about-details">
      <summary>4. Cài Module</summary>
      <div class="content">
        <ul>
          <li>Module = thư mục trong <code>modules/</code> có <code>main.py</code> + <code>init.txt</code></li>
          <li>Upload ZIP qua nút <code>📤</code> trong tab Modules</li>
          <li>Reload: nhấn <code>⟳</code> · Uninstall: nhấn <code>🗑</code></li>
          <li>Module có thể thêm: UI buttons, custom routes, overlay CSS/JS, diagnostics, settings schema</li>
          <li>Xem <code>modules/demo_module/</code> để có template</li>
        </ul>
      </div>
    </details>
    <details class="about-details">
      <summary>5. Diagnostics (VS Code style)</summary>
      <div class="content">
        <ul>
          <li>Module đăng ký <code>diagnose()</code> để báo lỗi/cảnh báo</li>
          <li>Hiển thị dạng gạch chân + trong panel Problems</li>
          <li>Click vào lỗi để nhảy tới đúng dòng</li>
          <li>Bật auto-run: Settings → Diagnostics → Auto-run on save</li>
        </ul>
      </div>
    </details>
    <details class="about-details">
      <summary>6. Settings</summary>
      <div class="content">
        <ul>
          <li><strong>General</strong> — Theme, cấu hình chung</li>
          <li><strong>Editor</strong> — Font size, tab size, line wrap, auto-save</li>
          <li><strong>Diagnostics</strong> — Tự động chạy, hiển thị inline</li>
          <li><strong>Overlays</strong> — Bật/tắt CSS/JS từ module, safe mode</li>
          <li><strong>Modules</strong> — Cấu hình riêng cho từng module</li>
          <li><strong>About</strong> — Thông tin + hướng dẫn (tab này)</li>
        </ul>
      </div>
    </details>
    <details class="about-details">
      <summary>7. Troubleshooting</summary>
      <div class="content">
        <ul>
          <li>Port bị chiếm: <code>python3 main.py --port 9000</code></li>
          <li>Kẹt process: <code>pkill -f "python main.py"; fuser -k 8765/tcp</code></li>
          <li>Reset settings: xoá <code>core/data/settings.json</code></li>
          <li>Safe mode (không overlay): mở <code>/?safe=1</code></li>
          <li>Nếu <code>main.py</code> bị đè bởi module: verify <code>head -1 main.py</code> = <code>#!/usr/bin/env python3</code></li>
        </ul>
      </div>
    </details>
  `;

  // ============================================================ //
  //  OPEN / HIDE
  // ============================================================ //
  async function open(tab) {
    state.activeTab = tab || 'general';
    document.getElementById('settingsModal').style.display = 'flex';
    await loadAll();
    render();
  }

  function hide() {
    document.getElementById('settingsModal').style.display = 'none';
  }

  async function loadAll() {
    try {
      const [gs, ms, st] = await Promise.all([
        fetch('/api/settings').then(r => r.json()),
        fetch('/api/settings/modules', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({}),
        }).then(r => r.json()),
        fetch('/api/status').then(r => r.json()).catch(() => null),
      ]);
      if (gs && gs.ok) state.global = gs.settings;
      if (ms && ms.ok) state.modules = ms.modules;
      if (st && st.version) state.version = st.version;
    } catch (e) {
      console.error('[Settings] load error', e);
    }
  }

  // ============================================================ //
  //  RENDER
  // ============================================================ //
  function render() {
    const tabBar = document.getElementById('settingsTabs');
    const content = document.getElementById('settingsContent');
    if (!tabBar || !content) return;
    tabBar.innerHTML = '';

    const tabs = [
      { id: 'general',     label: '⚙ General' },
      { id: 'editor',      label: '📝 Editor' },
      { id: 'diagnostics', label: '🩺 Diagnostics' },
      { id: 'overlays',    label: '🎨 Overlays' },
      { id: 'modules',     label: '🧩 Modules' },
      { id: 'about',       label: 'ℹ About' },
    ];
    for (const t of tabs) {
      const el = document.createElement('button');
      el.className = 'settings-tab' + (state.activeTab === t.id ? ' active' : '');
      el.textContent = t.label;
      el.addEventListener('click', () => { state.activeTab = t.id; render(); });
      tabBar.appendChild(el);
    }

    content.innerHTML = '';
    if (state.activeTab === 'general') content.appendChild(renderGlobalGeneral());
    else if (state.activeTab === 'editor') content.appendChild(renderGlobalEditor());
    else if (state.activeTab === 'diagnostics') content.appendChild(renderGlobalDiagnostics());
    else if (state.activeTab === 'overlays') content.appendChild(renderGlobalOverlays());
    else if (state.activeTab === 'modules') content.appendChild(renderModules());
    else if (state.activeTab === 'about') content.appendChild(renderAbout());
  }

  function renderField(key, spec, value) {
    const row = document.createElement('div');
    row.className = 'settings-field';
    const label = document.createElement('label');
    label.textContent = spec.label || key;
    label.className = 'settings-label';
    row.appendChild(label);
    if (spec.description) {
      const desc = document.createElement('div');
      desc.className = 'settings-desc';
      desc.textContent = spec.description;
      row.appendChild(desc);
    }
    let input;
    const t = spec.type || 'string';
    if (t === 'boolean') {
      input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = !!value;
    } else if (t === 'number') {
      input = document.createElement('input');
      input.type = 'number';
      input.value = value != null ? value : (spec.default != null ? spec.default : 0);
      if ('min' in spec) input.min = spec.min;
      if ('max' in spec) input.max = spec.max;
      if ('step' in spec) input.step = spec.step;
    } else if (t === 'select') {
      input = document.createElement('select');
      for (const opt of (spec.options || [])) {
        const o = document.createElement('option');
        o.value = opt;
        o.textContent = opt;
        if (opt === value) o.selected = true;
        input.appendChild(o);
      }
    } else {
      input = document.createElement('input');
      input.type = 'text';
      input.value = value != null ? value : (spec.default || '');
    }
    input.dataset.key = key;
    input.dataset.type = t;
    input.className = 'settings-input';
    row.appendChild(input);
    return row;
  }

  function collectValues(container) {
    const out = {};
    qa('[data-key]', container).forEach(el => {
      const k = el.dataset.key;
      const t = el.dataset.type;
      if (t === 'boolean') out[k] = el.checked;
      else if (t === 'number') out[k] = parseFloat(el.value) || 0;
      else out[k] = el.value;
    });
    return out;
  }

  // ⭐ FIX (v1.3.2): apply settings ngay sau khi save (không đợi WS),
  // và vẫn để WS handler trong app.js re-apply (idempotent).
  async function saveSettings(payload) {
    let res;
    try {
      res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }).then(r => r.json());
    } catch (e) {
      return { ok: false, error: e.message };
    }
    if (res && res.ok && res.settings && window.App && window.App.editor &&
        typeof window.App.editor.onSettingsChanged === 'function') {
      try { window.App.editor.onSettingsChanged(res.settings); } catch (e) {}
    }
    return res;
  }

  function renderGlobalGeneral() {
    const wrap = document.createElement('div');
    wrap.className = 'settings-section';
    const gs = state.global || {};
    // ⭐ FIX: options theme phải là theme hợp lệ của CodeMirror 5.
    // `light`/`dark` không tồn tại → setOption xong nhìn như bị lỗi CSS.
    wrap.appendChild(renderField('theme',
      { label: 'Theme', type: 'select',
        options: ['dracula', 'default', 'material', 'monokai', 'solarized', 'eclipse'] },
      gs.theme || 'dracula'));
    wrap.appendChild(makeSaveBar(async () => {
      const v = collectValues(wrap);
      const res = await saveSettings(v);
      if (res && res.ok) toast('Settings saved');
      else toast('Save failed: ' + (res && res.error ? res.error : 'unknown'), 'error');
    }));
    return wrap;
  }

  function renderGlobalEditor() {
    const wrap = document.createElement('div');
    wrap.className = 'settings-section';
    const ed = (state.global && state.global.editor) || {};
    const schema = {
      font_size: { label: 'Font size', type: 'number', min: 10, max: 32 },
      tab_size:  { label: 'Tab size',  type: 'number', min: 1,  max: 8  },
      line_wrap: { label: 'Line wrap', type: 'boolean' },
      auto_save: { label: 'Auto save', type: 'boolean' },
    };
    for (const [k, s] of Object.entries(schema)) {
      wrap.appendChild(renderField('editor.' + k, s, ed[k]));
    }
    wrap.appendChild(makeSaveBar(async () => {
      const flat = collectValues(wrap);
      const nested = { editor: {} };
      for (const [k, v] of Object.entries(flat)) {
        const [, b] = k.split('.');
        nested.editor[b] = v;
      }
      const res = await saveSettings(nested);
      if (res && res.ok) toast('Editor settings saved');
      else toast('Save failed', 'error');
    }));
    return wrap;
  }

  function renderGlobalDiagnostics() {
    const wrap = document.createElement('div');
    wrap.className = 'settings-section';
    const d = (state.global && state.global.diagnostics) || {};
    const schema = {
      auto_run_on_save: { label: 'Auto-run on save', type: 'boolean',
        description: 'Re-scan file each time you save' },
      auto_run_on_open: { label: 'Auto-run on open', type: 'boolean',
        description: 'Scan file when opened' },
      show_inline: { label: 'Show inline markers', type: 'boolean' },
    };
    for (const [k, s] of Object.entries(schema)) {
      wrap.appendChild(renderField('diagnostics.' + k, s, d[k]));
    }
    wrap.appendChild(makeSaveBar(async () => {
      const flat = collectValues(wrap);
      const nested = { diagnostics: {} };
      for (const [k, v] of Object.entries(flat)) {
        const [, b] = k.split('.');
        nested.diagnostics[b] = v;
      }
      const res = await saveSettings(nested);
      if (res && res.ok) toast('Diagnostics settings saved');
      else toast('Save failed', 'error');
    }));
    return wrap;
  }

  function renderGlobalOverlays() {
    const wrap = document.createElement('div');
    wrap.className = 'settings-section';
    const ov = (state.global && state.global.overlays) || {};

    wrap.appendChild(renderField('overlays.safe_mode',
      { label: 'Safe mode', type: 'boolean',
        description: 'Disable ALL module overlays (CSS + JS)' },
      !!ov.safe_mode));

    const per = ov.per_module || {};
    const table = document.createElement('div');
    table.className = 'overlays-table';

    const overlayMods = state.modules.filter(m => {
      const o = m.overlay || {};
      return o.css || o.js;
    });

    if (overlayMods.length === 0) {
      table.innerHTML = '<div class="settings-desc">No module overlays detected.</div>';
    } else {
      for (const m of overlayMods) {
        const conf = per[m.name] || {};
        const cssOn = conf.css !== false;
        const jsOn = conf.js !== false;
        const row = document.createElement('div');
        row.className = 'overlays-row';
        row.innerHTML = `
          <div class="overlays-name">${m.name} <small>v${m.version || ''}</small></div>
          <label class="overlays-toggle">
            <input type="checkbox" data-name="${m.name}" data-kind="css" ${cssOn ? 'checked' : ''}/> CSS
          </label>
          <label class="overlays-toggle">
            <input type="checkbox" data-name="${m.name}" data-kind="js" ${jsOn ? 'checked' : ''}/> JS
          </label>
        `;
        table.appendChild(row);
      }
    }
    wrap.appendChild(table);

    wrap.appendChild(makeSaveBar(async () => {
      const safe_mode = q('[data-key="overlays.safe_mode"]', wrap).checked;
      const per_module = {};
      qa('input[data-kind]', wrap).forEach(el => {
        const name = el.dataset.name;
        per_module[name] = per_module[name] || {};
        per_module[name][el.dataset.kind] = el.checked;
      });
      const res = await saveSettings({ overlays: { safe_mode, per_module } });
      if (res && res.ok) {
        toast('Overlay settings saved — refreshing');
        if (window.OverlayLoader) OverlayLoader.refresh();
      } else toast('Save failed', 'error');
    }));
    return wrap;
  }

  function renderModules() {
    const wrap = document.createElement('div');
    wrap.className = 'settings-section';
    if (!state.modules.length) {
      wrap.innerHTML = '<div class="settings-desc">No modules with settings schema.</div>';
      return wrap;
    }
    for (const m of state.modules) {
      const item = document.createElement('div');
      item.className = 'module-settings-item';
      const hdr = document.createElement('div');
      hdr.className = 'module-settings-header';
      hdr.innerHTML = `<strong>${m.name}</strong>
        <small>v${m.version || ''}</small>
        <span class="module-settings-desc">${m.description || ''}</span>`;
      item.appendChild(hdr);

      const body = document.createElement('div');
      body.className = 'module-settings-body';
      for (const [k, spec] of Object.entries(m.schema || {})) {
        body.appendChild(renderField(k, spec, m.values[k]));
      }
      item.appendChild(body);

      const bar = document.createElement('div');
      bar.className = 'settings-savebar';
      const btn = document.createElement('button');
      btn.className = 'btn-primary';
      btn.textContent = 'Save';
      btn.addEventListener('click', async () => {
        const values = collectValues(body);
        const res = await fetch('/api/settings/module/set', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: m.name, values }),
        }).then(r => r.json());
        if (res && res.ok) toast(`Saved: ${m.name}`);
        else if (res && res.errors) toast('Error: ' + res.errors.join('; '), 'error');
      });
      bar.appendChild(btn);
      item.appendChild(bar);

      wrap.appendChild(item);
    }
    return wrap;
  }

  // ⭐ v1.3.0: About tab — logo + info + user guide
  function renderAbout() {
    const wrap = document.createElement('div');
    wrap.className = 'settings-section';

    // ---- Hero ----
    const hero = document.createElement('div');
    hero.className = 'about-hero';
    hero.innerHTML = `
      <svg class="about-hero-logo" width="80" height="80" viewBox="0 0 100 100" aria-hidden="true">
        <defs>
          <linearGradient id="aboutLogoGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#1177bb"/>
            <stop offset="100%" stop-color="#0e639c"/>
          </linearGradient>
        </defs>
        <polygon points="50,5 90,27 90,73 50,95 10,73 10,27"
                 fill="url(#aboutLogoGrad)" stroke="#4af" stroke-width="2.5"/>
        <text x="50" y="46" text-anchor="middle" fill="#fff"
              font-size="18" font-weight="bold" font-family="sans-serif">ACDV</text>
        <text x="50" y="61" text-anchor="middle" fill="#4af"
              font-size="11" font-family="sans-serif">TEAMS</text>
        <text x="50" y="76" text-anchor="middle" fill="#aaa"
              font-size="9" font-family="monospace">CODER</text>
      </svg>
      <div class="about-hero-text">
        <h3>ACDV-Teams Coder</h3>
        <div class="version">v${state.version || '1.3.0'}</div>
        <div class="tagline">Local web IDE · Python stdlib backend · CodeMirror frontend</div>
      </div>
    `;
    wrap.appendChild(hero);

    // ---- System info ----
    const sys = document.createElement('div');
    sys.className = 'about-card';
    sys.innerHTML = `
      <h4>ℹ Thông tin hệ thống</h4>
      <div class="about-grid">
        <span class="label">Version</span><span class="value">${state.version || '?'}</span>
        <span class="label">Modules</span><span class="value">${state.modules.length}</span>
        <span class="label">Platform</span><span class="value">${navigator.platform || '?'}</span>
        <span class="label">Backend</span><span class="value">Python stdlib</span>
        <span class="label">Frontend</span><span class="value">CodeMirror 5 · Vanilla JS</span>
      </div>
    `;
    wrap.appendChild(sys);

    // ---- Usage guide ----
    const guide = document.createElement('div');
    guide.className = 'about-card';
    guide.innerHTML = `<h4>📖 Hướng dẫn sử dụng</h4>${GUIDE_HTML}`;
    wrap.appendChild(guide);

    // ---- Links ----
    const links = document.createElement('div');
    links.className = 'about-card';
    links.innerHTML = `
      <h4>🔗 Liên kết</h4>
      <div class="about-links">
        <a href="/api/status" target="_blank" rel="noopener">API status</a>
        <a href="/api/modules" target="_blank" rel="noopener">Module list</a>
        <a href="/api/settings" target="_blank" rel="noopener">Settings JSON</a>
      </div>
      <div class="settings-desc" style="margin-top:8px;">
        Educational / personal use. Không cài module từ nguồn không tin cậy.
      </div>
    `;
    wrap.appendChild(links);

    return wrap;
  }

  function makeSaveBar(onSave) {
    const bar = document.createElement('div');
    bar.className = 'settings-savebar';
    const btn = document.createElement('button');
    btn.className = 'btn-primary';
    btn.textContent = 'Save';
    btn.addEventListener('click', onSave);
    bar.appendChild(btn);
    return bar;
  }

  function toast(msg, kind) {
    if (window.AppToast) window.AppToast(msg, kind);
    else console.log('[Settings]', msg);
  }

  document.addEventListener('DOMContentLoaded', () => {
    const close = document.getElementById('settingsClose');
    if (close) close.addEventListener('click', hide);
    const modal = document.getElementById('settingsModal');
    if (modal) {
      modal.addEventListener('click', (e) => { if (e.target === modal) hide(); });
    }
  });

  window.SettingsUI = { open, hide };
})();