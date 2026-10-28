/* ACDV Settings UI — global + per-module settings + overlay toggles + server config + About
 * v2.0.1:
 * - M1: hiển thị đầy đủ error (error + errors[]) ở mọi save bar.
 */
(function () {
  'use strict';

  const state = {
    global: null,
    modules: [],
    config: null,
    version: '2.0.1',
    activeTab: 'general',
  };

  function q(sel, root) { return (root || document).querySelector(sel); }
  function qa(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

  const GUIDE_HTML = `
    <details class="about-details" open>
      <summary>1. Tạo và mở project</summary>
      <div class="content">
        <ul>
          <li>Nhấn nút <code>＋</code> trên toolbar hoặc <code>New Project</code> ở màn hình chính</li>
          <li>Chọn tên + ngôn ngữ → hệ thống tự tạo file starter</li>
          <li>Upload project có sẵn dạng ZIP qua nút <code>📤</code> trong tab Projects</li>
          <li>Click tên project ở sidebar để mở</li>
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
          <li>Undo/Redo per-tab (giữ history khi đổi tab)</li>
        </ul>
      </div>
    </details>
    <details class="about-details">
      <summary>3. Module Storage (💾)</summary>
      <div class="content">
        <ul>
          <li>Mỗi module có storage riêng — quota <strong>512MB</strong></li>
          <li>Click nút <code>💾</code> trong tab Modules để mở</li>
          <li>Upload file (chunked 4MB), download, xoá, export ZIP</li>
          <li>Cảnh báo khi dùng > 90%, từ chối upload khi > 98%</li>
        </ul>
      </div>
    </details>
    <details class="about-details">
      <summary>4. Chạy code</summary>
      <div class="content">
        <ul>
          <li>Hỗ trợ: <code>.py</code>, <code>.js</code>, <code>.sh</code>, <code>.bash</code></li>
          <li>Nhấn <code>▶</code> trên toolbar hoặc cạnh file trong Explorer</li>
          <li>Output stream realtime vào panel Run</li>
          <li>Nhấn <code>■</code> để dừng — SIGTERM → SIGKILL nếu quá 2s</li>
        </ul>
      </div>
    </details>
    <details class="about-details">
      <summary>5. Terminal</summary>
      <div class="content">
        <ul>
          <li>Mở/đóng: <code>Ctrl+\`</code> hoặc nút ⌨</li>
          <li>Shell thật qua PTY (POSIX), hỗ trợ vim/htop/less</li>
          <li>Session gắn với WS — đóng browser → kill session</li>
        </ul>
      </div>
    </details>
    <details class="about-details">
      <summary>6. Diagnostics</summary>
      <div class="content">
        <ul>
          <li>Module báo lỗi/cảnh báo qua <code>diagnose()</code></li>
          <li>Gạch chân + panel Problems, click để nhảy tới dòng</li>
          <li>Bật auto-run trong Settings → Diagnostics</li>
        </ul>
      </div>
    </details>
    <details class="about-details">
      <summary>7. Server Config</summary>
      <div class="content">
        <ul>
          <li>Tab <strong>🖥 Server</strong> cho phép chỉnh <code>config.json</code> từ UI</li>
          <li>Field có badge <span class="restart-badge">requires restart</span> cần restart server</li>
          <li>Sau khi save, hỏi restart ngay nếu cần</li>
        </ul>
      </div>
    </details>
    <details class="about-details">
      <summary>8. Troubleshooting</summary>
      <div class="content">
        <ul>
          <li>Port bị chiếm: <code>python3 main.py --port 9000</code></li>
          <li>Kẹt process: <code>pkill -f "python main.py"</code></li>
          <li>Reset settings: xoá <code>core/data/settings.json</code></li>
          <li>Safe mode (không overlay): <code>/?safe=1</code></li>
        </ul>
      </div>
    </details>
  `;

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
      const [gs, ms, st, cfg] = await Promise.all([
        fetch('/api/settings').then(r => r.json()),
        fetch('/api/settings/modules', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({}),
        }).then(r => r.json()),
        fetch('/api/status').then(r => r.json()).catch(() => null),
        fetch('/api/config').then(r => r.json()).catch(() => null),
      ]);
      if (gs && gs.ok) state.global = gs.settings;
      if (ms && ms.ok) state.modules = ms.modules;
      if (st && st.version) state.version = st.version;
      if (cfg && cfg.ok) state.config = cfg.config;
    } catch (e) {
      console.error('[Settings] load error', e);
    }
  }

  function render() {
    const tabBar = document.getElementById('settingsTabs');
    const content = document.getElementById('settingsContent');
    if (!tabBar || !content) return;
    tabBar.innerHTML = '';

    const tabs = [
      { id: 'general',     label: '⚙ General' },
      { id: 'server',      label: '🖥 Server' },
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
    else if (state.activeTab === 'server') content.appendChild(renderServer());
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
      if (spec.integer) input.step = 1;
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

  // ⭐ M1: helper format error thống nhất
  function formatSaveError(res) {
    if (!res) return 'unknown';
    if (Array.isArray(res.errors) && res.errors.length) return res.errors.join('; ');
    if (res.error) return res.error;
    return 'unknown';
  }

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
    wrap.appendChild(renderField('theme',
      { label: 'Theme', type: 'select',
        options: ['dracula', 'default', 'material', 'monokai', 'solarized', 'eclipse'] },
      gs.theme || 'dracula'));
    wrap.appendChild(makeSaveBar(async () => {
      const v = collectValues(wrap);
      const res = await saveSettings(v);
      if (res && res.ok) toast('Settings saved');
      else toast('Save failed: ' + formatSaveError(res), 'error');
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
      else toast('Save failed: ' + formatSaveError(res), 'error');
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
      else toast('Save failed: ' + formatSaveError(res), 'error');
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
      } else {
        toast('Save failed: ' + formatSaveError(res), 'error');
      }
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
        let res;
        try {
          res = await fetch('/api/settings/module/set', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: m.name, values }),
          }).then(r => r.json());
        } catch (e) {
          res = { ok: false, error: e.message };
        }
        if (res && res.ok) toast(`Saved: ${m.name}`);
        else toast('Error: ' + formatSaveError(res), 'error');
      });
      bar.appendChild(btn);
      item.appendChild(bar);

      wrap.appendChild(item);
    }
    return wrap;
  }

  function renderServer() {
    const wrap = document.createElement('div');
    wrap.className = 'settings-section';

    if (!state.config) {
      wrap.innerHTML = '<div class="settings-error">✗ Không tải được /api/config. Backend có thể chưa update.</div>';
      return wrap;
    }

    const info = document.createElement('div');
    info.className = 'settings-info-banner';
    info.innerHTML = `
      <span>ℹ</span>
      <span>Field có badge <span class="restart-badge">requires restart</span>
        chỉ có hiệu lực <strong>sau khi restart server</strong>. Bạn sẽ được hỏi restart ngay sau khi save nếu cần.</span>
    `;
    wrap.appendChild(info);

    const groups = [
      { title: '🌐 Server binding',  keys: ['host', 'port'] },
      { title: '🔒 TLS / SSL',       keys: ['ssl.enabled', 'ssl.auto_generate'] },
      { title: '⚙️ Runtime',          keys: [
          'log_level',
          'auto_stop_on_disconnect',
          'auto_detect_modules',
          'module_watch_interval',
          'enable_system_controls',
        ] },
      { title: '💾 Storage',         keys: ['module_storage_quota'] },
      { title: '⌨ Terminal',         keys: ['terminal.shell', 'terminal.max_sessions'] },
    ];

    const collected = {};
    for (const group of groups) {
      const g = document.createElement('div');
      g.className = 'settings-group';
      const h = document.createElement('h4');
      h.className = 'settings-group-title';
      h.textContent = group.title;
      g.appendChild(h);

      for (const key of group.keys) {
        const entry = state.config[key];
        if (!entry) continue;
        const spec = entry.spec;
        const field = renderField(key, spec, entry.value);

        if (spec.restart) {
          const label = field.querySelector('label');
          if (label) {
            const badge = document.createElement('span');
            badge.className = 'restart-badge';
            badge.textContent = 'requires restart';
            badge.title = 'Chỉ có hiệu lực sau khi restart server';
            label.appendChild(badge);
          }
        }

        if (key === 'module_storage_quota') {
          const input = field.querySelector('[data-key]');
          const hint = document.createElement('div');
          hint.className = 'settings-hint';
          const updateHint = () => {
            const bytes = parseFloat(input.value) || 0;
            hint.textContent = `≈ ${(bytes / (1024 * 1024)).toFixed(1)} MB`;
          };
          if (input) {
            input.addEventListener('input', updateHint);
            updateHint();
          }
          field.appendChild(hint);
        }

        g.appendChild(field);
        const input = field.querySelector('[data-key]');
        if (input) collected[key] = input;
      }
      wrap.appendChild(g);
    }

    const bar = document.createElement('div');
    bar.className = 'settings-savebar';
    const saveBtn = document.createElement('button');
    saveBtn.className = 'btn-primary';
    saveBtn.textContent = 'Save config';
    saveBtn.addEventListener('click', async () => {
      const patch = {};
      for (const [key, input] of Object.entries(collected)) {
        const type = input.dataset.type;
        if (type === 'boolean') patch[key] = input.checked;
        else if (type === 'number') patch[key] = parseFloat(input.value) || 0;
        else patch[key] = input.value;
      }

      saveBtn.disabled = true;
      saveBtn.textContent = 'Saving…';
      let res;
      try {
        res = await fetch('/api/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ patch }),
        }).then(r => r.json());
      } catch (e) {
        res = { ok: false, error: e.message };
      } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save config';
      }

      if (res && res.ok) {
        try {
          const cfg = await fetch('/api/config').then(r => r.json());
          if (cfg && cfg.ok) state.config = cfg.config;
        } catch (e) {}
        render();

        if (res.restart_required) {
          const doRestart = confirm(
            '✓ Đã lưu config.\n\n' +
            'Một số thay đổi cần RESTART server để có hiệu lực ' +
            '(host, port, SSL, watcher…).\n\n' +
            'Restart ngay bây giờ?\n\n' +
            '(Nếu bind port mới thất bại, bạn có thể phải sửa config.json thủ công ' +
            'và chạy lại: python3 main.py)'
          );
          if (doRestart && window.App && typeof App.restartServer === 'function') {
            hide();
            App.restartServer();
          } else {
            toast('Đã lưu — nhớ restart server sau');
          }
        } else {
          toast('Config saved');
        }
      } else {
        toast('Save failed: ' + formatSaveError(res), 'error');
      }
    });
    bar.appendChild(saveBtn);
    wrap.appendChild(bar);

    return wrap;
  }

  function renderAbout() {
    const wrap = document.createElement('div');
    wrap.className = 'settings-section';

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
        <div class="version">v${state.version || '2.0.1'}</div>
        <div class="tagline">Local web IDE · Python stdlib backend · CodeMirror frontend</div>
      </div>
    `;
    wrap.appendChild(hero);

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
        <span class="label">Storage quota</span><span class="value">512 MB / module</span>
      </div>
    `;
    wrap.appendChild(sys);

    const guide = document.createElement('div');
    guide.className = 'about-card';
    guide.innerHTML = `<h4>📖 Hướng dẫn sử dụng</h4>${GUIDE_HTML}`;
    wrap.appendChild(guide);

    const links = document.createElement('div');
    links.className = 'about-card';
    links.innerHTML = `
      <h4>🔗 Liên kết</h4>
      <div class="about-links">
        <a href="/api/status" target="_blank" rel="noopener">API status</a>
        <a href="/api/config" target="_blank" rel="noopener">Config JSON</a>
        <a href="/api/modules" target="_blank" rel="noopener">Module list</a>
        <a href="/api/settings" target="_blank" rel="noopener">Settings JSON</a>
        <a href="/api/boot" target="_blank" rel="noopener">Boot info</a>
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

  window.SettingsUI = { open, hide, reload: async () => { await loadAll(); render(); } };
})();