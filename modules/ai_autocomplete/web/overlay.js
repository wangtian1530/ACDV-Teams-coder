/* AI Autocomplete overlay — © ACDV-Teams */
(function () {
  'use strict';
  const TAG = '[ai_autocomplete]';
  const log = (...a) => console.log(TAG, ...a);

  let activeKeyMap = null;
  let activeGhostEl = null;
  let activePos = null;

  function toast(msg, type) {
    let box = document.getElementById('ai-ac-toasts');
    if (!box) {
      box = document.createElement('div');
      box.id = 'ai-ac-toasts';
      box.style.cssText =
        'position:fixed;bottom:20px;right:20px;z-index:99999;display:flex;' +
        'flex-direction:column;gap:8px;max-width:340px;pointer-events:none;';
      document.body.appendChild(box);
    }
    const colors = { info: '#89b4fa', warning: '#f9e2af', error: '#f38ba8', ok: '#a6e3a1' };
    const c = colors[type] || colors.info;
    const el = document.createElement('div');
    el.style.cssText =
      'padding:10px 14px;border-radius:8px;background:#181825;color:' + c +
      ';border:1px solid ' + c + ';font-size:13px;font-family:monospace;' +
      'box-shadow:0 4px 14px rgba(0,0,0,.5);pointer-events:auto;' +
      'transition:opacity .25s;';
    el.textContent = msg;
    box.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 3500);
  }

  function cleanup(cm) {
    if (activeGhostEl && activeGhostEl.parentNode) activeGhostEl.parentNode.removeChild(activeGhostEl);
    activeGhostEl = null;
    if (activeKeyMap && cm) { try { cm.removeKeyMap(activeKeyMap); } catch (_) {} }
    activeKeyMap = null;
    activePos = null;
    document.querySelectorAll('.ai-ac-loading').forEach(e => e.remove());
  }

  function getCM() {
    const A = window.App;
    return (A && A.editor && A.editor.cm) || null;
  }

  function getContext(cm) {
    const cur = cm.getCursor();
    const lines = cm.getValue().split('\n');
    const prefix = lines.slice(0, cur.line).concat([lines[cur.line].slice(0, cur.ch)]).join('\n');
    const suffix = [lines[cur.line].slice(cur.ch)].concat(lines.slice(cur.line + 1)).join('\n');

    let filename = '', language = 'text';
    try {
      const tab = window.App && window.App.editor && window.App.editor.currentTab;
      filename = (tab && (tab.path || tab.name)) || '';
      const ext = (filename.split('.').pop() || '').toLowerCase();
      const map = {
        py: 'python', js: 'javascript', mjs: 'javascript', ts: 'typescript',
        html: 'html', htm: 'html', css: 'css', scss: 'scss', json: 'json',
        md: 'markdown', sh: 'bash', bash: 'bash', java: 'java', c: 'c',
        cpp: 'cpp', rs: 'rust', go: 'go', php: 'php', rb: 'ruby', sql: 'sql',
        yml: 'yaml', yaml: 'yaml', xml: 'xml', txt: 'text'
      };
      language = map[ext] || 'text';
    } catch (_) {}
    return { cur, prefix, suffix, filename, language };
  }

  async function trigger(cm) {
    if (!cm) return;
    cleanup(cm);
    const { cur, prefix, suffix, filename, language } = getContext(cm);

    if (!prefix.trim()) {
      toast('Cần code trước cursor để gợi ý', 'warning');
      return;
    }

    const loader = document.createElement('span');
    loader.className = 'ai-ac-loading';
    loader.textContent = ' ⏳';
    loader.style.cssText = 'color:#89b4fa;font-size:12px;pointer-events:none;';
    cm.addWidget(cur, loader, false);

    try {
      const r = await fetch('/api/ai_autocomplete/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prefix, suffix, language, filename })
      });
      const d = await r.json();
      cleanup(cm);

      if (!d.ok) { toast('AI: ' + (d.error || 'Không có gợi ý'), 'error'); return; }
      const text = (d.suggestion || '').replace(/\s+$/, '');
      if (!text) { toast('AI không trả về gì', 'warning'); return; }

      if (d.used_fallback) toast('Fallback: ' + (d.model_used || ''), 'warning');
      showGhost(cm, cur, text, d);
    } catch (e) {
      cleanup(cm);
      toast('Lỗi: ' + e.message, 'error');
    }
  }

  function showGhost(cm, pos, text, meta) {
    const el = document.createElement('span');
    el.style.cssText =
      'color:#6c7086;opacity:.65;font-style:italic;white-space:pre;' +
      'font-family:inherit;pointer-events:none;';
    el.textContent = text;
    cm.addWidget(pos, el, false);

    activeGhostEl = el;
    activePos = pos;

    const providerLabel = meta && meta.provider ? ` [${meta.provider}]` : '';
    toast(`AI${providerLabel} gợi ý — Tab chấp nhận · Esc huỷ`, 'info');

    const accept = (cmx) => {
      cmx.replaceRange(text, pos);
      cleanup(cm);
      return true;
    };
    const cancel = (cmx) => { cleanup(cm); return true; };

    activeKeyMap = { 'Tab': accept, 'Esc': cancel };
    cm.addKeyMap(activeKeyMap);

    const abort = () => { cleanup(cm); };
    cm.once('change', abort);
    cm.once('cursorActivity', abort);

    setTimeout(() => { if (activeGhostEl === el) cleanup(cm); }, 30000);
  }

  function hook() {
    const cm = getCM();
    if (!cm) return setTimeout(hook, 500);
    if (cm.__ai_ac_hooked__) return;
    cm.__ai_ac_hooked__ = true;

    log('editor hooked');

    cm.addKeyMap({ 'Ctrl-Space': (cx) => { trigger(cx); return true; } });

    const host = document.querySelector('.toolbar, #toolbar, .editor-toolbar, .topbar');
    const btn = document.createElement('button');
    btn.id = 'ai-ac-btn';
    btn.title = 'AI Autocomplete (Ctrl+Space)';
    btn.textContent = '🤖 AI';
    btn.style.cssText =
      'padding:5px 10px;margin:0 3px;border-radius:6px;cursor:pointer;' +
      'background:#89b4fa22;border:1px solid #89b4fa;color:#89b4fa;' +
      'font-size:12px;font-weight:600;';
    btn.addEventListener('click', () => trigger(getCM()));

    const settingsBtn = document.createElement('button');
    settingsBtn.title = 'AI Settings';
    settingsBtn.textContent = '⚙';
    settingsBtn.style.cssText =
      'padding:5px 9px;margin:0 3px;border-radius:6px;cursor:pointer;' +
      'background:#313244;border:1px solid #45475a;color:#cdd6f4;font-size:12px;';
    settingsBtn.addEventListener('click', () => {
      window.open('/module/ai_autocomplete/', '_blank', 'noopener');
    });

    if (host) { host.appendChild(btn); host.appendChild(settingsBtn); }
    else {
      btn.style.cssText +=
        'position:fixed;bottom:84px;right:20px;z-index:99998;' +
        'padding:10px 14px;font-size:14px;box-shadow:0 4px 14px rgba(0,0,0,.5);';
      document.body.appendChild(btn);
    }
  }

  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', () => setTimeout(hook, 800));
  else setTimeout(hook, 800);

  log('overlay loaded — © ACDV-Teams');
})();