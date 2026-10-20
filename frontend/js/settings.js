/* ACDV Settings UI — global + per-module settings + overlay toggles */
(function () {
  'use strict';

  const state = {
    global: null,
    modules: [],
    activeTab: 'general',
  };

  function q(sel, root) { return (root || document).querySelector(sel); }
  function qa(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

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
      const [gs, ms] = await Promise.all([
        fetch('/api/settings').then(r => r.json()),
        fetch('/api/settings/modules', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({}),
        }).then(r => r.json()),
      ]);
      if (gs && gs.ok) state.global = gs.settings;
      if (ms && ms.ok) state.modules = ms.modules;
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
      { id: 'editor',      label: '📝 Editor' },
      { id: 'diagnostics', label: '🩺 Diagnostics' },
      { id: 'overlays',    label: '🎨 Overlays' },
      { id: 'modules',     label: '🧩 Modules' },
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

  async function saveSettings(payload) {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).then(r => r.json());
    return res;
  }

  function renderGlobalGeneral() {
    const wrap = document.createElement('div');
    wrap.className = 'settings-section';
    const gs = state.global || {};
    wrap.appendChild(renderField('theme',
      { label: 'Theme', type: 'select', options: ['dracula', 'light', 'dark'] },
      gs.theme));
    wrap.appendChild(makeSaveBar(async () => {
      const v = collectValues(wrap);
      const res = await saveSettings(v);
      if (res && res.ok) toast('Settings saved');
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
        const res = await fetch('/api/settings/module/set', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: m.name, values }),
        }).then(r => r.json());
        if (res && res.ok) toast(`Saved: ${m.name}`);
        else if (res && res.errors) toast('Error: ' + res.errors.join('; '));
      });
      bar.appendChild(btn);
      item.appendChild(bar);

      wrap.appendChild(item);
    }
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

  function toast(msg) {
    if (window.AppToast) window.AppToast(msg);
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