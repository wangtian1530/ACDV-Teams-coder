(function () {
  'use strict';
  if (window.__acdvCodeSuggestLoaded) return;
  window.__acdvCodeSuggestLoaded = true;

  const API           = '/api/code_suggest/complete';
  const SETTINGS_API  = '/api/settings/module/get';
  const IDENT         = /[A-Za-z0-9_$]/;
  const WORD_START    = /[A-Za-z_$]/;

  let cm         = null;
  let box        = null;
  let list       = null;
  let items      = [];
  let selected   = 0;
  let visible    = false;
  let keymapObj  = null;
  let debounce   = null;
  let suppress   = false;
  let bootTries  = 0;
  let settings   = { enabled: true, min_prefix: 1 };

  // ─── Editor discovery ─────────────────────────────────
  function findEditor() {
    if (window.editor && window.editor.getMode && window.editor.getCursor) return window.editor;
    if (window.cm     && window.cm.getMode     && window.cm.getCursor)     return window.cm;
    if (window.CodeMirror) {
      const el = document.querySelector('.CodeMirror');
      if (el && el.CodeMirror) return el.CodeMirror;
    }
    return null;
  }

  function getLanguage() {
    if (!cm) return null;
    try {
      const m = cm.getMode();
      const n = (m && (m.name || m.helperType || '')) || '';
      if (n === 'python') return 'python';
      if (['javascript','jsx','typescript','typescript-jsx'].includes(n)) return 'javascript';
      if (['shell','bash','sh'].includes(n)) return 'bash';
    } catch (_) {}
    return null;
  }

  function extractPrefix(line, ch) {
    let i = ch;
    while (i > 0 && IDENT.test(line.charAt(i - 1))) i--;
    return line.slice(i, ch);
  }

  // ─── Box ──────────────────────────────────────────────
  function buildBox() {
    if (box) return;
    box = document.createElement('div');
    box.className = 'csuggest-box';
    box.style.display = 'none';
    list = document.createElement('ul');
    list.className = 'csuggest-list';
    box.appendChild(list);
    document.body.appendChild(box);

    document.addEventListener('mousedown', (e) => {
      if (visible && box && !box.contains(e.target)) hide();
    }, true);

    if (cm) {
      cm.on('scroll', () => { if (visible) positionBox(); });
    }
  }

  function positionBox() {
    if (!cm || !box) return;
    try {
      const c = cm.cursorCoords(false, 'window');
      const boxH = Math.min(box.offsetHeight || 0, 280);
      let top = c.bottom + 4;
      // flip up nếu chạm đáy viewport
      if (top + boxH > window.innerHeight - 10) top = c.top - boxH - 4;
      box.style.left = Math.max(4, c.left) + 'px';
      box.style.top  = Math.max(4, top)  + 'px';
    } catch (_) {}
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
    }[c]));
  }

  function iconFor(type) {
    return { snippet:'★', keyword:'K', builtin:'B', local:'L' }[type] || '·';
  }

  function render() {
    if (!list) return;
    list.innerHTML = '';
    items.forEach((it, idx) => {
      const li = document.createElement('li');
      li.className = 'csuggest-item' + (idx === selected ? ' selected' : '');
      li.innerHTML =
        '<span class="csuggest-icon csuggest-type-' + it.type + '">' + iconFor(it.type) + '</span>' +
        '<span class="csuggest-label">' + escapeHtml(it.label) + '</span>' +
        (it.detail ? '<span class="csuggest-detail">' + escapeHtml(it.detail) + '</span>' : '');
      li.addEventListener('mousedown', (e) => { e.preventDefault(); selected = idx; accept(); });
      li.addEventListener('mouseover', () => { selected = idx; updateSelection(); });
      list.appendChild(li);
    });
  }

  function updateSelection() {
    if (!list) return;
    Array.from(list.children).forEach((li, i) => {
      li.classList.toggle('selected', i === selected);
    });
    const el = list.children[selected];
    if (el && el.scrollIntoView) el.scrollIntoView({ block: 'nearest' });
  }

  function show() {
    if (visible || !box) return;
    visible = true;
    box.style.display = 'block';
    positionBox();
    keymapObj = {
      'Up':    () => { move(-1); return true; },
      'Down':  () => { move(1);  return true; },
      'Enter': () => { accept(); return true; },
      'Tab':   () => { accept(); return true; },
      'Esc':   () => { hide();   return true; },
    };
    cm.addKeyMap(keymapObj);
  }

  function hide() {
    if (!visible) return;
    visible = false;
    if (box) box.style.display = 'none';
    if (keymapObj && cm) { cm.removeKeyMap(keymapObj); keymapObj = null; }
    items = []; selected = 0;
  }

  function move(delta) {
    if (!items.length) return;
    selected = (selected + delta + items.length) % items.length;
    updateSelection();
  }

  function accept() {
    if (!items.length) return hide();
    const it = items[selected];
    const text = it.insert || it.label;
    const cur  = cm.getCursor();
    const line = cm.getLine(cur.line);
    const prefix = extractPrefix(line, cur.ch);
    const from = { line: cur.line, ch: cur.ch - prefix.length };

    // auto-indent cho multiline snippets
    const indent = (line.match(/^[\t ]*/) || [''])[0];
    const final = text.indexOf('\n') >= 0
      ? text.split('\n').map((ln, i) =>
          i === 0 ? ln : (ln ? indent + ln : ln)
        ).join('\n')
      : text;

    suppress = true;
    cm.replaceRange(final, from, cur, '+input');
    hide();
    cm.focus();
    setTimeout(() => { suppress = false; }, 50);
  }

  // ─── Fetch ────────────────────────────────────────────
  function fetchSuggestions(lang, prefix, cursor) {
    if (!lang) return hide();
    let content = cm.getValue();
    // cap 50KB quanh cursor để nhẹ
    if (content.length > 50000) {
      const off = cm.indexFromPos(cursor);
      const a = Math.max(0, off - 25000);
      const b = Math.min(content.length, off + 25000);
      content = content.slice(a, b);
    }

    fetch(API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        language: lang,
        prefix: prefix,
        content: content,
        line: cursor.line,
      }),
    })
      .then(r => r.json())
      .then(data => {
        if (!data || !data.ok || !Array.isArray(data.suggestions) || !data.suggestions.length) {
          return hide();
        }
        // bỏ qua nếu suggestion == prefix (không giúp gì)
        const list2 = data.suggestions.filter(s => s.label !== prefix);
        if (!list2.length) return hide();
        items = list2;
        selected = 0;
        render();
        show();
      })
      .catch(() => hide());
  }

  function onInput() {
    if (suppress) return;
    if (!settings.enabled) return hide();
    const lang = getLanguage();
    if (!lang) return hide();

    const cur  = cm.getCursor();
    const line = cm.getLine(cur.line);
    const prefix = extractPrefix(line, cur.ch);
    if (!prefix || !WORD_START.test(prefix.charAt(0))) return hide();
    if (prefix.length < (settings.min_prefix || 1)) return hide();

    clearTimeout(debounce);
    debounce = setTimeout(() => fetchSuggestions(lang, prefix, cur), 120);
  }

  function manualTrigger() {
    const lang = getLanguage();
    if (!lang) return;
    const cur  = cm.getCursor();
    const line = cm.getLine(cur.line);
    const prefix = extractPrefix(line, cur.ch);
    fetchSuggestions(lang, prefix, cur);
  }

  // ─── Bind ─────────────────────────────────────────────
  function bindEvents() {
    let hasInputRead = false;
    cm.on('inputRead', () => { hasInputRead = true; onInput(); });
    cm.on('change', (ed, change) => {
      if (hasInputRead) return;
      if (change.origin === '+input') onInput();
    });
    cm.on('cursorActivity', () => { if (visible) positionBox(); });
    cm.on('blur', () => {
      setTimeout(() => { if (visible && !box.matches(':hover')) hide(); }, 150);
    });
    cm.addKeyMap({
      'Ctrl-Space': () => { manualTrigger(); return true; },
    });
  }

  // ─── Settings ─────────────────────────────────────────
  function loadSettings() {
    fetch(SETTINGS_API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'code_suggest' }),
    })
      .then(r => r.json())
      .then(d => {
        const v = (d && (d.values || d.data || d.result)) || d || {};
        settings = Object.assign(settings, v);
      })
      .catch(() => {});
  }

  // ─── Boot ─────────────────────────────────────────────
  function boot() {
    cm = findEditor();
    if (!cm) {
      if (++bootTries > 100) return; // 30s timeout
      setTimeout(boot, 300);
      return;
    }
    buildBox();
    bindEvents();
    loadSettings();
    console.info('[code_suggest] ready');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();